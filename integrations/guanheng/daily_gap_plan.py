"""缺口计划唯一持久文档合同；原保护身份、任务与排除项保持完整。"""
import hashlib
import math
from datetime import date
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
import re
import time
from threading import Event

from ..guanheng_market_client import strict_json
from .market_generation import encode, read_fixed

SCHEMA = 'guanheng.daily-gap-plan.v1'
MAX_PROTECTED_SLOTS = 100000  # 沿原日线输入合同的保护引用上限，不限制证券/交易目标。
# 保护引用按每项约1KiB规划，加原16MiB任务/排除文档空间，向上取128MiB。
# 只限制原件资源；不截断保护、任务、日期或排除列表，通用16MiB默认保持。
MAX_GAP_PLAN_BYTES = 128 * 1024 * 1024
MAX_REFERENCE_READERS = 4  # 只并行本地原槽读取/纯资格核验，不并发Source或SDK准备调用。
_HASH = re.compile(r'[0-9a-f]{64}')
_SYMBOL = re.compile(r'[0-9]{6}\.(?:SH|SZ|BJ)')


class GapPlanReferenceError(RuntimeError):
    """已冻结责任的原件缺失/身份改变；保留marker，不降为可重建半份计划。"""


def _check(deadline, cancelled):
    if cancelled():
        raise InterruptedError('daily gap plan stopped')
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('daily gap plan deadline expired')


def _controls(deadline, cancelled):
    if (not callable(cancelled) or deadline is not None and
            (type(deadline) not in (int, float) or not math.isfinite(deadline))):
        raise ValueError('daily gap plan controls invalid')
    _check(deadline, cancelled)


def _day(value):
    if type(value) is not str or re.fullmatch('[0-9]{8}', value) is None:
        raise ValueError('daily gap plan date invalid')
    date.fromisoformat(value[:4]+'-'+value[4:6]+'-'+value[6:])
    return value


def _validate(value, deadline, cancelled, *, historical_read=False):
    required = {'schema', 'capture', 'snapshot_id', 'authorized_from', 'authorized_to',
                'protected_requests', 'tasks', 'exclusions'}
    if (type(value) is not dict or not required <= set(value)
            or set(value)-required-{'required_adjustments', 'required_from'}
            or value.get('schema') != SCHEMA
            or any(type(value[key]) is not list for key in ('protected_requests', 'tasks', 'exclusions'))
            or len(value['protected_requests']) > MAX_PROTECTED_SLOTS):
        raise ValueError('daily gap plan schema or capacity invalid')
    capture = value['capture']
    if (type(capture) is not dict or set(capture) != {'directory', 'sha256'}
            or type(capture['directory']) is not str or not Path(capture['directory']).is_absolute()
            or type(capture['sha256']) is not str or _HASH.fullmatch(capture['sha256']) is None
            or type(value['snapshot_id']) is not str or _HASH.fullmatch(value['snapshot_id']) is None
            or any(type(value[key]) is not str or re.fullmatch('[0-9]{8}', value[key]) is None
                   for key in ('authorized_from', 'authorized_to'))):
        raise ValueError('daily gap plan binding invalid')
    first,last=_day(value['authorized_from']),_day(value['authorized_to'])
    if first>last:
        raise ValueError('daily gap plan authorization invalid')
    adjustments=value.get('required_adjustments',['none','front_ratio'])
    required_from=value.get('required_from',{})
    if (type(adjustments)is not list or tuple(adjustments)not in(('none',),('front_ratio',),('none','front_ratio'))
            or type(required_from)is not dict):
        raise ValueError('daily gap plan price requirements invalid')
    for symbol,start in required_from.items():
        _check(deadline,cancelled)
        if type(symbol)is not str or _SYMBOL.fullmatch(symbol)is None or not first<=_day(start)<=last:
            raise ValueError('daily gap plan per-security date invalid')
    blocked={};protected=[]
    for row in value['protected_requests']:
        _check(deadline, cancelled)
        # v1原writer只冻结这五项身份，没有保存执行结论；只读解码保持unknown。
        # 新写入仍须显式六字段。精确旧形态之外的缺项/额外字段继续作为损坏拒绝。
        if (historical_read and type(row)is dict and set(row)=={
                'slot','request_id','operation_id','arguments','request_sha256'}):
            row=dict(row,execution_state='unknown')
        if (type(row) is not dict or set(row) != {'slot', 'request_id', 'operation_id', 'arguments',
                                                  'request_sha256', 'execution_state'}
                or type(row['slot']) is not str or not Path(row['slot']).is_absolute()
                or any(type(row[key]) is not str or not row[key] for key in ('request_id', 'operation_id'))
                or type(row['arguments']) is not dict or type(row['request_sha256']) is not str
                or _HASH.fullmatch(row['request_sha256']) is None
                or row['execution_state'] not in ('unknown', 'call_returned', 'not_executed')):
            raise ValueError('daily gap plan protected identity invalid')
        protected.append(row)
        args=row['arguments']
        if row['operation_id']=='market.history_prepare'and args.get('period')=='1d'and row['execution_state']=='unknown':
            if (type(args.get('symbol'))is not str or _SYMBOL.fullmatch(args['symbol'])is None
                    or _day(args.get('start_time'))>_day(args.get('end_time'))):
                raise ValueError('daily gap plan original protection invalid')
            blocked.setdefault(args['symbol'],[]).append((args['start_time'],args['end_time']))
    previous_end={}
    for index, task in enumerate(value['tasks']):
        _check(deadline, cancelled)
        if (type(task) is not dict or set(task) != {'index', 'symbol', 'start_date', 'end_date', 'dates', 'reason'}
                or type(task['index']) is not int or task['index'] != index
                or type(task['dates']) is not list or not task['dates']
                or task['dates'][0] != task['start_date'] or task['dates'][-1] != task['end_date']
                or type(task['symbol']) is not str or _SYMBOL.fullmatch(task['symbol']) is None
                or task['reason'] != 'calendar_expected_cache_gap'):
            raise ValueError('daily gap plan task invalid')
        symbol=task['symbol'];previous=None
        for day in task['dates']:
            _check(deadline,cancelled);day=_day(day)
            if (not required_from.get(symbol,first)<=day<=last or previous is not None and day<=previous
                    or any(start<=day<=end for start,end in blocked.get(symbol,()))):
                raise ValueError('daily gap plan task dates outside authorized unprotected range')
            previous=day
        if task['start_date']<=previous_end.get(symbol,''):
            raise ValueError('daily gap plan task ranges overlap')
        previous_end[symbol]=task['end_date']
    for row in value['exclusions']:
        _check(deadline, cancelled)
        if (type(row) is not dict or set(row) != {'symbol', 'date', 'reason'}
                or type(row['symbol'])is not str or _SYMBOL.fullmatch(row['symbol'])is None
                or not first<=_day(row['date'])<=last or row['reason']not in(
                    'before_listing','after_expiry','original_HPR_responsibility',
                    'source_halted_requires_quantity_or_original_history','official_security_no_trade')):
            raise ValueError('daily gap plan exclusion invalid')
    _check(deadline, cancelled)
    # 规范视图供全部消费者/恢复共用；原PLAN字节、描述符SHA及槽保持原身份。
    return dict(value,protected_requests=protected)


