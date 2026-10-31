"""App持有执行进程的只读生命周期；运行、成交及恢复事实仍归原生owner。"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from .operations import process_status, utc_now


def router(*, configuration=None, invalid=False):
    routes = APIRouter()

    @routes.get('/v1/ui/execution-process')
    async def status(request: Request):
        if (request.query_params or request.headers.get('content-length', '0') != '0'
                or request.headers.get('transfer-encoding')):
            raise HTTPException(422, '执行进程状态不接受额外参数')
        app = request.app
        process = process_status(app.state.execution_process, invalid=invalid,
                                 startup_failed=app.state.execution_start_error)
        if process['state'] == 'ready':
            process['label'] = '已启动'
            if process['error'] is None:
                process['reason'] = '原生执行进程已确认启动；实际策略、账户与执行资格分别核实'
        return JSONResponse(headers={'Cache-Control': 'no-store'}, content={
            'schema_version': 'guanheng.execution-app-status.v1', 'read_only': True,
            'observed_at': utc_now(), 'process': process,
            'configuration_sha256': configuration.configuration_sha256 if configuration is not None else None,
            'execution_qualification': 'not_checked', 'recovery_ready': False,
        })

    return routes
