"""WT已发布回测归档的只读装配；运行和保存仍由WT原owner负责。"""
import asyncio
from pathlib import Path
from time import monotonic

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .backtest_archive import BacktestArchive, ArchiveError
from .reading import ReadCapacityError

# 排队、原件核验及两份报告比较共用一次截止，不按子步骤重新计时。
REQUEST_SECONDS = 30


def router(root):
    """原归档完整校验及有界读取；本入口没有运行、取消或归档写方法。"""
    archive = BacktestArchive(root) if root else None
    routes = APIRouter(prefix='/v1/ui/backtest')

    async def read(request, operation, keys=()):
        if (set(request.query_params) - set(keys) or any(len(request.query_params.getlist(k)) != 1
                for k in request.query_params) or request.headers.get('content-length', '0') != '0'
                or request.headers.get('transfer-encoding')):
            raise HTTPException(422, '历史报告只接受声明的查询参数')
        if archive is None:
            raise HTTPException(503, '尚未配置WT已保存的回测报告')
        deadline, future = monotonic() + REQUEST_SECONDS, None
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

    @routes.get('/archive-summaries')
    async def summaries(request: Request):
        """轻量原件归属目录；完整报告与绩效仍沿用户选中的原读取入口。"""
        return await read(request, lambda deadline: archive.list(deadline, summaries=True))

    @routes.get('/source')
    async def source(request: Request):
        """目录状态与读取故障分别表达；持久归档在WT停止后仍保持可读。"""
        if request.query_params or request.headers.get('content-length', '0') != '0' or request.headers.get('transfer-encoding'):
            raise HTTPException(422, '报告来源状态不接受额外参数')
        def body(state, reason, index=None):
            return JSONResponse(dict(schema_version='guanheng.backtest-source.v1', read_only=True,
                state=state, reason=reason, persistent=True, index=index), headers={'Cache-Control':'no-store'})
        if archive is None:
            return body('unconfigured', '尚未配置WT回测归档目录，请由维护人员连接已有正式归档。')
        def inspect(deadline):
            path = Path(root)
            if not path.is_absolute() or not path.is_dir():
                return 'invalid_path', '配置的回测归档目录不存在或路径类型错误，请核对读取配置。', None
            try:
                value = archive.list(deadline)
            except ArchiveError:
                return 'invalid_archive', '归档目录读取或格式校验失败，请保留原目录并核对访问权限、原件和完成证明。', None
            state = 'available' if value['runs'] else 'invalid_archive' if value['invalid_receipts'] else 'empty'
            reason = {'available':'已连接WT保存的回测归档；WT停止后仍可读取原报告。',
                'invalid_archive':'已有回测完成证明未通过校验，请核对原件和格式。',
                'empty':'已连接归档目录，当前没有已保存的正式回测报告。'}[state]
            if state == 'empty' and value['unarchived_runs']:
                reason = '目录中存在尚未发布完成证明的运行，当前没有可读取的正式归档。'
            return state, reason, value
        deadline, future = monotonic() + REQUEST_SECONDS, None
        try:
            future = request.app.state.backtest_reader.submit(lambda _remaining: inspect(deadline), deadline)
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            return body(*await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline-monotonic())))
        except (ReadCapacityError, TimeoutError):
            raise HTTPException(503, '报告来源状态读取繁忙或超时，请重新读取') from None
        finally:
            if future is not None:
                future.cancel()

    @routes.get('/comparison')
    async def comparison(request: Request,
        left_run_id: str = Query(pattern=r'^[a-f0-9]{32}$'), left_receipt_sha256: str = Query(pattern=r'^[a-f0-9]{64}$'),
        right_run_id: str = Query(pattern=r'^[a-f0-9]{32}$'), right_receipt_sha256: str = Query(pattern=r'^[a-f0-9]{64}$')):
        if left_run_id == right_run_id:
            raise HTTPException(422, '请选择两份不同运行的报告')
        return await read(request, lambda deadline: archive.compare(left_run_id, left_receipt_sha256,
            right_run_id, right_receipt_sha256, deadline), ('left_run_id','left_receipt_sha256','right_run_id','right_receipt_sha256'))

    @routes.get('/archive/{run_id}/visuals')
    async def visuals(request: Request, run_id: str, receipt_sha256: str = Query(pattern=r'^[a-f0-9]{64}$')):
        return await read(request, lambda deadline: archive.visual(run_id, receipt_sha256, deadline), ('receipt_sha256',))

    @routes.get('/archive/{run_id}/ledger')
    async def ledger(request: Request, run_id: str, receipt_sha256: str = Query(pattern=r'^[a-f0-9]{64}$'),
                     day: int | None = Query(default=None, ge=19000101, le=29991231),
                     offset: int = Query(default=0, ge=0, le=65536), limit: int = Query(default=50, ge=1, le=50)):
        return await read(request, lambda deadline: archive.visual(run_id, receipt_sha256, deadline,
            ledger=True, day=day, offset=offset, limit=limit), ('receipt_sha256', 'day', 'offset', 'limit'))

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
