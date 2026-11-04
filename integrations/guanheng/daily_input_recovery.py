"""原INDEX输入任务的读取责任续核；不重新采集旧日公开事实或创建旧请求。"""
from pathlib import Path
import time

from .market_generation import read_fixed
from ..guanheng_market_client import strict_json


def observe_input_reads(index, state, *, target_day, deadline, cancelled):
    """调用方持publication租约及本线程state；原slot仍为唯一持久结果。

    state只缓存本进程已核的consumed槽及轮询顺序，重启从原INDEX/slot恢复。
    只核已尝试的v8/v9原身份；未派发的旧页/批次不补发，HPR由原计划拥有。
    """
    from .source_history_transport import BoundHistorySource, SourcePending
    from guanheng_qmt_shm.read_retention_client import (
        RetainedReadClient, RetainedReadPending, RetainedReadFailure, inspect_saved_result)

    roots = {}
    for day, row in index.items():
        roots.update((Path(path).parent/'inputs', day) for path in
                     [*row.get('history_requests', []), *([row['request']] if row.get('request') else [])])
    slots = state['slots']
    discovery_deadline = time.monotonic()+max(0, (deadline-time.monotonic())/2)
    for root, day in sorted(roots.items()):
        if root in state['roots']:
            continue
        if cancelled():
            raise InterruptedError('daily retained input observation stopped')
        if time.monotonic() >= discovery_deadline:
            break
        intent = root/'INPUTS.json'
        if not intent.exists():
            continue
        original = strict_json(read_fixed(intent, maximum=16777216))['configuration']
        # 顶层请求只在完整股票capture后提交；未提交输入的只读槽仍留在原根。
        if not (root.parent/'REQUEST.json').exists():
            for slot in (root/'cache'/'slots').glob('*.json'):
                slots[slot] = original['inputs']['connections']['batch']
        source = root/'prices'/'source'
        scope = root/'prices'/'SCOPE.json'
        complete = scope.exists() and strict_json(read_fixed(scope, maximum=16777216)).get('reference_state', {}).get('membership_complete') is True
        if not complete:
            connection = original.get('price_scope', {}).get('reference_connection')
            for pattern in ('universe-*.json', 'details-*.json'):
                for slot in source.glob(pattern):
                    if connection is None:
                        raise ValueError('daily retained reference connection missing')
                    slots[slot] = connection
        if day < target_day or (root.parent/'REQUEST.json').exists():
            state['roots'].add(root)  # 已封存日不再创建页；当前失败输入每轮重新发现原槽。
    if len(slots) > 100000:
        raise ValueError('daily retained input slot capacity')
    observed = 0
    for slot in sorted(slots, key=lambda path: (state['checked'].get(str(path), 0), str(path))):
        name = str(slot)
        if name in state['consumed']:
            continue
        if cancelled():
            raise InterruptedError('daily retained input observation stopped')
        if time.monotonic() >= deadline:
            break
        record = strict_json(read_fixed(slot, maximum=16777216))
        inspect_saved_result(record)  # 共用原请求/绑定/结果准入；损坏保持明确失败。
        if set(record) == {'request'}:
            state['pending'].add(name)  # 旧证明不足的登记保留未知，不据缺attempted推断未执行。
            continue
        if record.get('consumed') is True:
            state['consumed'].add(name)
            state['pending'].discard(name)
            continue
        if record.get('attempted') is not True and record.get('result') is None:
            # 未尝试槽没有Source执行责任；禁止借恢复补发旧批次。
            continue
        request = record['request']
        if request['operation_id'] not in ('market.market_data', 'market.security_universe', 'market.security_details'):
            raise ValueError('daily retained input operation invalid')
        transport = BoundHistorySource(slots[slot], reuse_connections=True)
        try:
            try:
                RetainedReadClient(transport).read(request['operation_id'], request['arguments'], slot,
                    deadline=min(deadline, time.monotonic()+.25))
            except (SourcePending, RetainedReadPending, RetainedReadFailure):
                pass  # 原未知或失败均留原槽；确认消费与业务成功分别核实。
        finally:
            transport.close()
        after = strict_json(read_fixed(slot, maximum=16777216))
        if after['request'] != request:
            raise ValueError('daily retained input request changed')
        inspect_saved_result(after)
        if after.get('consumed') is True or after.get('admission_rejection') is not None:
            state['consumed'].add(name)
            state['pending'].discard(name)
        else:
            state['pending'].add(name)
        state['checked'][name] = time.monotonic()
        observed += 1
    return dict(observed=observed,  # 本轮实际核查的原读取槽数，未产生新请求。
                pending=len(state['pending']),  # 已发现仍未确认消费的原身份数，不阻止独立新日读取。
                discovery_pending=sum(root not in state['roots'] and (root/'INPUTS.json').exists()
                                      for root in roots))  # 尚未完成发现或当前未提交的输入根数。
