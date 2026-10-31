"""回测HTTP只承接值与owner投影，报告读取走应用有界worker。"""

import asyncio

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse

from .backtest_workspace import WorkspaceError
from .reading import ReadCapacityError
from .ui_origin import require_ui_origin
from .strategy_host import _json
from time import monotonic


def router():
    routes = APIRouter(prefix="/v1/ui/backtest")

    def allowed_query(request, keys=()):
        if set(request.query_params) - set(keys) or any(
            len(request.query_params.getlist(k)) != 1
            for k in keys
            if k in request.query_params
        ):
            raise HTTPException(422, "回测请求包含额外或重复参数")

    def owner(request):
        return request.app.state.backtest_workspace

    async def command(request):
        allowed_query(request)
        require_ui_origin(request, "回测操作只接受当前应用同源请求")
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            raise HTTPException(415, "回测操作需要JSON请求")

        async def read():
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 1024:
                    raise HTTPException(413, "回测请求超过容量")
            return bytes(raw)

        try:
            raw = await asyncio.wait_for(read(), 2)
            value = _json(raw, 1024, monotonic() + 1)
            if type(value) is not dict or set(value) != {"owner_id", "request_id"}:
                raise ValueError()
            return value
        except HTTPException:
            raise
        except (Exception, SystemExit):
            raise HTTPException(422, "回测请求格式无效") from None

    @routes.get("/workspace")
    async def workspace(request: Request):
        allowed_query(request)
        return owner(request).overview()

    @routes.post("/runs", status_code=202)
    async def start(request: Request):
        value = await command(request)
        return owner(request).start(**value)

    @routes.get("/runs/{request_id}")
    async def status(
        request: Request,
        request_id: str,
        owner_id: str = Query(pattern=r"^[a-f0-9]{32}$"),
    ):
        allowed_query(request, ("owner_id",))
        return owner(request).status(owner_id, request_id)

    @routes.post("/runs/{request_id}/cancel")
    async def cancel(request: Request, request_id: str):
        value = await command(request)
        if value["request_id"] != request_id:
            raise HTTPException(422, "取消请求身份不匹配")
        return owner(request).cancel(**value)

    async def read_value(request, operation):
        deadline = monotonic() + 5
        try:
            future = request.app.state.backtest_reader.submit(
                lambda _budget: operation(deadline),
                deadline,
            )
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(
                lambda done: None if done.cancelled() else done.exception()
            )
            try:
                return await asyncio.wait_for(
                    asyncio.shield(wrapped), max(0, deadline - monotonic())
                )
            finally:
                future.cancel()
        except (ReadCapacityError, TimeoutError):
            raise HTTPException(503, "回测报告读取繁忙或超时，请稍后重试") from None

    async def read_report(request, owner_id, request_id, **selection):
        return await read_value(request, lambda deadline: owner(request).report(
            owner_id, request_id, deadline=deadline, **selection))

    async def readonly_input(request, keys):
        allowed_query(request, keys)
        # 只读指标不接受隐藏的正文输入；流式检查在首个非空块即拒绝。
        try:
            async def empty():
                async for chunk in request.stream():
                    if chunk:
                        raise HTTPException(422, "回测报告只接受查询参数")
            await asyncio.wait_for(empty(), 1)
        except TimeoutError:
            raise HTTPException(422, "回测报告请求正文读取超时") from None

    @routes.get("/comparison")
    async def comparison(request: Request,
                         left_run_id: str = Query(pattern=r"^[a-f0-9]{32}$"),
                         left_receipt_sha256: str = Query(pattern=r"^[a-f0-9]{64}$"),
                         right_run_id: str = Query(pattern=r"^[a-f0-9]{32}$"),
                         right_receipt_sha256: str = Query(pattern=r"^[a-f0-9]{64}$")):
        await readonly_input(request, ("left_run_id", "left_receipt_sha256", "right_run_id", "right_receipt_sha256"))
        if left_run_id == right_run_id:
            raise HTTPException(422, "请选择两份不同运行的报告")
        value = await read_value(request, lambda deadline: owner(request).comparison(
            left_run_id, left_receipt_sha256, right_run_id, right_receipt_sha256, deadline=deadline))
        return JSONResponse(content=value, headers={"Cache-Control": "no-store"})

    @routes.get("/archive/{run_id}/performance")
    async def performance(request: Request, run_id: str = Path(pattern=r"^[a-f0-9]{32}$"),
                          receipt_sha256: str = Query(pattern=r"^[a-f0-9]{64}$")):
        await readonly_input(request, ("receipt_sha256",))
        value = await read_value(request, lambda deadline: owner(request).archive(
            deadline=deadline, run_id=run_id, receipt_sha=receipt_sha256, performance=True))
        return JSONResponse(content=value, headers={"Cache-Control": "no-store"})

    @routes.post("/runs/{request_id}/archive")
    async def retry_archive(request: Request, request_id: str):
        value = await command(request)
        if value["request_id"] != request_id:
            raise HTTPException(422, "归档请求身份不匹配")
        return await read_value(request, lambda deadline: owner(request).retry_archive(
            **value, deadline=deadline))

    @routes.get("/archive")
    async def archive_index(request: Request):
        allowed_query(request)
        return await read_value(request, lambda deadline: owner(request).archive(deadline=deadline))

    @routes.get("/archive/{run_id}")
    async def archive_configuration(request: Request, run_id: str,
                                    receipt_sha256: str = Query(pattern=r"^[a-f0-9]{64}$")):
        allowed_query(request, ("receipt_sha256",))
        return await read_value(request, lambda deadline: owner(request).archive(
            deadline=deadline, run_id=run_id, receipt_sha=receipt_sha256, configuration=True))

    @routes.get("/archive/{run_id}/records")
    async def archive_records(request: Request, run_id: str,
                              receipt_sha256: str = Query(pattern=r"^[a-f0-9]{64}$"),
                              offset: int = Query(default=0, ge=0, le=4096),
                              limit: int = Query(default=50, ge=1, le=50)):
        allowed_query(request, ("receipt_sha256", "offset", "limit"))
        return await read_value(request, lambda deadline: owner(request).archive(
            deadline=deadline, run_id=run_id, receipt_sha=receipt_sha256, offset=offset, limit=limit))

    @routes.get("/archive/{run_id}/records/{index}")
    async def archive_record(request: Request, run_id: str, index: int,
                             receipt_sha256: str = Query(pattern=r"^[a-f0-9]{64}$")):
        allowed_query(request, ("receipt_sha256",))
        return await read_value(request, lambda deadline: owner(request).archive(
            deadline=deadline, run_id=run_id, receipt_sha=receipt_sha256, index=index))

    @routes.get("/runs/{request_id}/records")
    async def records(
        request: Request,
        request_id: str,
        owner_id: str = Query(pattern=r"^[a-f0-9]{32}$"),
        offset: int = Query(default=0, ge=0, le=4096),
        limit: int = Query(default=50, ge=1, le=50),
    ):
        allowed_query(request, ("owner_id", "offset", "limit"))
        return await read_report(
            request, owner_id, request_id, offset=offset, limit=limit
        )

    @routes.get("/runs/{request_id}/records/{index}")
    async def record(
        request: Request,
        request_id: str,
        index: int,
        owner_id: str = Query(pattern=r"^[a-f0-9]{32}$"),
    ):
        allowed_query(request, ("owner_id",))
        return await read_report(request, owner_id, request_id, index=index)

    return routes


async def workspace_error(_request, exception: WorkspaceError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=exception.code, content={"detail": str(exception)})
