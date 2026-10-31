"""原执行owner的只读业务投影；不触发策略、券商或订单查询。"""
import asyncio
from time import monotonic

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .operations import utc_now


def router(*, invalid=False):
    routes = APIRouter()
    path = '/v1/ui/strategy-runtime'

    @routes.get(path)
    async def read(request: Request):
        if (request.query_params or request.headers.get('content-length', '0') != '0'
                or request.headers.get('transfer-encoding')):
            raise HTTPException(422, '策略运行结果不接受额外参数')
        app, future = request.app, None
        deadline = monotonic() + 2
        try:
            if invalid or app.state.execution_start_error:
                raise ValueError('execution unavailable')
            owner = app.state.execution_process
            observer = getattr(owner, 'observe_strategy', None)
            if observer is None:
                value = dict(state='unconfigured', strategy=None)
            else:
                future = app.state.reader.submit(lambda _remaining: observer(deadline), deadline)
                wrapped = asyncio.wrap_future(future)
                wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
                value = await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline-monotonic()))
            return JSONResponse(headers={'Cache-Control': 'no-store'}, content=dict(
                schema_version='guanheng.strategy-runtime.v1', read_only=True, observed_at=utc_now(), **value))
        except Exception:
            return JSONResponse({'detail': '策略运行结果暂时无法更新，请稍后重新读取'}, status_code=503,
                                headers={'Cache-Control': 'no-store'})
        finally:
            if future is not None:
                future.cancel()

    @routes.api_route(path, methods=['POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'])
    async def read_only():
        return JSONResponse({'detail': '策略运行结果仅提供只读查询'}, status_code=405,
                            headers={'Allow': 'GET', 'Cache-Control': 'no-store'})
    return routes
