"""终端外签名HTTP边界；受理、原结果查询与认证来源分别表达。"""
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response
from guanheng_qmt_shm_agent.errors import GatewayError
from .auth import HMACVerifier
from .runtime import error, HostRequest
from .trade_bound import HostTradeRequest


class _Capacity:
    """One event-loop owner; release after final send, disconnect or cancel."""
    def __init__(self, app, *, runtime):
        self.app,self.runtime,self.active=app,runtime,0

    async def __call__(self, scope, receive, send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        if self.runtime.shutdown_started or self.active>=self.runtime.max_http_inflight:
            value=error(503,'queue_full')
            reply=Response(value.content,status_code=value.status_code,media_type='application/json',
                headers={'Connection':'close'})
            return await reply(scope,receive,send)
        # No suspension between comparison and admission on the server loop.
        self.active+=1
        try:
            body=bytearray()
            async def receive_body():
                while True:
                    message=await receive()
                    if message['type']=='http.disconnect':
                        return 400
                    chunk=message.get('body',b'')
                    if len(body)+len(chunk)>self.runtime.max_frame:
                        return 413
                    body.extend(chunk)
                    if not message.get('more_body',False):
                        return None
            try:
                # One total receive window for every route, including health
                # and unknown paths. A chunk never resets the absolute limit.
                status=await asyncio.wait_for(receive_body(),self.runtime.budget.io_seconds)
            except asyncio.TimeoutError:
                status=408
            if status is not None:
                value=error(status,'request_timeout' if status==408 else 'invalid_arguments')
                reply=Response(value.content,status_code=status,media_type='application/json',
                    headers={'Connection':'close'})
                return await reply(scope,receive,send)
            original=bytes(body);del body
            delivered=False
            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered=True
                    return {'type':'http.request','body':original,'more_body':False}
                return await receive()
            return await self.app(scope,replay,send)
        finally:
            self.active-=1


def create_app(runtime, *, http_keys):
    runtime.require_http_credentials(http_keys)
    verifier=HMACVerifier(dict(http_keys))

    @asynccontextmanager
    async def lifespan(unused_app):
        try:
            await run_in_threadpool(runtime.start)
            yield
        finally:
            # shutdown窗口一经形成不逐层重启；超时runtime保留owner并报错。
            deadline=runtime.begin_shutdown()
            runtime.request_close()
            await run_in_threadpool(runtime.close,deadline)

    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(_Capacity,runtime=runtime)

    def render(value):
        return Response(value.content,status_code=value.status_code,media_type='application/json')

    @app.get('/health')
    def diagnostic():
        return runtime.health()

    @app.api_route('/internal/v1/{path:path}',methods=['GET','POST'])
    async def exchange(path: str, request: Request):
        raw=await request.body()  # Already bounded once by the ingress owner.
        try:
            target=request.scope['raw_path'].decode('ascii')
            if request.url.query:
                target+='?'+request.url.query
            verifier.verify(request.method,target,request.headers,raw)
        except GatewayError as exc:
            # 保留原认证拒绝/nonce重放/容量耗尽的状态和固定code，去敏正文。
            return render(error(exc.status_code,exc.code))
        except (ValueError,UnicodeError):
            return render(error(400,'invalid_arguments'))
        if request.url.query or (request.method=='GET' and raw):
            return render(error(400,'invalid_arguments'))
        try:
            trade_operation = None
            trade_id = None
            if request.method=='GET' and path=='trade-status':
                trade_operation='trade.status'
            elif request.method=='POST' and path=='trade-commands':
                trade_operation='trade.submit'
            elif request.method=='GET' and path.startswith('trade-commands/'):
                trade_operation='trade.result'
                trade_id=path[len('trade-commands/'):]
            elif request.method=='POST' and path=='trade-cancel-lookup':
                trade_operation='trade.cancel_lookup'
            elif request.method=='POST' and path=='trade-order-lookup':
                trade_operation='trade.lookup'
            elif request.method=='POST' and path=='trade-events':
                trade_operation='trade.events'
            if trade_operation is not None:
                if getattr(runtime,'trade_requests_enabled',False) is not True:
                    return render(error(503,'capability_unavailable'))
                message=HostTradeRequest(trade_operation,raw,command_id=trade_id)
            elif request.method=='GET' and path=='read-binding':
                message=HostRequest('binding.read')
            elif request.method=='POST' and path.startswith('bound-operations/'):
                request_type=HostRequest
                if getattr(runtime,'bulk_requests_enabled',False) is True:
                    from .bulk_runtime import BulkHostRequest
                    request_type=BulkHostRequest
                message=request_type('bound.submit',raw,operation_id=path[len('bound-operations/'):])
            elif request.method=='GET' and path.startswith('bound-results/'):
                message=HostRequest('bound.result',request_id=path[len('bound-results/'):])
            else:
                return render(error(503,'capability_unavailable'))
            value=await run_in_threadpool(runtime.request,message)
        except (ValueError,TypeError):
            value=error(400,'invalid_arguments')
        return render(value)

    return app
