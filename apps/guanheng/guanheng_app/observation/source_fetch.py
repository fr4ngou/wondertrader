"""独立采集的有限HTTP读取；原字节先登记，全部来源共用原总截止。"""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import time
from urllib.parse import urlsplit


class SourceFailure(Exception):
    """固定错误码；公开回执不包含供应商原文、URL或部署配置。"""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass
class CollectionBudget:
    deadline: float
    max_requests: int = 256
    max_bytes: int = 256*1024*1024
    response_bytes: int = 16*1024*1024
    requests: int = 0
    captured_bytes: int = 0
    cancelled: object = None
    http_requests: int = 0
    sdk_requests: int = 0
    decoded_bytes: int = 0

    def remaining(self):
        if self.cancelled is not None and self.cancelled():
            raise SourceFailure('collection_stopped')
        value = self.deadline-time.monotonic()
        if value <= 0:
            raise SourceFailure('collection_timeout')
        return value


    def request(self,kind='http'):
        self.remaining()
        if kind not in ('http','sdk'):raise SourceFailure('invalid_request_kind')
        if self.requests >= self.max_requests:
            raise SourceFailure('request_budget_exceeded')
        self.requests += 1
        if kind=='http':self.http_requests+=1
        else:self.sdk_requests+=1

    def consume(self, count):
        self.remaining()
        if self.captured_bytes+count > self.max_bytes:
            raise SourceFailure('capture_budget_exceeded')
        self.captured_bytes += count

    def expand(self,count):
        self.remaining()
        if self.decoded_bytes+count>self.max_bytes:
            raise SourceFailure('decode_budget_exceeded')
        self.decoded_bytes+=count

    def request_deadline(self,seconds):
        """单次请求的绝对截止；分块抵达不能续期，仍先服从原批次D/停止。"""
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=60:
            raise SourceFailure('invalid_request_timeout')
        self.remaining()
        return RequestDeadline(self,min(self.deadline,time.monotonic()+seconds))


class RequestDeadline:
    """保存原请求D；OS毫秒取整提前报超时时仍按最早预算owner分类。"""
    def __init__(self,budget,end):self.budget,self.end=budget,end

    def __call__(self):
        self.budget.remaining();value=self.end-time.monotonic()
        if value<=0:raise SourceFailure('source_request_timeout')
        return value

    def timeout(self):
        self.budget.remaining()
        raise SourceFailure('collection_timeout' if self.end>=self.budget.deadline else 'source_request_timeout')


class BoundedContentStore:
    """同一采集D/停止信号覆盖原内容IO；原store继续拥有布局和原子写入。"""
    def __init__(self,store,budget):
        self.store,self.budget,self.root=store,budget,store.root

    def get(self,sha):
        self.budget.remaining();body=self.store.get(sha);self.budget.remaining();return body

    def put(self,body,*,kind='raw'):
        self.budget.remaining();sha=self.store.put(body,kind=kind);self.budget.remaining();return sha


