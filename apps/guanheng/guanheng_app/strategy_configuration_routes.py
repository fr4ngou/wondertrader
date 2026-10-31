"""策略配置HTTP只承接值，文件操作归当前owner和应用已有有界读池。"""

import asyncio
from time import monotonic

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .contracts.strategy_configuration import (
    ConfigurationValueError, MAX_REQUEST_BYTES, MAX_STATE_BYTES, VALIDATE_SCHEMA, decode, keys,
)
from .reading import ReadCapacityError
from .strategy_configuration import StrategyConfigurationError, UNAVAILABLE, UNKNOWN
from .ui_origin import require_ui_origin

REQUEST_SECONDS = 2.0


async def _body(request, deadline, *, writing, query=()):
    if set(request.query_params) - set(query) or any(len(request.query_params.getlist(k)) != 1 for k in query):
        raise HTTPException(422, "策略配置请求参数无效")
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1:
        raise HTTPException(422, "策略配置请求长度无效")
    if writing:
        require_ui_origin(request, "策略配置写入只接受当前应用同源请求")
        types = request.headers.getlist("content-type")
        if len(types) != 1 or types[0].split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, "策略配置写入需要JSON请求")
        if lengths and (not lengths[0].isascii() or not lengths[0].isdigit()):
            raise HTTPException(422, "策略配置请求长度无效")
        if lengths and (len(lengths[0]) > 10 or int(lengths[0]) > MAX_REQUEST_BYTES):
            raise HTTPException(413, "策略配置请求超过容量")
    elif request.headers.get("content-length", "0") != "0" or request.headers.get("transfer-encoding"):
        raise HTTPException(422, "策略配置读取不接受请求正文")
    limit = MAX_REQUEST_BYTES if writing else 0

    async def consume():
        raw = bytearray()
        async for chunk in request.stream():
            if monotonic() >= deadline:
                raise TimeoutError()
            if len(chunk) > limit - len(raw):
                raise HTTPException(413 if writing else 422, "策略配置请求超过容量")
            raw.extend(chunk)
        return bytes(raw)

    try:
        raw = await asyncio.wait_for(consume(), max(0, deadline - monotonic()))
        if monotonic() >= deadline:
            raise TimeoutError()
        return decode(raw) if writing else None
    except TimeoutError:
        raise StrategyConfigurationError(UNAVAILABLE) from None
    except ConfigurationValueError:
        raise HTTPException(422, "策略配置JSON格式无效") from None


async def _disconnect(request):
    while True:
        if (await request.receive())["type"] == "http.disconnect":
            return


async def _submit(request, operation, deadline, *, saving=False):
    try:
        future = request.app.state.reader.submit(lambda _remaining: operation(deadline), deadline)
    except ReadCapacityError:
        raise StrategyConfigurationError(UNAVAILABLE) from None
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
        completed, _pending = await asyncio.wait((wrapped, disconnected), timeout=max(0, deadline - monotonic()),
                                                return_when=asyncio.FIRST_COMPLETED)
        if wrapped in completed:
            raw = await wrapped
            if monotonic() >= deadline or type(raw) is not bytes or len(raw) > MAX_STATE_BYTES:
                raise StrategyConfigurationError(UNKNOWN if saving else UNAVAILABLE)
            return Response(raw, media_type="application/json", headers={"Cache-Control": "no-store"})
        if disconnected in completed:
            raise HTTPException(499, "策略配置连接已关闭，请沿原请求核查结果")
        raise StrategyConfigurationError(UNKNOWN if saving else UNAVAILABLE)
    finally:
        future.cancel()
        if disconnected is not None:
            disconnected.cancel()
            await asyncio.gather(disconnected, return_exceptions=True)


def router():
    routes = APIRouter(prefix="/v1/ui/strategy-configurations")

    def owner(request):
        value = getattr(request.app.state, "strategy_configuration_owner", None)
        if value is None:
            raise StrategyConfigurationError()
        return value

    @routes.get("")
    async def workspace(request: Request):
        deadline = monotonic() + REQUEST_SECONDS
        await _body(request, deadline, writing=False)
        return await _submit(request, owner(request).read, deadline)

    @routes.post("/validate")
    async def validate(request: Request):
        deadline = monotonic() + REQUEST_SECONDS
        value = await _body(request, deadline, writing=True)
        try:
            keys(value, ("schema", "configuration"))
            if value["schema"] != VALIDATE_SCHEMA:
                raise ConfigurationValueError()
        except ConfigurationValueError:
            raise HTTPException(422, "策略配置校验请求格式无效") from None
        return await _submit(request, lambda end: owner(request).validate(value["configuration"], end), deadline)

    @routes.put("")
    async def save(request: Request):
        deadline = monotonic() + REQUEST_SECONDS
        value = await _body(request, deadline, writing=True)
        return await _submit(request, lambda end: owner(request).save(value, end), deadline, saving=True)

    @routes.get("/requests/{request_id}")
    async def receipt(request: Request, request_id: str):
        deadline = monotonic() + REQUEST_SECONDS
        await _body(request, deadline, writing=False, query=("store_id",))
        return await _submit(request, lambda end: owner(request).lookup(request.query_params["store_id"], request_id, end), deadline)

    return routes


async def strategy_configuration_error(_request, error: StrategyConfigurationError):
    return JSONResponse(status_code=error.code, content={"detail": str(error)}, headers={"Cache-Control": "no-store"})
