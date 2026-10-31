"""采集HTTP实例的原始网络截止与有界正文解码；普通读取不导入HTTP依赖。"""
import time
import os
import ssl
import socket
import select
import zlib
from .source_fetch import SourceFailure


class SocketStream:
    """单socket IO；sendall使用Python的整次发送时限，部分写入不会重新计时。"""
    def __init__(self,connection):self.connection=connection

    def read(self,size,timeout=None):
        import httpcore
        self.connection.settimeout(timeout)
        try:return self.connection.recv(size)
        except socket.timeout:raise httpcore.ReadTimeout('source read timeout') from None
        except OSError:raise httpcore.ReadError('source read failed') from None

    def write(self,body,timeout=None):
        import httpcore
        self.connection.settimeout(timeout)
        try:self.connection.sendall(body)
        except socket.timeout:raise httpcore.WriteTimeout('source write timeout') from None
        except OSError:raise httpcore.WriteError('source write failed') from None

    def get_extra_info(self,info):
        if info=='socket':return self.connection
        if info=='client_addr':return self.connection.getsockname()
        if info=='server_addr':return self.connection.getpeername()
        if info=='is_readable':
            return self.connection.fileno()<0 or bool(select.select([self.connection],[],[],0)[0])
        return None

    def close(self):self.connection.close()


class DeadlineStream:
    """池内连接每次读取当前请求D，复用连接不携带上次请求的截止。"""
    def __init__(self,stream,remaining):
        self.stream,self.remaining=stream,remaining

    def _timeout(self,timeout):
        remaining=self.remaining()
        return remaining if timeout is None else min(timeout,remaining)

    def read(self,max_bytes,timeout=None):
        import httpcore
        try:value=self.stream.read(min(max_bytes,65536),timeout=self._timeout(timeout))
        except httpcore.TimeoutException:
            self.remaining(timed_out=True)
        self.remaining()
        return value

    def write(self,buffer,timeout=None):
        import httpcore
        # GET请求由HTTPX装配；有界块交回原stream，块间复核本次截止。
        for offset in range(0,len(buffer),65536):
            try:self.stream.write(buffer[offset:offset+65536],timeout=self._timeout(timeout))
            except httpcore.TimeoutException:
                self.remaining(timed_out=True)
            self.remaining()

    def start_tls(self,ssl_context,server_hostname=None,timeout=None):
        try:return DeadlineTLSStream(self,ssl_context,server_hostname)
        except BaseException:
            self.close();raise

    def get_extra_info(self,info):return self.stream.get_extra_info(info)

    def close(self):
        # 关闭始终委托原owner，截止/停止不会拦截资源释放。
        self.stream.close()


class DeadlineTLSStream:
    """TLS与代理内TLS共用同一个有界原始stream，握手/空TLS记录也逐读核D。"""
    def __init__(self,stream,context,server_hostname):
        import httpcore
        self.stream=stream;self.remaining=stream.remaining
        self.incoming,self.outgoing=ssl.MemoryBIO(),ssl.MemoryBIO()
        self.tls=context.wrap_bio(self.incoming,self.outgoing,server_hostname=server_hostname)
        try:self._io(self.tls.do_handshake)
        except OSError:raise httpcore.ConnectError('source TLS connection failed') from None

    def _io(self,operation):
        while True:
            self.remaining();want_read=False;waiting=False;value=None
            try:value=operation()
            except ssl.SSLWantReadError:want_read=True;waiting=True
            except ssl.SSLWantWriteError:waiting=True
            while self.outgoing.pending:
                self.stream.write(self.outgoing.read(16384))
            if want_read:
                raw=self.stream.read(16384)
                if raw:self.incoming.write(raw)
                else:self.incoming.write_eof()
            if not waiting:
                self.remaining();return value

    def read(self,max_bytes,timeout=None):
        import httpcore
        try:return self._io(lambda:self.tls.read(min(max_bytes,65536)))
        except OSError:raise httpcore.ReadError('source TLS read failed') from None

    def write(self,buffer,timeout=None):
        import httpcore
        try:
            pending=memoryview(buffer)
            while pending:
                sent=self._io(lambda:self.tls.write(pending[:16384]));pending=pending[sent:]
        except OSError:raise httpcore.WriteError('source TLS write failed') from None

    def start_tls(self,ssl_context,server_hostname=None,timeout=None):
        try:return DeadlineTLSStream(self,ssl_context,server_hostname)
        except BaseException:
            self.close();raise

    def get_extra_info(self,info):
        return self.tls if info=='ssl_object' else self.stream.get_extra_info(info)

    def close(self):self.stream.close()