class Fetcher:
    """单来源拥有HTTP client；批次budget由采集owner注入，不延长调用者D。

    HTTP/DNS或外部SDK无法协作取消时，独立进程的原Job拥有最终回收责任。
    普通观察读取不会构造本对象或导入可选HTTP依赖。
    """
    def __init__(self, objects, allowed_hosts, timeout=15, *, budget, client=None):
        from .http_transport import owned_client
        self.objects, self.allowed_hosts, self.records = objects, set(allowed_hosts), []
        self.budget, self.timeout = budget, timeout
        self._request_remaining = self.budget.remaining
        self.client = client if client is not None else owned_client(self._remaining)

    def _remaining(self,timed_out=False):
        if timed_out:self._request_remaining.timeout()
        return self._request_remaining()

    def close(self):
        self.client.close()

    def get(self, url, params=None, referer=None, *, session_handoff=False):
        return self._read('GET', url, params=params, referer=referer,session_handoff=session_handoff)

    def post_readonly(self, url, form, *, referer=None, session_handoff=False):
        """仅供已核只读查询适配器；公开表单归档，Cookie仅由原client内存持有。

        可选会话交接只接受一次307回到原URL且设置Cookie；两次请求共用
        原请求绝对D和批次额度，其他跳转继续失败，不导入浏览器认证资料。
        """
        if (type(form) is not dict or not 1 <= len(form) <= 64
                or any(type(k) is not str or not 1 <= len(k) <= 100
                       or type(v) is not str or len(v) > 4096 for k,v in form.items())
                or type(session_handoff) is not bool):
            raise SourceFailure('source_public_form_invalid')
        return self._read('POST', url, form=form, referer=referer, session_handoff=session_handoff)

    def _read(self, method, url, *, params=None, form=None, referer=None, session_handoff=False):
        import httpx
        if type(session_handoff) is not bool:raise SourceFailure('source_public_session_invalid')
        parts = urlsplit(url)
        host = parts.hostname
        if (parts.scheme not in ('http','https') or host not in self.allowed_hosts
                or parts.username is not None or parts.password is not None
                or parts.port not in (None,80,443)):
            raise SourceFailure('unregistered_source_host')
        if referer and urlsplit(referer).hostname not in self.allowed_hosts:
            raise SourceFailure('unregistered_source_host')
        handoff_deadline=self.budget.request_deadline(self.timeout) if session_handoff else None
        for attempt in range(2):
            request_remaining=handoff_deadline or self.budget.request_deadline(self.timeout)
            self._request_remaining=request_remaining
            self.budget.request()
            try:
                remaining = request_remaining()
                options={'data':form} if method=='POST' else {}
                with self.client.stream(method, url, params=params, **options,
                        headers={'Referer':referer} if referer else None,
                        timeout=httpx.Timeout(remaining)) as response:
                    chunks, size = [], 0
                    # 消费原始网络块，HTTPX解码及64KiB聚块均退出输入准入路径。
                    for chunk in response.iter_raw():
                        request_remaining()
                        self.budget.consume(len(chunk)); size += len(chunk)
                        if size > self.budget.response_bytes:
                            raise SourceFailure('response_budget_exceeded')
                        chunks.append(chunk)
                    raw = b''.join(chunks)
                    wire_sha = self.objects.put(raw)
                    record=dict(sha256=wire_sha,source_host=host,status=response.status_code,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),query=params or {},attempt=attempt+1,
                        request_url=str(response.request.url),media_type=response.headers.get('content-type'),
                        encoding=response.encoding,compression=response.headers.get('content-encoding') or 'identity',
                        transport_compression=response.headers.get('content-encoding'),kind='http_wire')
                    if method=='POST':record.update(method=method,form=dict(form))
                    self.records.append(record)
                    from .http_transport import decode_body
                    body=decode_body(raw,response.headers.get('content-encoding'),self.budget,request_remaining)
                    sha=self.objects.put(body)
                    self.records.append(dict(record,sha256=sha,kind='http_body',compression='identity',parent_sha256=wire_sha))
                    request_remaining()
                    if response.status_code in (401,403):
                        raise SourceFailure('source_permission_denied')
                    if (session_handoff and not attempt
                            and (response.status_code==307 or method=='GET' and response.status_code==302)
                            and response.headers.get('location')==str(response.request.url)
                            and bool(response.cookies)):
                        continue
                    if response.status_code == 429:
                        hint = response.headers.get('Retry-After','1')
                        try:
                            delay = float(hint)
                        except ValueError:
                            try:
                                when = parsedate_to_datetime(hint)
                                delay = (when.replace(tzinfo=when.tzinfo or timezone.utc)-datetime.now(timezone.utc)).total_seconds()
                            except (ValueError,TypeError,OverflowError):
                                raise SourceFailure('source_rate_limited') from None
                        if attempt or not math.isfinite(delay) or delay > 5:
                            raise SourceFailure('source_rate_limited')
                        self._wait(max(0,delay)); continue
                    if response.status_code != 200:
                        raise SourceFailure('source_http_'+str(response.status_code))
                    return body
            except (httpx.TimeoutException,httpx.NetworkError):
                request_remaining()
                if attempt:
                    raise SourceFailure('source_network_timeout') from None
                self._wait(1)
        raise SourceFailure('source_retry_exhausted')

    def _wait(self, seconds):
        if seconds >= self.budget.remaining():
            raise SourceFailure('collection_timeout')
        time.sleep(seconds)
        self.budget.remaining()
