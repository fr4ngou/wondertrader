"""线上策略观察只读HTTP；所有文件/本地副本IO由原App有界读池执行。"""
import asyncio
from time import monotonic

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse


def router():
    """只消费App生命周期登记的LiveStrategyPerformanceOwner，不创建运行角色。"""
    routes = APIRouter()
    path = '/v1/ui/live-strategy-performance'

    @routes.get(path)
    async def read(request: Request, strategy_id: str = Query(min_length=1,max_length=64),
                   strategy_version: str = Query(min_length=1,max_length=64),
                   limit: int = Query(default=90,ge=1,le=366)):
        if (set(request.query_params)-{'strategy_id','strategy_version','limit'}
                or any(len(request.query_params.getlist(k))!=1 for k in request.query_params)
                or request.headers.get('content-length','0')!='0' or request.headers.get('transfer-encoding')):
            raise HTTPException(422,'线上策略请求包含额外或重复参数')
        future = None
        deadline = monotonic()+2
        try:
            owner = request.app.state.live_strategy_performance
            future = request.app.state.reader.submit(lambda _remaining: owner.read(
                strategy_id,strategy_version,limit,deadline=deadline),deadline)
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            value = await asyncio.wait_for(asyncio.shield(wrapped),max(0,deadline-monotonic()))
            return JSONResponse(value,headers={'Cache-Control':'no-store'})
        except Exception:
            return JSONResponse({'detail':'线上策略观察暂不可用，请稍后重试'},status_code=503,
                                headers={'Cache-Control':'no-store'})
        finally:
            if future is not None: future.cancel()

    @routes.api_route(path,methods=['POST','PUT','PATCH','DELETE','HEAD','OPTIONS','TRACE','CONNECT'])
    async def read_only():
        return JSONResponse({'detail':'线上策略仅提供只读观察'},status_code=405,
                            headers={'Allow':'GET','Cache-Control':'no-store'})
    return routes
