"""HPR产品独立控制合同；原paired-control唯一拥有Server/monitor/关闭。"""
from .paired_control import _serve_factory
from .history_preparation_product import build_product_runtime

SCHEMAS = dict(ready='qmt.history-preparation-ready.v1',
    stop='qmt.history-preparation-stop.v1', closed='qmt.history-preparation-closed.v1')


def serve_product(directory, *, installed_agent, control_directory=None, control_id=None):
    return _serve_factory(lambda: build_product_runtime(directory, installed_agent=installed_agent),
        control_directory=control_directory, control_id=control_id, schemas=SCHEMAS)
