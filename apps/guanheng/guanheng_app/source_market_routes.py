"""当前App持有历史查询进程的有限只读投影。"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .operations import process_status, utc_now


def router(*, invalid=False):
    routes = APIRouter()

    @routes.get('/v1/ui/source-market')
    async def status(request: Request):
        if (request.query_params or request.headers.get('content-length', '0') != '0'
                or request.headers.get('transfer-encoding')):
            raise HTTPException(422, '历史查询进程状态不接受额外参数')
        app = request.app
        return JSONResponse(headers={'Cache-Control': 'no-store'}, content={
            'schema_version': 'guanheng.source-market-app-status.v1',
            'read_only': True, 'observed_at': utc_now(),
            'process': process_status(app.state.source_market_process, invalid=invalid,
                                      startup_failed=app.state.source_market_start_error),
            'data_qualification': 'not_checked',
        })

    return routes