def read_protected_request(path, *, deadline, cancelled=lambda: False):
    """新计划及恢复共用原slot/SDK资格核验，只读、不确认消费或访问Source。"""
    from guanheng_qmt_shm.read_retention_client import inspect_saved_result
    _controls(deadline, cancelled)
    slot = strict_json(read_fixed(path, maximum=1048576))
    original = slot['request']
    state = 'unknown'
    if original['operation_id'] == 'market.history_prepare':
        reply = inspect_saved_result(slot)
        if (reply is not None and reply['ok'] is True and reply['data']['effect'] == 'call_returned'
                and all(slot['result'][key] == slot['binding'] for key in
                        ('admitted_binding', 'dispatch_binding', 'result_binding'))):
            state = 'call_returned'
        elif (reply is not None and reply['ok'] is False and reply.get('error_code') == 'preparation_not_executed'
                and slot['result']['admitted_binding'] == slot['binding']
                and slot['result']['dispatch_binding'] is None and slot['result']['result_binding'] is None):
            state = 'not_executed'
    _check(deadline, cancelled)
    return dict(
        slot=str(Path(path).absolute()),  # 原持久槽绝对位置；结果及消费仍归原owner。
        request_id=original['request_id'],  # 原请求UUID，不创建或迁移身份。
        operation_id=original['operation_id'],  # 原业务操作；普通批读不提升为HPR。
        arguments=original['arguments'],  # 原证券、日期及截止参数，保留原值。
        request_sha256=hashlib.sha256(encode(original)).hexdigest(),  # 原请求规范语义SHA。
        execution_state=state)  # 原已返回/明确未派发/未知；独立于价格覆盖。


