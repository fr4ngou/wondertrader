"""QST-R19 源状态的纯准入；核事实与同次配置，不授额外写许可。"""
from guanheng_qmt_shm_agent.protocol import ProtocolError
from guanheng_qmt_shm_agent.trade_capabilities import SOURCE_STATUS_V1, SOURCE_STATUS_V2


_V2_FIELDS = ('unknown_fenced', 'hard_fault', 'cancel_admission')
_MAX_SEQUENCE = 2 ** 53 - 1
_FIELDS = ('schema_version', 'session_id', 'binding_id', 'binding_sha256',
           'writes_enabled', 'source_mode_live', 'write_admission', 'closing',
           'gap', 'queued', 'executing', 'commands', 'completed', 'events')
_EVENT_FIELDS = ('closed', 'inflight', 'retained', 'used_bytes',
                 'published_through', 'offered_through', 'acknowledged_through',
                 'gap', 'session_id', 'binding_id')


def _reject():
    # 账户、SDK对象与输入原文均不进入错误正文。
    raise ProtocolError('invalid trade source status') from None


def _fields(value, names):
    if (type(value) is not dict or len(value) != len(names)
            or any(type(key) is not str for key in value)
            or set(value) != set(names)):
        _reject()


def _text(value):
    if (type(value) is not str or not 1 <= len(value) <= 128
            or not value.strip() or any(not 32 <= ord(char) < 127 for char in value)):
        _reject()
    return value


def _digest(value):
    if (type(value) is not str or len(value) != 64
            or any(char not in '0123456789abcdef' for char in value)):
        _reject()
    return value


def _integer(value, maximum, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        _reject()
    return value


def _gap(value):
    if value is None:
        return None
    _fields(value, ('code', 'sequence'))
    _text(value['code'])
    if value['sequence'] is not None:
        _integer(value['sequence'], _MAX_SEQUENCE, 1)
    return dict(value)


def validate_source_status(value, *, binding_id, binding_sha256, writes_enabled, limits):
    """校验源普通值，返回独立副本。

    expected参数由已准入配置owner提供；此处只取状态用到的三个额度，
    完整descriptor仍由trade_capabilities唯一校验。状态不预留队列容量，
    也不清除Host已经观察的unknown/gap；其生命周期由runtime拥有。
    """
    _text(binding_id)
    _digest(binding_sha256)
    if type(writes_enabled) is not bool or type(limits) is not dict:
        _reject()
    maxima = {}
    for name in ('max_commands', 'max_events', 'max_total_event_bytes'):
        if name not in limits:
            _reject()
        maxima[name] = _integer(limits[name], _MAX_SEQUENCE, 1)

    if type(value) is not dict or value.get('schema_version') not in (SOURCE_STATUS_V1, SOURCE_STATUS_V2):
        _reject()
    v2 = value['schema_version'] == SOURCE_STATUS_V2
    _fields(value, _FIELDS + (_V2_FIELDS if v2 else ()))
    session_id = _text(value['session_id'])
    if (_text(value['binding_id']) != binding_id
            or _digest(value['binding_sha256']) != binding_sha256):
        _reject()
    for name in ('writes_enabled', 'source_mode_live', 'write_admission', 'closing', 'executing'):
        if type(value[name]) is not bool:
            _reject()
    if value['writes_enabled'] is not writes_enabled:
        _reject()
    for name in ('queued', 'completed', 'commands'):
        _integer(value[name], maxima['max_commands'])
    # 结果发布先将entry设completed，原tick finally才清executing；该合法
    # 重叠仍有执行收尾职责，不能强制三类计数互斥并中断来源代际。
    if (value['queued'] + value['completed'] > value['commands']
            or value['queued'] + int(value['executing']) > value['commands']):
        _reject()
    gap = _gap(value['gap'])

    events = value['events']
    _fields(events, _EVENT_FIELDS)
    if (_text(events['session_id']) != session_id
            or _text(events['binding_id']) != binding_id
            or type(events['closed']) is not bool):
        _reject()
    retained = _integer(events['retained'], maxima['max_events'])
    _integer(events['inflight'], retained)
    _integer(events['used_bytes'], maxima['max_total_event_bytes'])
    published = _integer(events['published_through'], _MAX_SEQUENCE)
    offered = _integer(events['offered_through'], published)
    acknowledged = _integer(events['acknowledged_through'], offered)
    if published - acknowledged > retained:
        _reject()
    event_gap = _gap(events['gap'])
    # service.status优先呈现event gap；自身fault允许在event无gap时存在。
    if event_gap is not None and event_gap != gap:
        _reject()
    if value['write_admission'] and (not writes_enabled or not value['source_mode_live']
            or value['closing'] or gap is not None):
        _reject()
    hard_fault = None
    if v2:
        for key in ('unknown_fenced', 'cancel_admission'):
            if type(value[key]) is not bool:
                _reject()
        if value['hard_fault'] is not None:
            _fields(value['hard_fault'], ('code',))
            hard_fault = {'code': _text(value['hard_fault']['code'])}
        if gap != event_gap:
            _reject()
        base = (writes_enabled and value['source_mode_live'] and not value['closing']
                and not events['closed'] and gap is None and hard_fault is None)
        if (value['cancel_admission'] != base
                or value['write_admission'] != (base and not value['unknown_fenced'])):
            _reject()
    # SDK执行中关闭会延迟event封口；两个closed事实不能强制相等。
    result = dict(value)
    result['gap'] = gap
    result['events'] = dict(events)
    result['events']['gap'] = event_gap
    if v2:
        result['hard_fault'] = hard_fault
    return result
