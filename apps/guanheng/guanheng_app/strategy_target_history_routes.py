"""策略原生目标历史HTTP；沿App原有有界读池，不创建新工作线程。"""
import asyncio
from time import monotonic
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from .strategy_target_history import read_target_history, TargetHistoryChanged, _cursor


def router(settings):
    routes = APIRouter()
    path = '/v1/ui/strategy-target-history'

    @routes.get(path)
    async def read(request: Request, strategy_id: str = Query(min_length=1, max_length=64),
                   strategy_version: str = Query(min_length=1, max_length=64),
                   limit: int = Query(default=20, ge=1, le=100), cursor: str | None = Query(default=None, max_length=512)):
        if (set(request.query_params)-{'strategy_id', 'strategy_version', 'limit', 'cursor'}
                or any(len(request.query_params.getlist(k)) != 1 for k in request.query_params)
                or request.headers.get('content-length', '0') != '0' or request.headers.get('transfer-encoding')):
            raise HTTPException(422, '目标记录请求包含额外或重复参数')
        try:
            _cursor(cursor)
        except Exception:
            raise HTTPException(422, '目标记录分页身份无效，请重新读取最新记录') from None
        future, deadline = None, monotonic()+2
        try:
            future = request.app.state.reader.submit(lambda _remaining: read_target_history(
                settings, strategy_id, strategy_version, limit, cursor, deadline=deadline), deadline)
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            value = await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline-monotonic()))
            return JSONResponse(value, headers={'Cache-Control':'no-store'})
        except TargetHistoryChanged:
            return JSONResponse({'detail':'目标日志已更新或替换，请刷新后从最新记录查看'}, status_code=409, headers={'Cache-Control':'no-store'})
        except Exception:
            return JSONResponse({'detail':'目标仓位记录暂时无法读取，请稍后重新读取'}, status_code=503, headers={'Cache-Control':'no-store'})
        finally:
            if future is not None: future.cancel()

    @routes.api_route(path, methods=['POST','PUT','PATCH','DELETE','HEAD','OPTIONS','TRACE','CONNECT'])
    async def readonly():
        return JSONResponse({'detail':'目标仓位记录仅提供只读查询'}, status_code=405,
            headers={'Allow':'GET','Cache-Control':'no-store'})
    return routes
