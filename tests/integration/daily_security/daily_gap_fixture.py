"""恢复测试的完整合成计划；走原writer/loader，外部来源由各用例替换。"""
from pathlib import Path
import time

from integrations.guanheng.daily_data_update import _save, _descriptor
from integrations.guanheng.daily_gap_plan import SCHEMA, write_gap_plan


def synthetic_gap_plan(directory, symbols, day, *, capture=None, snapshot_id='a'*64):
    """固定合成捕获身份和逐日任务，使用生产计划写入校验保存原件。"""
    directory = Path(directory)
    if capture is None:
        source = directory.parent/'synthetic-capture'
        source.mkdir(exist_ok=True)
        manifest = source/'manifest.json'
        _save(manifest, dict(synthetic=True, symbols=list(symbols)))
        capture = dict(directory=str(source), sha256=_descriptor(manifest)['sha256'])
    value = dict(schema=SCHEMA, capture=capture, snapshot_id=snapshot_id,
                 authorized_from=day, authorized_to=day, protected_requests=[], exclusions=[],
                 required_adjustments=['none'], tasks=[dict(index=index, symbol=symbol,
                     start_date=day, end_date=day, dates=[day], reason='calendar_expected_cache_gap')
                     for index, symbol in enumerate(symbols)])
    return write_gap_plan(directory, value, deadline=time.monotonic()+10)
