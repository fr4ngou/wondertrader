"""WT已发布回测归档的只读装配；运行和保存仍由WT原owner负责。"""
import asyncio
from time import monotonic

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .backtest_archive import BacktestArchive, ArchiveError
from .reading import ReadCapacityError


def router(root):
    """原归档完整校验和5秒总截止保持；本入口没有运行、取消或归档写方法。"""
    archive = BacktestArchive(root) if root else None
    routes = APIRouter(prefix='/v1/ui/backtest')

    async def read(request, operation, keys=()):
        if (set(request.query_params) - set(keys) or any(len(request.query_params.getlist(k)) != 1
                for k in request.query_params) or request.headers.get('content-length', '0') != '0'
                or request.headers.get('transfer-encoding')):
            raise HTTPException(422, '历史报告只接受声明的查询参数')
        if archive is None:
            raise HTTPException(503, '尚未配置WT已保存的回测报告')
        deadline, future = monotonic() + 5, None
        try:
            future = request.app.state.backtest_reader.submit(lambda _remaining: operation(deadline), deadline)
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            return JSONResponse(content=await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline-monotonic())),
                                headers={'Cache-Control': 'no-store'})
        except ArchiveError as error:
            raise HTTPException(error.code, str(error)) from None
        except (ReadCapacityError, TimeoutError):
            raise HTTPException(503, '历史报告读取繁忙或超时，请重新读取') from None
        finally:
            if future is not None:
                future.cancel()

    @routes.get('/archive')
    async def index(request: Request):
        return await read(request, lambda deadline: archive.list(deadline))

    @routes.get('/comparison')
    async def comparison(request: Request,
        left_run_id: str = Query(pattern=r'^[a-f0-9]{32}$'), left_receipt_sha256: str = Query(pattern=r'^[a-f0-9]{64}$'),
        right_run_id: str = Query(pattern=r'^[a-f0-9]{32}$'), right_receipt_sha256: str = Query(pattern=r'^[a-f0-9]{64}$')):
        if left_run_id == right_run_id:
            raise HTTPException(422, '请选择两份不同运行的报告')
        return await read(request, lambda deadline: archive.compare(left_run_id, left_receipt_sha256,
            right_run_id, right_receipt_sha256, deadline), ('left_run_id','left_receipt_sha256','right_run_id','right_receipt_sha256'))

    @routes.get('/archive/{run_id}')
    @routes.get('/archive/{run_id}/{selection}')
    @routes.get('/archive/{run_id}/records/{index}')
    async def report(request: Request, run_id: str, receipt_sha256: str = Query(pattern=r'^[a-f0-9]{64}$'),
                     selection: str | None = None, index: int | None = None,
                     offset: int = Query(default=0, ge=0, le=4096), limit: int = Query(default=50, ge=1, le=50)):
        if selection not in (None, 'performance', 'records'):
            raise HTTPException(404, '未知报告内容')
        keys = ('receipt_sha256', 'offset', 'limit') if selection == 'records' and index is None else ('receipt_sha256',)
        return await read(request, lambda deadline: archive.read(run_id, receipt_sha256, deadline,
            configuration=selection is None and index is None, performance=selection=='performance',
            index=index, offset=offset, limit=limit), keys)

    @routes.api_route('/{path:path}', methods=['POST','PUT','PATCH','DELETE','HEAD','OPTIONS','TRACE','CONNECT'])
    async def read_only(path: str):
        return JSONResponse({'detail': '回测运行、取消和保存由WT入口负责；观衡仅查询已发布报告'},
                            status_code=405, headers={'Allow': 'GET', 'Cache-Control': 'no-store'})
    return routes
