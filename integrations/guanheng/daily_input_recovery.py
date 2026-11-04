"""原INDEX输入任务的读取责任续核；不重新采集旧日公开事实或创建旧请求。"""
from pathlib import Path
from contextlib import ExitStack
import time

from .market_generation import read_fixed
from ..guanheng_market_client import strict_json


def registered_requests(index):
    """核所有已提交请求的存在性，返回可供新输入引用的原件；不读取来源。"""
    requests = []
    for _, row in sorted(index.items()):
        for original in row.get('history_requests', []):
            if not Path(original).is_file():
                raise FileNotFoundError('daily historical original request missing')
            requests.append(original)
        original = row.get('request')
        if original is None:
            if row.get('state') == 'published':
                raise ValueError('daily published original request absent')
            continue
        path = Path(original)
        if path.is_file():
            requests.append(original)
        elif (row.get('state') == 'published' or (path.parent/'work/REQUEST.json').exists()
              or (path.parent/'work/STATE.json').exists()):
            raise FileNotFoundError('daily committed original request missing')
    return list(dict.fromkeys(requests))


def _slot_candidates(root, original):
    """仅枚举原数据owner可能创建的读取槽；生成器由外层owner显式关闭。"""
    captures = [root/'cache', root.parent/'work/readback',
                root.parent/'work/prices/inputs/cache', root.parent/'work/prices/inputs/readback']
    for capture in captures:
        if not (capture/'manifest.json').exists():
            for slot in (capture/'slots').glob('*.json'):
                yield slot, original['inputs']['connections']['batch']
    source = root/'prices/source'
    scope = root/'prices/SCOPE.json'
    complete = scope.exists() and strict_json(read_fixed(scope, maximum=16777216)).get('reference_state', {}).get('membership_complete') is True
    if not complete:
        connection = original.get('price_scope', {}).get('reference_connection')
        for pattern in ('universe-*.json', 'details-*.json'):
            for slot in source.glob(pattern):
                if connection is None:
                    raise ValueError('daily retained reference connection missing')
                yield slot, connection


def close_input_discovery(state):
    """停止时关闭全部未完成目录迭代；完成迭代不累积清理回调。"""
    with ExitStack() as resources:
        for iterator, _ in state.get('discovery', {}).values():
            resources.callback(iterator.close)
        state.get('discovery', {}).clear()


def observe_input_reads(index, state, *, target_day, deadline, cancelled):
    """调用方持publication租约及本线程state；原slot仍为唯一持久结果。

    state只缓存本进程已核的consumed槽及轮询顺序，重启从原INDEX/slot恢复。
    调用方在退出租约前调用close_input_discovery，关闭跨轮保留的目录迭代。
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
    discovery = state.setdefault('discovery', {})
    discovered = state.setdefault('discovered', set())
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
        if root not in discovery:
            original = strict_json(read_fixed(intent, maximum=16777216))['configuration']
            discovery[root] = (_slot_candidates(root, original), target_day)
        iterator, started_target = discovery[root]
        while time.monotonic() < discovery_deadline:
            if cancelled():
                raise InterruptedError('daily retained input discovery stopped')
            try:
                slot, connection = next(iterator)
            except StopIteration:
                del discovery[root]
                discovered.add(root)
                # 当前日后续run_update仍可创建回读；跨日后须重新完整扫描再封存。
                if day < started_target:
                    state['roots'].add(root)
                break
            except BaseException:
                del discovery[root]
                discovered.discard(root)
                iterator.close()  # 异常终止不授完整扫描资格；后继从同原件再次明确失败。
                raise
            if slot not in slots and len(slots) >= 100000:
                iterator.close()
                del discovery[root]  # 容量拒绝不丢掉刚枚举的原槽；后继仍从原根明确拒绝。
                discovered.discard(root)
                raise ValueError('daily retained input slot capacity')
            slots[slot] = connection
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
        state['checked'][name] = time.monotonic()  # 未派发/旧证明不足也轮转，避免饿死其他已发现原槽。
        if set(record) == {'request'}:
            state['pending'].add(name)  # 旧证明不足的登记保留未知，不据缺attempted推断未执行。
            continue
        if record.get('consumed') is True:
            state['consumed'].add(name)
            state['pending'].discard(name)
            continue
        if record.get('attempted') is not True and record.get('result') is None:
            # 未尝试槽没有Source执行责任；禁止借恢复补发旧批次。
            state['pending'].discard(name)
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
                discovery_pending=len(set(discovery) | {root for root in roots
                    if root not in discovered and (root/'INPUTS.json').exists()}))  # 尚未完整发现的输入根数。
