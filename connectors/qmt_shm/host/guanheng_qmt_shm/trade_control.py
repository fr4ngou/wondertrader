"""交易产品控制收据；Server/monitor/关闭全部复用原paired-control owner。"""
import os
from pathlib import Path
from uuid import UUID, uuid4
from guanheng_qmt_shm_agent.protocol import canonical
from .paired_control import _serve_factory, PairedControlError
from .private_files import write_private_new
from .trade_pair import _inspect
from .trade_product import build_product_runtime

SCHEMAS = dict(ready='qmt.trade-host-ready.v1', stop='qmt.trade-host-stop.v1', closed='qmt.trade-host-closed.v1')


def serve_product(directory, *, installed_agent, control_directory=None, control_id=None):
    selected = [None]
    def factory():
        value = build_product_runtime(directory, installed_agent=installed_agent)
        selected[0] = value
        return value
    try:
        return _serve_factory(factory, control_directory=control_directory, control_id=control_id, schemas=SCHEMAS)
    except PairedControlError:
        value = selected[0]
        snapshot = None if value is None else value[0].fault_snapshot
        if snapshot is not None and control_directory is not None:
            # service已进入start才可能有故障快照；原控制owner此前已创建私有目录。
            # 独立附属诊断不改变原closed schema、首因或任何关闭资格。
            try:
                path = Path(control_directory)
                if path.is_absolute() and path.drive.upper() == 'E:' and str(UUID(control_id)) == control_id:
                    _inspect(path, True)
                    report = dict(schema='qmt.trade-host-failure.v1', control_id=control_id,
                        pid=os.getpid(), **value[2], fault=snapshot)
                    temporary = path / ('failure.' + uuid4().hex + '.tmp')
                    write_private_new(temporary, canonical(report))
                    os.rename(temporary, path / 'failure.json')
            except Exception:
                # 原异常仍由调用方接收；诊断发布失败不替代运行故障。
                pass
        raise
    finally:
        # 原控制owner完成关闭后发布首个404；正常收尾同样保留造成外层退出的业务读取事实。
        try:
            value = selected[0]
            snapshot = None if value is None else value[0].missing_response_snapshot
            if snapshot is not None and control_directory is not None:
                path = Path(control_directory)
                if path.is_absolute() and path.drive.upper() == 'E:' and str(UUID(control_id)) == control_id:
                    _inspect(path, True)
                    report = dict(
                        schema='qmt.trade-host-missing-response.v1',  # 附属诊断版本；不扩展原关闭收据。
                        control_id=control_id,  # 原控制owner的UUID。
                        pid=os.getpid(),  # 实际Host进程身份。
                        **value[2],  # 原配对manifest/config摘要，无认证或账户正文。
                        response=snapshot)  # 单条去敏404事实，由服务请求边界拥有。
                    temporary = path / ('missing-response.' + uuid4().hex + '.tmp')
                    write_private_new(temporary, canonical(report))
                    os.rename(temporary, path / 'missing-response.json')
        except Exception:
            pass  # 发布失败保留原运行结果，绝不将HTTP 404改判为关闭失败。
