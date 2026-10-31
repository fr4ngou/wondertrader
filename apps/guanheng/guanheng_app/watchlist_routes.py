"""个人观察HTTP只承接协议值；实际文件和关闭均由应用owner拥有。"""

import asyncio
from time import monotonic

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .contracts.watchlist import MAX_REQUEST_BYTES, MAX_STATE_BYTES, decode_replacement
from .reading import ReadCapacityError
from .ui_origin import require_ui_origin
from .watchlist import UNAVAILABLE, UNKNOWN, WatchlistError


REQUEST_SECONDS = 2.0
_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "TRACE", "CONNECT"]


def _check(deadline, *, writing=False):
    if monotonic() >= deadline:
        raise WatchlistError(UNKNOWN if writing else UNAVAILABLE)


def _query(request):
    if request.query_params:
        raise HTTPException(422, "个人观察不接受额外查询参数")


async def _body(request, deadline, *, writing):
    _check(deadline, writing=writing)
    _query(request)
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1:
        raise HTTPException(422, "个人观察请求正文长度无效")
    if not writing and (request.headers.get("content-length", "0") != "0"
                        or request.headers.get("transfer-encoding") is not None):
        raise HTTPException(422, "个人观察读取不接受请求正文")
    if writing:
        require_ui_origin(request, "个人观察保存只接受当前应用同源请求")
        content_types = request.headers.getlist("content-type")
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, "个人观察保存需要JSON请求")
        if lengths:
            if not lengths[0].isascii() or not lengths[0].isdigit():
                raise HTTPException(422, "个人观察请求正文长度无效")
            # 先限制数字长度，避免对任意长十进制做转换。
            if len(lengths[0]) > 10 or int(lengths[0]) > MAX_REQUEST_BYTES:
                raise HTTPException(413, "个人观察请求超过容量")
    limit = MAX_REQUEST_BYTES if writing else 0

    async def consume():
        raw = bytearray()
        async for chunk in request.stream():
            _check(deadline, writing=writing)
            if len(chunk) > limit - len(raw):
                raise HTTPException(413 if writing else 422, "个人观察请求正文超过允许范围")
            raw.extend(chunk)
        _check(deadline, writing=writing)
        return bytes(raw)

    try:
        raw = await asyncio.wait_for(consume(), max(0, deadline - monotonic()))
    except TimeoutError:
        raise WatchlistError(UNAVAILABLE) from None
    _check(deadline, writing=writing)
    return raw


async def _disconnect(request):
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return


async def _submit(request, operation, deadline, *, writing):
    _check(deadline, writing=writing)
    try:
        future = request.app.state.reader.submit(lambda _remaining: operation(deadline), deadline)
    except ReadCapacityError:
        raise WatchlistError(UNAVAILABLE) from None
    disconnected = None
    try:
        wrapped = asyncio.wrap_future(future)
        wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        coroutine = _disconnect(request)
        try:
            disconnected = asyncio.create_task(coroutine)
        except BaseException:
            coroutine.close()
            raise
        _check(deadline, writing=writing)
        complete, _pending = await asyncio.wait((wrapped, disconnected),
                                               timeout=max(0, deadline - monotonic()),
                                               return_when=asyncio.FIRST_COMPLETED)
        if wrapped in complete:
            raw = await wrapped
            _check(deadline, writing=writing)
            if type(raw) is not bytes or len(raw) > MAX_STATE_BYTES:
                raise WatchlistError(UNKNOWN if writing else UNAVAILABLE)
            response = Response(raw, media_type="application/json", headers={"Cache-Control": "no-store"})
            _check(deadline, writing=writing)
            return response
        if disconnected in complete:
            raise HTTPException(499, "个人观察连接已关闭，请重新读取核实")
        raise WatchlistError(UNKNOWN if writing else UNAVAILABLE)
    finally:
        # cancel只撤销尚未运行的队列项，实际worker仍持有原owner直至结束。
        future.cancel()
        if disconnected is not None:
            if not disconnected.done():
                disconnected.cancel()
            await asyncio.gather(disconnected, return_exceptions=True)


def router():
    routes = APIRouter(prefix="/v1/ui/watchlists")

    @routes.get("/default")
    async def read_default(request: Request):
        deadline = monotonic() + REQUEST_SECONDS
        await _body(request, deadline, writing=False)
        owner = getattr(request.app.state, "watchlist_owner", None)
        if owner is None:
            raise WatchlistError()
        return await _submit(request, owner.read, deadline, writing=False)

    @routes.put("/default")
    async def replace_default(request: Request):
        deadline = monotonic() + REQUEST_SECONDS
        raw = await _body(request, deadline, writing=True)
        _check(deadline, writing=True)
        try:
            replacement = decode_replacement(raw)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise HTTPException(422, "个人观察保存请求格式无效") from None
        _check(deadline, writing=True)
        owner = getattr(request.app.state, "watchlist_owner", None)
        if owner is None:
            raise WatchlistError()
        return await _submit(request, lambda total_deadline: owner.replace(replacement, total_deadline),
                             deadline, writing=True)

    @routes.api_route("/default", methods=[item for item in _METHODS if item not in ("GET", "PUT")])
    async def unsupported_method():
        raise HTTPException(405, "个人观察默认列表只支持GET和PUT", headers={"Allow": "GET, PUT"})

    @routes.api_route("", methods=_METHODS)
    @routes.api_route("/{path:path}", methods=_METHODS)
    async def unsupported_list(path: str = ""):
        raise HTTPException(404, "当前仅支持默认个人观察列表")

    return routes


async def watchlist_error(_request, exception: WatchlistError):
    return JSONResponse(status_code=exception.code, content={"detail": str(exception)},
                        headers={"Cache-Control": "no-store"})
