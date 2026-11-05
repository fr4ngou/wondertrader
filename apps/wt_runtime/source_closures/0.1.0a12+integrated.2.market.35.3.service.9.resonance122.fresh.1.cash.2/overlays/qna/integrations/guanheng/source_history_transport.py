"""源值采集的原bound客户端：原UUID先留证，通信事实仍归Host Journal。"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import hmac
import http.client
import ipaddress
import io
import math
import os
import time
from urllib.parse import urlsplit
from uuid import uuid4

from guanheng_qmt_shm import bound
from guanheng_qmt_shm.bulk_clock import WindowsBulkUptimeClock
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_capabilities import validate_read_profile, validate_read_request, operation_descriptor


class SourcePending(RuntimeError):
    """保留原请求身份；调用者以后只核原GET。"""


def require(value):
    if not value:
        raise ValueError('source preparation transport identity differs')


class _DeadlineRead(io.RawIOBase):
    """http.client内部readline/read也须在每次实际接收前消费同一截止。"""
    def __init__(self,raw,owner):self.raw,self.owner=raw,owner
    def readable(self):return True
    def readinto(self,buffer):
        self.owner.before_io();return self.raw.readinto(buffer)
    def close(self):
        try:self.raw.close()
        finally:super().close()


class _DeadlineSocket:
    """仅用于显式RPC预算；复用原socket及HTTP解析，不增加线程或运输。"""
    def __init__(self,socket,clock,deadline,timeout):
        self.socket,self.clock,self.deadline,self.timeout=socket,clock,deadline,timeout
    def __getattr__(self,name):return getattr(self.socket,name)
    def before_io(self):
        remaining=self.deadline-self.clock()
        if remaining<=0:raise SourcePending('source RPC deadline')
        self.socket.settimeout(min(self.timeout,remaining))
    def sendall(self,*args,**kwargs):
        self.before_io();return self.socket.sendall(*args,**kwargs)
    def makefile(self,mode):
        require(mode=='rb')
        return io.BufferedReader(_DeadlineRead(self.socket.makefile(mode,buffering=0),self))


class BoundHistorySource:
    """默认单次连接；显式复用由最外层RPC预算拥有，无后台线程或自动重发。"""

    def __init__(self, configuration, *, environ=None, clock=time.monotonic, reuse_connections=False):
        require(type(configuration) is dict and set(configuration) == {'base_url','key_id','secret_env','timeout'})
        value=urlsplit(configuration['base_url'])
        require(value.scheme=='http' and value.hostname is not None and ipaddress.ip_address(value.hostname).is_loopback
            and value.port is not None and not value.username and not value.password and value.path in ('','/')
            and not value.query and not value.fragment)
        require(type(configuration['timeout'])in(int,float) and math.isfinite(configuration['timeout'])
            and .1<=configuration['timeout']<=30)
        require(type(configuration['key_id'])is str and 1<=len(configuration['key_id'])<=128)
        require(type(reuse_connections)is bool)
        environment=os.environ if environ is None else environ
        secret=environment[configuration['secret_env']]
        require(type(secret)is str and 32<=len(secret.encode('utf8'))<=8192)
        self.host,self.port,self.key_id,self.secret=value.hostname,value.port,configuration['key_id'],secret.encode('utf8')
        self.timeout,self.clock=configuration['timeout'],clock
        self._rpc_seconds=None
        self._reuse_connections=reuse_connections
        self._rpc_depth=0
        self._connection=None
        self.uptime=WindowsBulkUptimeClock()

    def close(self):
        """连接关闭成功后才释放owner；失败异常保留本实例供调用方重试释放。"""
        connection=self._connection
        if connection is not None:
            try:connection.close()
            except BaseException as error:
                error.source_transport_owner=self
                raise
            self._connection=None

    @contextmanager
    def rpc_budget(self,seconds):
        """创建线程内临时收紧每次HTTP交换；原默认预算保持。"""
        require(type(seconds)in(int,float)and math.isfinite(seconds)and .1<=seconds<=30)
        if self._reuse_connections and self._rpc_depth==0:
            # 上次关闭若失败，先恢复其唯一owner；不创建第二条连接绕过失败。
            self.close()
        previous=(self.timeout,self._rpc_seconds);self.timeout=min(self.timeout,seconds)
        self._rpc_seconds=seconds if self._rpc_seconds is None else min(self._rpc_seconds,seconds)
        self._rpc_depth+=1
        try:yield
        finally:
            self.timeout,self._rpc_seconds=previous
            self._rpc_depth-=1
            if self._reuse_connections and self._rpc_depth==0:self.close()

    def exchange(self, method, path, body, deadline):
        if self._rpc_seconds is not None:deadline=min(deadline,self.clock()+self._rpc_seconds)
        remaining=deadline-self.clock()
        if remaining<=0:raise SourcePending('source deadline')
        stamp,nonce=str(time.time()),str(uuid4());digest=bound.digest(body)
        signature=hmac.new(self.secret,'\n'.join((method,path,stamp,nonce,digest)).encode('utf8'),hashlib.sha256).hexdigest()
        headers={'X-QMT-Key-Id':self.key_id,'X-QMT-Timestamp':stamp,'X-QMT-Nonce':nonce,
            'X-QMT-Content-SHA256':digest,'X-QMT-Signature':signature,'Content-Type':'application/json'}
        reuse=self._reuse_connections and self._rpc_depth>0
        if reuse:
            if self._connection is None:
                self._connection=http.client.HTTPConnection(self.host,self.port,timeout=min(self.timeout,remaining))
            connection=self._connection
            connection.timeout=min(self.timeout,remaining)
        else:
            connection=http.client.HTTPConnection(self.host,self.port,timeout=min(self.timeout,remaining))
        response=None;failed=True
        try:
            if self._rpc_seconds is not None:
                if connection.sock is None:connection.connect()
                if isinstance(connection.sock,_DeadlineSocket):
                    # 同一预算内每次交换都重新绑定其绝对D，避免沿用前次已过期D。
                    connection.sock.deadline,connection.sock.timeout=deadline,self.timeout
                else:connection.sock=_DeadlineSocket(connection.sock,self.clock,deadline,self.timeout)
            connection.request(method,path,body=body,headers=headers)
            if self._rpc_seconds is not None:connection.sock.before_io()
            response=connection.getresponse();blocks=[];size=0
            while True:
                remaining=deadline-self.clock()
                if remaining<=0:raise SourcePending('source deadline')
                if connection.sock is not None:connection.sock.settimeout(min(self.timeout,remaining))
                chunk=response.read(min(65536,4194305-size))
                size+=len(chunk);require(size<=4194304)
                if not chunk:break
                blocks.append(chunk)
            if self.clock()>=deadline:raise SourcePending('source deadline')
            result=response.status,decode(b''.join(blocks));failed=False
            return result
        except (OSError,http.client.HTTPException,TimeoutError):
            raise SourcePending('source exchange unresolved') from None
        finally:
            try:
                if response is not None:response.close()
            except BaseException:
                failed=True
                raise
            finally:
                if reuse:
                    if failed or response is not None and response.will_close:self.close()
                else:connection.close()

    def binding(self, deadline):
        code,value=self.exchange('GET','/internal/v1/read-binding',b'',deadline)
        if code!=200:raise SourcePending('source unavailable')
        require(type(value)is dict and set(value)=={'schema_version','binding','binding_sha256',
            'read_profile_body_b64','read_profile_body_sha256','limits','order_ready'})
        require(value['schema_version']==bound.SCHEMA and value['order_ready']is False)
        checked=bound.binding(value['binding']);require(bound.digest(canonical(checked))==value['binding_sha256'])
        raw=bound.unb64(value['read_profile_body_b64'],4096)
        require(bound.digest(raw)==value['read_profile_body_sha256']==checked['capability_sha256'])
        limits=value['limits']
        require(type(limits)is dict and set(limits)=={'max_request_bytes','max_result_bytes','max_http_request_bytes','max_http_response_bytes'})
        require(all(type(v)is int and 0<v<=4194304 for v in limits.values()))
        profile=validate_read_profile(decode(raw),max_result_bytes=limits['max_result_bytes'])
        require(profile['read_profile_version']=='qmt.read-profile.v6' and
            {'market.history_1m','market.history_prepare'}<=set(profile['read_operations']))
        return dict(value,profile=profile)

    def plan(self, operation, arguments, metadata, deadline):
        desc=operation_descriptor(metadata['profile'],operation,max_result_bytes=metadata['limits']['max_result_bytes'])
        remaining=int((deadline-self.clock())*1000)
        if remaining<100:raise SourcePending('source deadline')
        request=dict(request_id=str(uuid4()),correlation_id=str(uuid4()),operation_id=operation,
            arguments=arguments,timeout_ms=min(desc['execution_timeout_ms'],remaining),policy_id=desc['policy_id'],
            policy_version=desc['policy_version'],priority_class='normal')
        validate_read_request(request,metadata['profile'],max_result_bytes=metadata['limits']['max_result_bytes'])
        raw=canonical(request);require(len(raw)<=metadata['limits']['max_request_bytes'])
        return dict(request=request,binding=metadata['binding'],profile=metadata['profile'],limits=metadata['limits'],
            request_body_sha256=bound.digest(raw),attempted=False,result=None)

    def observe(self, record, save, deadline):
        """save先于POST；网络未知或重启只GET，原Host身份是唯一执行事实。"""
        request=record['request'];raw=canonical(request)
        require(bound.digest(raw)==record['request_body_sha256'])
        require(request['operation_id']in('market.history_1m','market.history_prepare')
            and bound.binding(record['binding'])==record['binding']
            and bound.digest(canonical(record['profile']))==record['binding']['capability_sha256'])
        validate_read_request(request,record['profile'],max_result_bytes=record['limits']['max_result_bytes'])
        if record['result']is not None:
            value=record['result']
        else:
            if not record['attempted']:
                record['attempted']=True;save()
                body=canonical(dict(schema_version=bound.SCHEMA,binding_sha256=bound.digest(canonical(record['binding'])),
                    request_body_b64=bound.b64(raw),request_body_sha256=bound.digest(raw)))
                code,value=self.exchange('POST','/internal/v1/bound-operations/'+request['operation_id'],body,deadline)
            else:
                code,value=self.exchange('GET','/internal/v1/bound-results/'+request['request_id'],b'',deadline)
            for unused in range(128):
                if code not in (200,202):raise SourcePending('original source request unresolved')
                bound.validate_response(value,max_result_bytes=record['limits']['max_result_bytes'],request=request)
                require(value['request_id']==request['request_id'] and value['operation_id']==request['operation_id']
                    and value['request_body_sha256']==record['request_body_sha256']
                    and value['admitted_binding']==record['binding'])
                if value['state']=='terminal':break
                if deadline-self.clock()<.02:raise SourcePending('original source request pending')
                time.sleep(.02)
                code,value=self.exchange('GET','/internal/v1/bound-results/'+request['request_id'],b'',deadline)
            else:raise SourcePending('original source request pending')
            record['result']=value;save()
        bound.validate_response(value,max_result_bytes=record['limits']['max_result_bytes'],request=request)
        require(value['request_body_sha256']==record['request_body_sha256'] and value['admitted_binding']==record['binding'])
        return decode(bound.unb64(value['result_body_b64'],record['limits']['max_result_bytes']))

    def prepare_arguments(self, symbol, start, end, metadata, deadline):
        scope=metadata['profile']['operation_profiles']['market.history_prepare']['limits']
        remaining=min(scope['total_timeout_ms'],int((deadline-self.clock())*1000))
        if remaining<100:raise SourcePending('source deadline')
        return dict(symbol=symbol,period='1m',start_time=start,end_time=end,
            clock_schema='qmt.win-uptime-ms.v1',deadline_ms=int(self.uptime.seconds()*1000)+remaining)
