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