def _parallel_references(items, operation, deadline, cancelled):
    """至多四项文件核验在途；主线程核原取消，退出前回收全部已启动读取。"""
    _controls(deadline,cancelled)
    stopped=Event();ordered=[];pending={};iterator=iter(items);exhausted=False;end=object()
    executor=ThreadPoolExecutor(max_workers=MAX_REFERENCE_READERS,thread_name_prefix='daily-gap-reference')
    try:
        while pending or not exhausted:
            _check(deadline,cancelled)
            while len(pending)<MAX_REFERENCE_READERS and not exhausted:
                _check(deadline,cancelled)
                item=next(iterator,end)
                if item is end:
                    exhausted=True;break
                index=len(ordered);ordered.append(None)
                pending[executor.submit(operation,item,stopped.is_set)]=index
            if not pending:break
            seconds=.05 if deadline is None else min(.05,max(0,deadline-time.monotonic()))
            done,_=wait(pending,timeout=seconds,return_when=FIRST_COMPLETED)
            for future in done:
                ordered[pending.pop(future)]=future.result()
        _check(deadline,cancelled)
        return ordered
    finally:
        stopped.set()
        for future in pending:future.cancel()
        executor.shutdown(wait=True,cancel_futures=True)


def collect_protected_requests(paths, *, deadline, cancelled=lambda: False):
    """与恢复共用相同本地核验；输出保留输入顺序及全部原请求身份。"""
    return _parallel_references(paths,lambda path,stop:read_protected_request(
        path,deadline=deadline,cancelled=stop),deadline,cancelled)


def inspect_gap_plan(path, *, expected_sha256=None, deadline=None, cancelled=lambda: False):
    """同一次有界读取返回固定描述符和计划；仅原件IO，不触发Source或改变原槽。"""
    _controls(deadline, cancelled)
    path = Path(path).absolute()
    if expected_sha256 is not None and (type(expected_sha256) is not str or _HASH.fullmatch(expected_sha256) is None):
        raise ValueError('daily gap plan digest invalid')
    raw = read_fixed(path, maximum=MAX_GAP_PLAN_BYTES, identity=expected_sha256)
    _check(deadline, cancelled)
    value = _validate(strict_json(raw), deadline, cancelled, historical_read=True)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest()), value


def load_gap_plan(descriptor, *, deadline=None, cancelled=lambda: False):
    """所有计划消费者共用类型/字节/SHA合同；deadline沿外层原D传递。"""
    if (type(descriptor) is not dict or set(descriptor) != {'path', 'sha256'}
            or type(descriptor['path']) is not str or not Path(descriptor['path']).is_absolute()):
        raise ValueError('daily gap plan descriptor invalid')
    return inspect_gap_plan(descriptor['path'], expected_sha256=descriptor['sha256'],
                            deadline=deadline, cancelled=cancelled)[1]


def restore_gap_plan(path, *, capture, snapshot_id, authorized_from, authorized_to,
                     protected_slots, deadline=None, cancelled=lambda: False,
                     required_adjustments=None, required_from=None):
    """完成marker按原输入认领；冻结责任不重算，不改旧slot或重新生成HPR身份。"""
    descriptor, value = inspect_gap_plan(path, deadline=deadline, cancelled=cancelled)
    expected = dict(capture=capture, snapshot_id=snapshot_id,
                    authorized_from=authorized_from, authorized_to=authorized_to)
    if (any(value[key] != item for key, item in expected.items())
            or sorted(row['slot'] for row in value['protected_requests'])
            != sorted(str(Path(path).absolute()) for path in protected_slots)
            or required_adjustments is not None and value.get('required_adjustments', ['none', 'front_ratio']) != list(required_adjustments)
            or required_from is not None and value.get('required_from', {}) != required_from):
        raise ValueError('daily gap plan restored input differs')
    def verify(original,stop):
        try:
            current = read_protected_request(original['slot'], deadline=deadline, cancelled=stop)
        except (InterruptedError, TimeoutError):
            raise
        except Exception as error:
            raise GapPlanReferenceError('daily gap plan protected reference unavailable') from error
        if (any(current[key] != original[key] for key in
                ('slot', 'request_id', 'operation_id', 'arguments', 'request_sha256'))
                or original['execution_state'] != 'unknown' and current['execution_state'] != original['execution_state']):
            raise GapPlanReferenceError('daily gap plan protected reference changed')
    _parallel_references(value['protected_requests'],verify,deadline,cancelled)
    _check(deadline, cancelled)
    return descriptor


def write_gap_plan(directory, value, *, deadline, cancelled=lambda: False):
    """写前核同一schema/容量，写后按同合同/SHA回读，成功才交阶段owner提交。"""
    _controls(deadline, cancelled)
    _validate(value, deadline, cancelled)
    raw = encode(value)
    if len(raw) > MAX_GAP_PLAN_BYTES:
        raise ValueError('daily gap plan byte capacity exceeded')
    _check(deadline, cancelled)
    directory = Path(directory).absolute()
    directory.mkdir(parents=False, exist_ok=False)
    path = directory/'PLAN.json'
    path.write_bytes(raw)
    descriptor, _value = inspect_gap_plan(path, expected_sha256=hashlib.sha256(raw).hexdigest(),
                                        deadline=deadline, cancelled=cancelled)
    return descriptor
