"""独立WT唯一1.1.2回放报告边界，复用已有业务validator。"""
import json
import math
from json.encoder import encode_basestring_ascii

from guanheng_strategy_core.contracts import canonical_bytes, json_value, KernelValidationError
from .retained_replay import REPORT_SCHEMA, RetainedReplayInput
from .strategy_replay_facts import SessionError


def report_schema_for_input(value):
    from .retained_per_date_replay import INPUT_SCHEMA, REPORT_SCHEMA as per_date_schema
    if type(value) is not dict:
        raise SessionError('独立WT回测只接受唯一正式1.1.2回放输入')
    if value.get('schema') == 'guanheng.retained-replay-input.v1':
        return REPORT_SCHEMA
    if value.get('schema') == INPUT_SCHEMA and set(value) == {'schema', 'session', 'source'}:
        return per_date_schema
    raise SessionError('独立WT回测只接受唯一正式1.1.2回放输入')


def _canonical_value(value, maximum):
    """生成与loads(canonical_bytes(value))相同的独立、有序JSON纯值及大小。

    领域准入先完成；json_value仍负责日期、枚举和dataclass的唯一规范化。
    私有树逐节点计入原ASCII JSON字节预算，省去Python流式编码后再解析
    同一树。短字符串长度只在本次调用内复用，缓存满后继续正常编码。
    """
    used = 0
    lengths = {}

    def consume(count):
        nonlocal used
        used += count
        if used > maximum:
            raise KernelValidationError('capacity_exceeded', '策略结果超出输出容量')

    def visit(item):
        if isinstance(item, dict):
            consume(2)
            result = {}
            if not item:
                return result
            for key, child in sorted(item.items()):
                # 与标准JSON编码器一致，分隔符按实际迭代项计费；容器
                # 子类的长度可与迭代结果不同，空容器判断也沿其原协议。
                if result:
                    consume(1)
                # json_value会原样返回Enum.value；其中的JSON容器和对象键
                # 仍沿标准编码器语义处理，包括tuple及数值/null对象键。
                if not isinstance(key, str):
                    if key is None or isinstance(key, (int, float)):
                        key = json.dumps(key, allow_nan=False, separators=(',', ':'))
                    else:
                        raise TypeError('keys must be str, int, float, bool or None')
                normalized_key = visit(key)
                consume(1)
                result[normalized_key] = visit(child)
            return result
        if isinstance(item, (tuple, list)):
            consume(2)
            result = []
            if not item:
                return result
            for child in item:
                if result:
                    consume(1)
                result.append(visit(child))
            return result
        if isinstance(item, str):
            item = str.__str__(item)
            size = lengths.get(item)
            if size is None:
                size = len(encode_basestring_ascii(item))
                if len(item) <= 256 and len(lengths) < 4096:
                    lengths[item] = size
        elif type(item) is bool:
            size = 4 if item else 5
        elif item is None:
            size = 4
        elif isinstance(item, int):
            item = int.__int__(item)
            size = len(repr(item))
        elif isinstance(item, float):
            item = float.__float__(item)
            if not math.isfinite(item):
                raise ValueError('Out of range float values are not JSON compliant')
            size = len(repr(item))
        else:
            raise TypeError('Object is not JSON serializable')
        consume(size)
        return item

    result = visit(json_value(value))
    return result, used


def normalize_session(value):
    schema = report_schema_for_input(value)
    if schema == REPORT_SCHEMA:
        return json.loads(canonical_bytes(RetainedReplayInput.from_dict(value), max_bytes=8388608))
    from .retained_per_date_replay import INPUT_SCHEMA, normalize_source_binding
    # 先沿原领域契约完整准入，再一次生成有界、排序且独立的公开值。
    # 原实现反复canonical编码/解析同一私有树；此处按相同JSON编码逐标量
    # 计费后直接返回规范纯值，容量在结果树扩张之前检查，原值与键序保持。
    session, session_size = _canonical_value(RetainedReplayInput.from_dict(value['session']), 8388608)
    source, source_size = _canonical_value(normalize_source_binding(value['source']), 16777216)
    outer_size = (4 + len('"schema":') + len(encode_basestring_ascii(INPUT_SCHEMA))
                  + len('"session":') + session_size + len('"source":') + source_size)
    if outer_size > 16777216:
        raise KernelValidationError('capacity_exceeded', '策略结果超出输出容量')
    return dict(schema=INPUT_SCHEMA, session=session, source=source)


def validate_report_dict(value, *, check=None):
    from .retained_report import validate_report, validate_per_date_report
    from .retained_per_date_replay import REPORT_SCHEMA as per_date_schema
    validator = (validate_per_date_report if type(value) is dict and value.get('schema') == per_date_schema
                 else validate_report)
    return validator(value, check=check)


def project_session_record(report, index, *, check=None):
    from .retained_report import ValidatedRetainedReport, project_record
    if type(report) is not ValidatedRetainedReport:
        report = validate_report_dict(report, check=check)
    return project_record(report, index, check=check)