class DeadlineBackend:
    def __init__(self,backend,remaining):self.backend,self.remaining=backend,remaining

    def _connect(self,method,timeout,**kwargs):
        import httpcore
        remaining=self.remaining()
        try:stream=method(timeout=remaining if timeout is None else min(timeout,remaining),**kwargs)
        except httpcore.TimeoutException:
            self.remaining(timed_out=True)
        try:self.remaining()
        except BaseException:
            stream.close();raise
        return DeadlineStream(stream,self.remaining)

    def connect_tcp(self,host,port,timeout=None,local_address=None,socket_options=None):
        import httpcore
        self.remaining()
        try:addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
        except OSError:
            self.remaining();raise httpcore.ConnectError('source resolution failed') from None
        # DNS不可协作时归父Job；返回后每个地址尝试重新取原D剩余量。
        for family,kind,protocol,_,address in addresses:
            remaining=self.remaining();connection=socket.socket(family,kind,protocol)
            try:
                connection.settimeout(remaining if timeout is None else min(timeout,remaining))
                if local_address is not None:connection.bind((local_address,0))
                for option in socket_options or ():connection.setsockopt(*option)
                connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                connection.connect(address);self.remaining()
                return DeadlineStream(SocketStream(connection),self.remaining)
            except socket.timeout:
                connection.close();self.remaining(timed_out=True)
            except OSError:connection.close();self.remaining()
            except BaseException:
                connection.close();raise
        raise httpcore.ConnectError('source connection failed')

    def connect_unix_socket(self,path,timeout=None,socket_options=None):
        return self._connect(self.backend.connect_unix_socket,timeout,path=path,socket_options=socket_options)

    def sleep(self,seconds):
        if seconds>=self.remaining():self.remaining(timed_out=True)
        time.sleep(seconds);self.remaining()


def owned_client(remaining):
    """保留HTTPX环境代理/NO_PROXY、证书及TLS；只替换本实例池的网络接缝。

    接缝绑定lock中的HTTPX0.28.1/httpcore1.0.9；升级须重验代理、池复用、
    TLS及关闭。无全局修改、后台超时线程或另一客户端/连接所有者。
    """
    import httpx
    # 显式证书配置沿HTTPX；默认使用操作系统可信根，Windows保留系统CA链。
    verify=True if os.environ.get('SSL_CERT_FILE') or os.environ.get('SSL_CERT_DIR') else ssl.create_default_context()
    client=httpx.Client(follow_redirects=False,verify=verify,
        headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'gzip, deflate'})
    try:
        transports={client._transport,*[value for value in client._mounts.values() if value is not None]}
        for transport in transports:
            pool=transport._pool
            pool._network_backend=DeadlineBackend(pool._network_backend,remaining)
    except BaseException:
        client.close();raise
    return client


def decode_body(raw,content_encoding,budget,remaining):
    """线上原件保存后解码；每层分配前限制输出，原D覆盖空输出和所有压缩层。"""
    encodings=[value.strip().lower() for value in (content_encoding or 'identity').split(',')]
    if len(encodings)>4 or any(value not in ('identity','gzip','deflate') for value in encodings):
        raise SourceFailure('source_response_encoding')
    body=raw
    for encoding in reversed(encodings):
        remaining()
        if encoding=='identity':continue
        if encoding=='gzip':bits=zlib.MAX_WBITS|16
        else:
            # deflate兼容RFC1950封装及已有裸RFC1951来源；按两字节头一次决定。
            wrapped=len(body)>=2 and body[0]&15==8 and body[0]>>4<=7 and (body[0]*256+body[1])%31==0
            bits=zlib.MAX_WBITS if wrapped else -zlib.MAX_WBITS
        decoder=zlib.decompressobj(bits);output=bytearray()
        try:
            for offset in range(0,len(body),65536):
                pending=body[offset:offset+65536]
                while pending:
                    remaining()
                    if decoder.eof:
                        if encoding!='gzip':raise SourceFailure('source_response_encoding')
                        decoder=zlib.decompressobj(bits)
                    chunk=decoder.decompress(pending,min(65536,budget.response_bytes-len(output)+1,
                        budget.max_bytes-budget.decoded_bytes+1))
                    if len(output)+len(chunk)>budget.response_bytes:
                        raise SourceFailure('response_decode_budget_exceeded')
                    budget.expand(len(chunk));output.extend(chunk)
                    pending=decoder.unused_data if decoder.eof else decoder.unconsumed_tail
            if not decoder.eof:raise SourceFailure('source_response_encoding')
        except zlib.error:raise SourceFailure('source_response_encoding') from None
        body=bytes(output)
    remaining()
    return body
