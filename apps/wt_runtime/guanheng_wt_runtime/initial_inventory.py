"""当前库存到原P23/唯一核输入的装配；不导入旧交易，也不维护金融账本。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from .execution_strategy import _need
from .managed_local_process import _inspect, _json, _path, _read, _sha


def _encode(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def _timestamp(value):
    _need(type(value) is str and len(value) <= 64, 'initial_inventory_time')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        _need(result.utcoffset() is not None, 'initial_inventory_time')
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        _need(False, 'initial_inventory_time')


@dataclass(frozen=True)
class InitialInventoryPreparation:
    """一次启用基准的输入字节；native_input为空表示原fresh空仓路径。

    baseline_at是本次新运行时间，opened_at保持空，真实旧开仓时间不在合同内。原P23消费
    native_input，原Configured消费runtime_input；后续状态由原WT与KV持有。
    """
    runtime_input: bytes
    native_input: bytes | None
    source_sha256: str
    baseline_at: datetime
    position_count: int


def prepare_initial_inventory(template, facts, *, now, uptime_ms):
    """纯值装配，保留原价/分析/参数/数量policy；所有旧周期与退出初值归零。

    facts由当前券商/标价owner冻结并绑定来源摘要；捕获/有效期不宣称四查询
    同一事务。now为启用UTC时点、uptime_ms为同进程当前系统uptime。CLI使用
    实际时钟；明确隔离模型可注入时钟。函数不写文件、不调用SDK、不发委托。
    """
    from guanheng_strategy_core.contracts import canonical_bytes, utc_timestamp
    from guanheng_strategy_v1 import PositionCycle, SYMBOLS
    from .execution_configured import RetainedRuntimeInput

    _need(type(template) is RetainedRuntimeInput and type(facts) is dict, 'initial_inventory_input')
    required = {'schema', 'broker_source_sha256', 'captured_at', 'valid_until', 'captured_uptime_ms',
                'valid_until_uptime_ms', 'positions'}
    version = facts.get('schema')
    _need(version in ('guanheng.initial-inventory-facts.v1', 'guanheng.initial-inventory-facts.v2'),
          'initial_inventory_input')
    explicit_day = version == 'guanheng.initial-inventory-facts.v1'
    _need(set(facts) == required | ({'trading_date'} if explicit_day else set()), 'initial_inventory_input')
    _need(type(now) is datetime and now.utcoffset() is not None, 'initial_inventory_time')
    now = utc_timestamp(now)
    captured, until = map(_timestamp, (facts['captured_at'], facts['valid_until']))
    _need(captured <= now < until and 0 < (until-captured).total_seconds() <= 3600, 'initial_inventory_expired')
    for value in (uptime_ms, facts['captured_uptime_ms'], facts['valid_until_uptime_ms']):
        _need(type(value) is int and 0 <= value < 2**64, 'initial_inventory_time')
    _need(facts['captured_uptime_ms'] <= uptime_ms < facts['valid_until_uptime_ms']
          and facts['valid_until_uptime_ms']-facts['captured_uptime_ms'] <= 3600000, 'initial_inventory_expired')
    _sha(facts['broker_source_sha256'])
    if explicit_day:
        day = facts['trading_date']
        _need(type(day) is int and 20000101 <= day <= 20991231, 'initial_inventory_trading_date')
        try:
            datetime.strptime(str(day), '%Y%m%d')
        except ValueError:
            _need(False, 'initial_inventory_trading_date')
    _need(type(facts['positions']) is list and len(facts['positions']) <= 8, 'initial_inventory_positions')
    positions = {}
    for item in facts['positions']:
        _need(type(item) is dict and set(item) == {'symbol', 'quantity', 'sellable', 'mark_price', 'mark_source_sha256'},
              'initial_inventory_position')
        symbol, quantity, sellable, mark = (item[k] for k in ('symbol', 'quantity', 'sellable', 'mark_price'))
        _need(type(symbol) is str and symbol in SYMBOLS and symbol not in positions, 'initial_inventory_symbol')
        _need(type(quantity) is int and type(sellable) is int and 0 < quantity <= 10**12
              and 0 <= sellable <= quantity, 'initial_inventory_quantity')
        _need(type(mark) in (int, float) and 0 < mark <= 10**9 and math.isfinite(mark), 'initial_inventory_mark')
        _sha(item['mark_source_sha256'])
        positions[symbol] = dict(item)
    # 先冻结已准入的小输入，再由此一份身份生成全部周期和原初始化文件。
    normalized = dict(facts, positions=[positions[s] for s in sorted(positions)])
    source = sha256(_encode(normalized)).hexdigest()
    cycles, rows = [], []
    opening = int(now.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d%H%M'))
    for symbol in SYMBOLS:
        item = positions.get(symbol)
        if item is None:
            cycles.append(PositionCycle(symbol, 'flat', 0, source))
            continue
        cycle = 'initial-inventory:'+sha256(_encode([source, symbol, now.isoformat()])).hexdigest()
        cycles.append(PositionCycle(symbol, 'initial_inventory', item['quantity'], source, cycle,
                                    baseline_at=now))
        rows.append(dict(code=('SSE' if symbol.endswith('.SH') else 'SZSE')+'.ETF.'+symbol[:6],
            quantity=item['quantity'], sellable=item['sellable'], mark_price=item['mark_price'],
            mark_source_sha256=item['mark_source_sha256'], cycle_id=cycle,
            opened_local_minute=opening, cycle_source_sha256=source))
    request = replace(template.request, cycles=tuple(cycles), previous_exits=(),
        cycles_captured_at=now, cycles_valid_until=until, decision_cutoff=now)
    runtime = replace(template, request=request)
    raw = canonical_bytes(runtime, max_bytes=16*1024*1024)
    native = None
    if rows:
        # 原P23明细时间承载新账本载入基准；唯一核另以明确baseline_at识别
        # 初始库存。原生重新核当前数量/可卖和未决责任，不生成旧真实成交。
        payload = dict(schema='guanheng.cta-takeover.v1' if explicit_day else 'guanheng.cta-takeover.v2', strategy_id='resonance-regime-v1',
            strategy_version='1.1.2', source_sha256=source,
            captured_uptime_ms=facts['captured_uptime_ms'], valid_until_uptime_ms=facts['valid_until_uptime_ms'],
            performance_basis='takeover-mark', positions=rows,
            strategy_state=_encode(dict(schema='guanheng.retained-init.v1', input_sha256=sha256(raw).hexdigest())).decode('ascii'))
        if explicit_day:
            payload['trading_date'] = day
        native = _encode(payload)
    return InitialInventoryPreparation(raw, native, source, now, len(rows))


def main():
    """已安装模块的准备入口；只独占生成输入文件，运行由原受管宿主启动。"""
    parser = argparse.ArgumentParser(description='以券商当前库存建立新运行输入，不迁入旧交易')
    for name in ('template', 'facts', 'output'):
        parser.add_argument('--'+name, required=True)
    for name in ('template-sha256', 'facts-sha256'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--seconds', type=float, default=30)
    args = parser.parse_args()
    _need(math.isfinite(args.seconds) and .1 <= args.seconds <= 120, 'initial_inventory_budget')
    deadline = time.monotonic()+args.seconds
    def check():
        _need(time.monotonic() < deadline, 'initial_inventory_deadline')
    from guanheng_strategy_core.contracts import EvaluationBudget
    from .execution_configured import RetainedRuntimeInput
    from .retained_evaluation import evaluate_retained
    import ctypes
    api = ctypes.WinDLL('kernel32'); api.GetTickCount64.restype = ctypes.c_ulonglong
    template_path, facts_path, output = map(_path, (args.template, args.facts, args.output))
    template_raw = _read(template_path, 16*1024*1024, clock=time.monotonic, deadline=deadline)
    facts_raw = _read(facts_path, 128*1024, clock=time.monotonic, deadline=deadline)
    _need(sha256(template_raw).hexdigest() == _sha(args.template_sha256)
          and sha256(facts_raw).hexdigest() == _sha(args.facts_sha256), 'initial_inventory_source_identity')
    prepared = prepare_initial_inventory(RetainedRuntimeInput.from_dict(_json(template_raw)), _json(facts_raw),
        now=datetime.now(timezone.utc), uptime_ms=api.GetTickCount64())
    request = RetainedRuntimeInput.from_dict(_json(prepared.runtime_input))
    check()
    evaluate_retained(request.request, request.policy, budget=EvaluationBudget(max_seconds=min(5, deadline-time.monotonic())))
    check(); _inspect(output.parent, directory=True)
    output.mkdir(); _inspect(output, directory=True)
    contents = {'runtime-input.json': prepared.runtime_input}
    if prepared.native_input is not None:
        contents['native-input.json'] = prepared.native_input
    files = {}
    for name, raw in contents.items():
        check()
        with (output/name).open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        _need(_read(output/name, 16*1024*1024, clock=time.monotonic, deadline=deadline) == raw,
              'initial_inventory_write')
        files[name] = sha256(raw).hexdigest()
    receipt = dict(schema='guanheng.initial-inventory-preparation.v1', source_sha256=prepared.source_sha256,
        baseline_at=prepared.baseline_at.isoformat(), origin='initial-inventory', position_count=prepared.position_count,
        template_sha256=sha256(template_raw).hexdigest(), facts_sha256=sha256(facts_raw).hexdigest(), files=files,
        history_imported=False, runtime_started=False)
    receipt_raw = _encode(receipt)
    check()
    with (output/'PREPARED.json').open('xb') as stream:
        stream.write(receipt_raw); stream.flush(); os.fsync(stream.fileno())
    _need(_read(output/'PREPARED.json', 128*1024, clock=time.monotonic, deadline=deadline) == receipt_raw,
          'initial_inventory_write')
    check()
    print(json.dumps(dict(prepared=True, position_count=prepared.position_count, runtime_started=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
