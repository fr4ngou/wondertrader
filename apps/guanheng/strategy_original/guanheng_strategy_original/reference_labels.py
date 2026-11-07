"""固定原SH50函数的可空原因文本装配；不改变原经济条件或文件。"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

_NAME = '_guanheng_optional_reason_number'


def _number(value, specification):
    """缺失指标保留未知文字；已知值执行同一Python数字格式化。"""
    return '未知' if value is None else format(value, specification)


class _ReasonNumbers(ast.NodeTransformer):
    def __init__(self):
        self.count = 0  # 仅本次已核函数的reason数字渲染位置数，不是业务限制。

    def visit_FormattedValue(self, node):
        # 原数字格式常量保持；转换/动态格式不在本修复的准入范围。
        if node.conversion == -1 and isinstance(node.format_spec, ast.JoinedStr):
            parts = node.format_spec.values
            if all(isinstance(part, ast.Constant) and isinstance(part.value, str) for part in parts):
                self.count += 1
                return ast.copy_location(ast.FormattedValue(value=ast.Call(func=ast.Name(id=_NAME, ctx=ast.Load()),
                    args=[node.value, ast.Constant(value=''.join(part.value for part in parts))], keywords=[]),
                    conversion=-1, format_spec=None), node)
        return node


def _reason_assignments(function):
    return [node for node in ast.walk(function) if isinstance(node, ast.Assign)
            and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'reason']


def _economics(function):
    tree = deepcopy(function)
    for node in _reason_assignments(tree):
        node.value = ast.Constant(value=None)
    return ast.dump(tree, include_attributes=False)


def prepare_nullable_reason_labels(backend: Path) -> None:
    """只在已核当前计算子进程装配原函数；router继续持同一函数对象。

    每次先核原文件SHA及函数归属，AST转换局限于reason赋值右侧。原函数对象的
    代码替换保留router已绑定引用、原globals/defaults；所有文件保持只读。
    """
    name = 'backend/base/analysis/strategy/sh50.py'
    path = backend.parent / name
    raw = path.read_bytes()
    manifest = json.loads((Path(__file__).parent / 'source_manifest.json').read_bytes())
    if hashlib.sha256(raw).hexdigest() != manifest['files'][name]:
        raise ValueError('原原因文本源码身份失配')
    module = importlib.import_module('base.analysis.strategy.sh50')
    if Path(module.__file__).resolve() != path.resolve():
        raise ValueError('原原因文本模块来源失配')
    function = module.run_sh50_strategy
    if getattr(function, '_guanheng_nullable_reason_sha256', None) == manifest['files'][name]:
        return
    tree = ast.parse(raw.decode('utf8'))
    original = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function.__name__)
    adapted = deepcopy(original)
    renderer = _ReasonNumbers()
    for assignment in _reason_assignments(adapted):
        assignment.value = renderer.visit(assignment.value)
    if not renderer.count or _economics(original) != _economics(adapted):
        raise ValueError('原原因文本转换影响经济逻辑')
    namespace = {}
    code = compile(ast.fix_missing_locations(ast.Module(body=[adapted], type_ignores=[])), str(path), 'exec',
                   flags=__import__('__future__').annotations.compiler_flag, dont_inherit=True)
    exec(code, module.__dict__, namespace)
    replacement = namespace[function.__name__]
    if function.__code__.co_freevars != replacement.__code__.co_freevars:
        raise ValueError('原原因文本函数闭包失配')
    module.__dict__[_NAME] = _number
    function.__code__ = replacement.__code__
    function._guanheng_nullable_reason_sha256 = manifest['files'][name]
