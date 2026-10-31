"""原报告JSON快照/冻结边界；唯一回放报告不导入旧策略session。"""
from json.encoder import encode_basestring_ascii
import math
from types import MappingProxyType
from .strategy_replay_facts import SessionError

class _ReportCheckSignal(BaseException):
    """报告内部的控制信号，越过业务/编码错误转换后交回原调用方。"""

    def __init__(self, original):
        self.original = original
        super().__init__()

def _run_report_checked(operation, check):
    """隔离调用方截止/取消异常，公开出口恢复同一异常对象及其原因码。

    check可使用与业务验证器相同的异常类型。内部传专用BaseException信号，
    使解压、编码和字段校验只转换自身错误；控制异常始终由调用方拥有。
    """
    if check is None:
        return operation(None)

    def guarded_check():
        try:
            check()
        except BaseException as original:
            raise _ReportCheckSignal(original) from None

    try:
        return operation(guarded_check)
    except _ReportCheckSignal as stopped:
        original = stopped.original
        raise original.with_traceback(original.__traceback__) from None

def _snapshot_json(value, *, maximum=8 * 1024 * 1024, check=None):
    """先有界复制JSON树，再交唯一业务校验器；回调不能修改已完成的快照。"""
    used, nodes = 0, 0
    # 仅本次快照复用短字符串的标准JSON长度；缓存满后继续逐值计算，
    # 每个出现位置仍计节点/深度/字节并执行原回调。容量保持固定。
    sizes = {}

    def consume(count):
        nonlocal used
        used += count
        if used > maximum:
            raise SessionError("报告JSON树字节预算耗尽")

    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if check is not None and nodes % 128 == 1:
            check()
        if nodes > 1048576 or depth > 32:
            raise SessionError("报告JSON树节点或深度超限")
        kind = type(item)
        if kind is dict:
            consume(2 + max(0, len(item) - 1))
            result = {}
            for key, child in item.items():
                if type(key) is not str:
                    raise SessionError("报告JSON键必须为字符串")
                visit(key, depth + 1)
                consume(1)
                result[key] = visit(child, depth + 1)
            return result
        if kind is list:
            consume(2 + max(0, len(item) - 1))
            return [visit(child, depth + 1) for child in item]
        # 每个节点只分类一次；检查和字节计费仍在原节点次序中完成。
        # 直接按精确内建类型分派，避免每个标量重复构造类型tuple。
        if kind is str:
            if len(item) > maximum:
                raise SessionError("报告JSON值类型或容量无效")
            size = sizes.get(item)
            if size is None:
                size = len(encode_basestring_ascii(item))
                if len(item) <= 256 and len(sizes) < 4096:
                    sizes[item] = size
        elif kind is int:
            if item.bit_length() > 4096:
                raise SessionError("报告JSON值类型或容量无效")
            size = len(repr(item))
        elif kind is float:
            if not math.isfinite(item):
                raise SessionError("报告JSON值类型或容量无效")
            size = len(repr(item))
        elif kind is bool:
            size = 4 if item else 5
        elif item is None:
            size = 4
        else:
            raise SessionError("报告JSON值类型或容量无效")
        consume(size)
        return item

    result = visit(value, 0)
    if check is not None:
        check()
    return result

def _freeze_json(value, *, check=None):
    if check is not None:
        check()
    if type(value) is dict:
        return MappingProxyType({key: _freeze_json(child, check=check) for key, child in value.items()})
    if type(value) is list:
        return tuple(_freeze_json(child, check=check) for child in value)
    return value

def _thaw_json(value, *, check=None):
    if check is not None:
        check()
    if type(value) is MappingProxyType:
        return {key: _thaw_json(child, check=check) for key, child in value.items()}
    if type(value) is tuple:
        return [_thaw_json(child, check=check) for child in value]
    return value
