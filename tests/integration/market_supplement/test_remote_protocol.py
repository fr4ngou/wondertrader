"""远端协议断连→原Fetcher分类→MSF缺口恢复；仅本机TCP和HTTPX隔离运输。"""
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import ContentStore,DAYS,QmtTransport,encode,plan
import httpx
import pytest

from guanheng_app.observation.source_fetch import CollectionBudget,Fetcher,SourceFailure
from integrations.guanheng.market_supplement_capture import collect_supplement,SupplementPending
from integrations.guanheng.market_supplement_store import MarketSupplementStore


@contextmanager
def disconnected_server(stage):
    """收到一次完整请求后在headers前或声明的正文完成前关连接。"""
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(4);listener.settimeout(.05)
    stop=threading.Event();accepted=[];errors=[]
    def serve():
        while not stop.is_set():
            try:connection,_=listener.accept()
            except socket.timeout:continue
            except OSError:return
            accepted.append(True)
            try:
                with connection:
                    connection.settimeout(1)
                    received=b''
                    while b'\r\n\r\n' not in received and len(received)<8192:
                        chunk=connection.recv(4096)
                        if not chunk:break
                        received+=chunk
                    if stage=='body':
                        connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\nConnection: close\r\n\r\n{"partial":')
            except OSError as exc:errors.append(type(exc).__name__)
    thread=threading.Thread(target=serve);thread.start()
    try:yield listener.getsockname()[1],accepted,errors
    finally:
        stop.set();listener.close();thread.join(2)
        assert not thread.is_alive()


class LocalTCPTransport(httpx.BaseTransport):
    """Fetcher仍验证原无端口来源URL；注入运输只把网络接到临时回环端口。"""
    def __init__(self,port):
        self.port=port;self.inner=httpx.HTTPTransport(retries=0);self.closed=False
    def handle_request(self,request):
        target=request.url.copy_with(scheme='http',host='127.0.0.1',port=self.port)
        mapped=httpx.Request(request.method,target,headers=request.headers,content=request.content,
                             extensions=request.extensions)
        return self.inner.handle_request(mapped)
    def close(self):self.closed=True;self.inner.close()


def budget(**kwargs):
    return CollectionBudget(time.monotonic()+10,max_requests=100,max_bytes=1024*1024,
                            response_bytes=65536,**kwargs)


@pytest.mark.parametrize('stage',['headers','body'])
def test_real_tcp_disconnect_is_sanitized_once_without_retry(tmp_path,stage,monkeypatch):
    with disconnected_server(stage) as (port,accepted,errors):
        transport=LocalTCPTransport(port)
        client=httpx.Client(transport=transport,trust_env=False)
        current=budget();fetch=Fetcher(ContentStore(tmp_path/'raw'),['fixture.test'],timeout=1,
                                       budget=current,client=client)
        def forbidden_wait(*a):raise AssertionError('remote protocol errors must not auto-retry')
        monkeypatch.setattr(fetch,'_wait',forbidden_wait)
        try:
            with pytest.raises(SourceFailure) as failure:fetch.get('http://fixture.test/disconnect')
            assert failure.value.code=='source_remote_protocol'
            assert failure.value.__cause__ is None and failure.value.__suppress_context__
            assert str(failure.value)=='source_remote_protocol'
            assert current.http_requests==1 and current.requests==1
            assert len(accepted)==1 and not errors
            assert fetch.records==[]  # 头/正文不完整的字节没有冒充成功原件。
            if stage=='body':assert 0<current.captured_bytes<100
        finally:fetch.close()
        assert client.is_closed and transport.closed


@pytest.mark.parametrize('higher_priority',['cancel','batch_deadline','request_deadline'])
def test_original_cancel_or_deadline_wins_over_protocol_error(tmp_path,higher_priority):
    stopped={'value':False};current=budget(cancelled=lambda:stopped['value']);calls=[]
    def handler(request):
        calls.append(request.url)
        if higher_priority=='cancel':stopped['value']=True
        elif higher_priority=='batch_deadline':current.deadline=time.monotonic()-1
        else:time.sleep(.025)
        raise httpx.RemoteProtocolError('synthetic private provider detail',request=request)
    client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    fetch=Fetcher(ContentStore(tmp_path/'raw'),['fixture.test'],timeout=.01 if higher_priority=='request_deadline' else 1,
                  budget=current,client=client)
    try:
        with pytest.raises(SourceFailure) as failure:fetch.get('http://fixture.test/disconnect')
        expected={'cancel':'collection_stopped','batch_deadline':'collection_timeout','request_deadline':'source_request_timeout'}
        assert failure.value.code==expected[higher_priority]
        assert 'provider detail' not in str(failure.value)
        assert len(calls)==1 and current.http_requests==1
        assert fetch.records==[]
    finally:fetch.close()
    assert client.is_closed


def test_collector_protocol_gap_persists_and_resumes_only_missing(tmp_path):
    observed=[];fail_second={'value':True}
    def handler(request):
        day=request.url.params['STAT_DATE'];observed.append(day)
        if day==DAYS[-1] and fail_second['value']:
            raise httpx.RemoteProtocolError('synthetic header disconnect',request=request)
        value=dict(actionErrors=[],fieldErrors={},pageHelp=dict(total=1,pageCount=1,pageNo=1),
                   result=[dict(STAT_DATE=day,SEC_CODE='510300',TOT_VOL='175000.125')])
        return httpx.Response(200,stream=httpx.ByteStream(encode(value)))
    objects=ContentStore(tmp_path/'raw');qmt=QmtTransport();target=plan(('etf_total_shares','SSE.510300'))
    def make_fetch():
        client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
        return Fetcher(objects,['query.sse.com.cn','www.sse.com.cn'],timeout=1,budget=budget(),client=client)
    def collect(fetch):
        return collect_supplement(target,DAYS[-1],DAYS,tmp_path/'work',objects=objects,fetch=fetch,
            qmt_transport=qmt,calendar_coverage=(DAYS[0],DAYS[-1]),deadline=time.monotonic()+10)
    first=make_fetch()
    try:
        with pytest.raises(SupplementPending):collect(first)
        coverage=json.loads((tmp_path/'work/COVERAGE.json').read_bytes())
        assert coverage['complete'] is False and coverage['observed']==1 and coverage['expected']==2
        assert coverage['gaps']==[dict(date=DAYS[-1],metric='etf_total_shares',symbol='SSE.510300',reason='source_remote_protocol')]
        prior=json.loads((tmp_path/'work/STATE.json').read_bytes())['rows']
        assert len(prior)==1 and not (tmp_path/'work/catalog.json').exists()
        assert observed==list(reversed(DAYS)) and first.budget.http_requests==2
    finally:first.close()
    fail_second['value']=False;second=make_fetch()
    try:descriptor=collect(second)
    finally:second.close();qmt.close()
    restored=json.loads(Path(descriptor['path']).read_bytes())
    assert restored['complete'] is True and restored['gaps']==[]
    assert restored['rows'][0]==next(iter(prior.values()))
    assert observed==[DAYS[-1],DAYS[0],DAYS[-1]] and second.budget.http_requests==1
    assert first.client.is_closed and second.client.is_closed
    store=MarketSupplementStore(descriptor)
    try:store.verify_sources()
    finally:store.close()


@pytest.mark.parametrize('legacy_error',[httpx.ReadTimeout,httpx.ReadError])
def test_existing_timeout_or_network_retry_policy_stays_intact(tmp_path,monkeypatch,legacy_error):
    attempts=[];waits=[]
    def handler(request):
        attempts.append(request.url)
        if len(attempts)==1:raise legacy_error('synthetic existing source failure',request=request)
        return httpx.Response(200,stream=httpx.ByteStream(b'complete source bytes'))
    current=budget();client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    fetch=Fetcher(ContentStore(tmp_path/'raw'),['fixture.test'],timeout=1,budget=current,client=client)
    # 记录原1秒等待意图；避免这个隔离回归为纯等待耗时。
    monkeypatch.setattr(fetch,'_wait',lambda seconds:waits.append(seconds))
    try:
        assert fetch.get('http://fixture.test/source')==b'complete source bytes'
        assert len(attempts)==2 and waits==[1]
        assert current.http_requests==2
        assert len(fetch.records)==2  # 完整wire和body各存一件，失败尝试不冒成功原件。
    finally:fetch.close()


@pytest.mark.parametrize('stop_kind',['cancel','owner_deadline'])
def test_collector_preserves_coverage_but_original_stop_wins_over_pending(tmp_path,stop_kind):
    stopped={'value':False};owner_deadline=time.monotonic()+(.5 if stop_kind=='owner_deadline' else 10)
    current=CollectionBudget(owner_deadline,cancelled=lambda:stopped['value'])
    def handler(request):
        if stop_kind=='cancel':stopped['value']=True
        else:time.sleep(.6)
        raise httpx.RemoteProtocolError('synthetic disconnect concurrent with owner stop',request=request)
    objects=ContentStore(tmp_path/'raw');qmt=QmtTransport()
    client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    fetch=Fetcher(objects,['query.sse.com.cn','www.sse.com.cn'],budget=current,timeout=1,client=client)
    try:
        with pytest.raises(InterruptedError if stop_kind=='cancel' else TimeoutError):
            collect_supplement(plan(('etf_total_shares','SSE.510300')),DAYS[-1],DAYS,tmp_path/'work',
                objects=objects,fetch=fetch,qmt_transport=qmt,calendar_coverage=(DAYS[0],DAYS[-1]),
                deadline=owner_deadline,cancelled=lambda:stopped['value'])
        coverage=json.loads((tmp_path/'work/COVERAGE.json').read_bytes())
        assert coverage['complete'] is False and coverage['observed']==0
        latest=next(row for row in coverage['gaps'] if row['date']==DAYS[-1])
        assert latest['reason']==('collection_stopped' if stop_kind=='cancel' else 'collection_timeout')
        assert not (tmp_path/'work/catalog.json').exists()
    finally:fetch.close();qmt.close()
