"""从V1唯一协议声明生成浏览器只读元数据；不导入/执行策略或复制金融算法。"""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def render(root):
    """元数据绑定原协议源码身份；固定角色、必需字段和分支仅取原声明。"""
    owner = root / 'apps/guanheng/strategy_v1/guanheng_strategy_v1'
    source = owner / 'diagnostics.py'
    profile = owner / 'role_profile.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    declarations = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ('SCHEMA', 'MARKET_FIELDS', 'BRANCH_FIELDS'):
                declarations[node.targets[0].id] = ast.literal_eval(node.value)
    roles = next(ast.literal_eval(node.value.args[0]) for node in ast.parse(profile.read_text(encoding='utf-8-sig')).body
                 if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ROLE_SYMBOLS' for t in node.targets))
    validator = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'validate_diagnostics')
    common = next(node.value for node in validator.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'common_roles' for t in node.targets))
    # 可替换角色由原验证器的common_roles排除条件拥有，生成工具不另设证券范围。
    condition = common.generators[0].ifs[0]
    if not (isinstance(condition, ast.Compare) and isinstance(condition.left, ast.Name)
            and condition.left.id == 'role' and len(condition.ops) == 1 and isinstance(condition.ops[0], ast.NotEq)):
        raise ValueError('V1角色线协议声明结构变化，请核实生成接缝')
    remaining_role = ast.literal_eval(condition.comparators[0])
    values = [
        ('schema', declarations['SCHEMA'], '唯一V1诊断线协议版本。'),
        ('owner_sha256', hashlib.sha256(source.read_bytes()).hexdigest(), '协议所有者源码摘要；生成校验绑定此身份。'),
        ('profile_sha256', hashlib.sha256(profile.read_bytes()).hexdigest(), '角色声明源码摘要；运行数学和策略版本保持原所有者。'),
        ('market_fields', declarations['MARKET_FIELDS'], '每角色必需的市场字段名，直接取V1声明。'),
        ('common_roles', {symbol: role for role, symbol in roles.items() if role != remaining_role}, '固定证券到角色的原映射；历史可替换角色按原验证器处理。'),
        ('remaining_role', remaining_role, '本轮其余一个证券归属的角色，兼容已归档物理证券。'),
        ('branches', declarations['BRANCH_FIELDS'], '每角色必需分支及字段顺序，直接取V1声明；无信号阈值或计算。'),
    ]
    lines = ['// 此文件由 scripts/generate-strategy-diagnostic-wire.py 生成；修改V1声明后重新生成并以--check核对。',
             'export const diagnosticWire = {']
    for name, value, comment in values:
        lines += ['  /** ' + comment + ' */', '  ' + name + ': ' + json.dumps(value, ensure_ascii=False, separators=(',', ':')) + ',']
    return '\n'.join(lines + ['} as const', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只核已提交元数据与当前协议源码身份一致')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root / 'apps/guanheng/console/src/workspace/strategyDiagnosticWire.generated.ts'
    content = render(root)
    if args.check:
        if not target.is_file() or target.read_text(encoding='utf-8') != content:
            raise SystemExit('策略诊断只读元数据已过期，请重新生成')
    else:
        target.write_text(content, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
