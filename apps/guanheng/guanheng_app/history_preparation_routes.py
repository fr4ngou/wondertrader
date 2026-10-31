"""HPR当前进程的有限只读观察；不访问来源、配对材料或补齐操作。"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from .operations import process_status, utc_now


def router(*, invalid=False):
    routes = APIRouter()
    path = '/v1/ui/qmt-history-preparation'

    @routes.get(path)
    async def status(request: Request):
        if (request.query_params or request.headers.get('content-length', '0') != '0'
                or request.headers.get('transfer-encoding')):
            raise HTTPException(422, '历史补齐状态不接受额外参数')
        app = request.app
        return JSONResponse(headers={'Cache-Control': 'no-store'}, content={
            'schema_version': 'guanheng.history-preparation-app-status.v1', 'read_only': True,
            'observed_at': utc_now(),
            'process': process_status(app.state.history_preparation_process, invalid=invalid,
                                      startup_failed=app.state.history_preparation_start_error),
            'qmt_connection': 'not_checked', 'data_qualification': 'not_checked',
        })

    @routes.api_route(path, methods=['POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'])
    async def read_only():
        return JSONResponse({'detail': '历史补齐状态仅提供只读查询'}, status_code=405,
                            headers={'Allow': 'GET', 'Cache-Control': 'no-store'})
    return routes
