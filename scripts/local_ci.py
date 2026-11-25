"""本地CI：按改动运行已有检查，绑定源码结果，再快进合入本地master。"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from native_support.process_startup import background_process_options


def git(root, *args, data=None):
    """只调用本地Git；隐藏短命令窗口，原失败保留非零结果。"""
    result = subprocess.run(['git', '-C', str(root), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'},
                            **background_process_options())
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def snapshot(root):
    """沿Git索引记录源码，仅对实际修改/新增内容重新计算blob身份。"""
    files = {}
    for entry in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not entry:
            continue
        info, name = entry.split(b'\t', 1)
        mode, blob, stage = info.split()
        if stage != b'0':
            raise ValueError('请先解决Git合并冲突')
        files[os.fsdecode(name)] = mode.decode() + ':' + blob.decode()
    # HEAD到工作目录的净差异可能为零：暂存B后把工作文件改回A时，测试仍运行A。
    # 独立纳入索引到工作目录的差异，确保身份对应实际被执行内容。
    changed = set(git(root, 'diff', '--name-only', '-z', 'HEAD').split(b'\0'))
    changed.update(git(root, 'diff', '--name-only', '-z').split(b'\0'))
    changed.update(git(root, 'ls-files', '-z', '--others', '--exclude-standard').split(b'\0'))
    for raw in sorted(changed - {b''}):
        name = os.fsdecode(raw)
        path = root / name
        if not path.exists():
            files.pop(name, None)
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('变更路径应为普通源码文件：' + name)
        mode = files.get(name, '100644:').split(':')[0]
        data = path.read_bytes()
        # 旧Git blob的CRLF可能受新属性重复报告M；原字节等于索引时保留该真实blob身份。
        if name in files and data == git(root, 'cat-file', 'blob', files[name].split(':')[1]):
            continue
        blob = git(root, 'hash-object', '--path=' + name, '--stdin', data=data).decode().strip()
        files[name] = mode + ':' + blob
    encoded = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'sha256': hashlib.sha256(encoded).hexdigest(), 'files': files}


def changed_paths(root):
    """合入基线以来的改动加工作区差异；用于选择验证范围。"""
    base = git(root, 'merge-base', 'master', 'HEAD').decode().strip()
    changes = git(root, 'diff', '--name-only', '-z', base, 'HEAD')
    changes += git(root, 'diff', '--name-only', '-z', 'HEAD')
    changes += git(root, 'diff', '--name-only', '-z')
    changes += git(root, 'ls-files', '-z', '--others', '--exclude-standard')
    return sorted({os.fsdecode(p) for p in changes.split(b'\0') if p})


def profiles_for(paths):
    """文档只做文档检查；软件改动跑软件回归，执行相关改动追加真实执行链。"""
    if paths and all(p.endswith('.md') for p in paths):
        return ['documentation']
    profiles = ['software']
    execution_prefixes = ('src/', 'cmake/', 'connectors/qmt_shm/', 'config/native-reader-overlays/runtime/',
                          'integrations/wondertrader_execution/', 'integrations/wondertrader_stock_reference/',
                          'config/native-data-variants/parser_retained_v6/',
                          'tests/integration/qmt_broker_context/', 'tests/integration/wt_runtime/',
                          'tests/integration/qmt_polling_lifecycle/')
    if any(p.startswith(execution_prefixes) or p in (
            'scripts/execution_product.py', 'scripts/local_ci_execution.py',
            'config/execution-product-build.json', 'config/native-dependencies.json') for p in paths):
        profiles.append('execution')
    return profiles


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run_check(root, output, settings):
    import native
    output = output.resolve()
    # 防止CI生成自己的日志改变源码快照；不删除任何已有结果。
    if output.is_relative_to(root) and git(root, 'check-ignore', str(output.relative_to(root))).strip() == b'':
        raise ValueError('CI输出应放在build等已忽略目录或仓库外')
    output.mkdir(parents=True, exist_ok=False)
    # 部分既有软件回归在build下创建自己的临时目录；新worktree也应具备该父目录。
    (root / 'build').mkdir(exist_ok=True)
    print('CI: source identity', flush=True)
    before = snapshot(root)
    paths = changed_paths(root)
    config = json.loads((root / 'config/local-ci.json').read_bytes())
    selected = profiles_for(paths)
    receipt = {'schema': 1, 'status': 'running', 'source': before,
               'head': git(root, 'rev-parse', 'HEAD').decode().strip(),
               'master': git(root, 'rev-parse', 'master').decode().strip(),
               'profiles': selected, 'changed_paths': paths, 'stages': [],
               'python': {'executable': sys.executable, 'version': sys.version},
               'finished_at': None}  # UTC完成时间；失败也保留当前阶段及源码身份。
    receipt_path = output / 'RESULT.json'
    save(receipt_path, receipt)
    values = {'python': sys.executable, 'run': str(output), 'settings': str(settings)}
    completed = set()
    try:
        for profile in selected:
            for stage in config['profiles'][profile]:
                if stage['name'] in completed:
                    continue
                record = {'name': stage['name'], 'status': 'running', 'log': stage['name'] + '.log'}
                receipt['stages'].append(record)
                save(receipt_path, receipt)
                argv = [part.format(**values) for part in stage['argv']]
                # 源码回归优先导入本候选包，第三方依赖继续使用调用解释器的正常安装。
                env = dict(os.environ)
                source_roots = ('apps/guanheng', 'apps/wt_runtime', 'apps/analysis_window_producer',
                                'apps/guanheng/strategy_core', 'apps/guanheng/strategy_v1',
                                'apps/guanheng/strategy_native', 'apps/guanheng/strategy_original',
                                'packages/native-analysis-core', 'packages/observer-read-side/wt_runtime',
                                'packages/unified-daily-data', 'connectors/qmt_shm/host',
                                'connectors/qmt_shm/agent', 'integrations')
                env['PYTHONPATH'] = os.pathsep.join(str(root / p) for p in source_roots)
                env['PYTHONDONTWRITEBYTECODE'] = '1'
                env['PYTHONIOENCODING'] = 'utf-8'
                print('CI: ' + stage['name'], flush=True)
                with contextlib.redirect_stdout(io.StringIO()):
                    native.run(argv, cwd=root, env=env, timeout=stage['seconds'],
                               log=output / record['log'], private_console=True)
                record['status'] = 'passed'
                completed.add(stage['name'])
        if snapshot(root) != before:
            raise RuntimeError('CI期间源码发生变化，请对最终代码重新运行')
        receipt['status'] = 'passed'
    except BaseException as error:
        receipt['status'] = 'failed'
        receipt['error'] = type(error).__name__ + ': ' + str(error)
        if receipt['stages'] and receipt['stages'][-1]['status'] == 'running':
            receipt['stages'][-1]['status'] = 'failed'
        raise
    finally:
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        save(receipt_path, receipt)
    return receipt_path


def integrate(root, target, receipt_path):
    """合入已验的同一内容；只做本地快进，不提交、推送、发布或切换服务。"""
    receipt = json.loads(receipt_path.read_bytes())
    if receipt.get('schema') != 1 or receipt.get('status') != 'passed':
        raise ValueError('需要本地CI成功结果')
    current = snapshot(root)
    if current != receipt['source']:
        raise ValueError('当前源码与CI结果不一致，请重跑受影响检查')
    required = profiles_for(changed_paths(root))
    if required != receipt['profiles']:
        raise ValueError('当前改动范围与CI结果不一致')
    config = json.loads((root / 'config/local-ci.json').read_bytes())
    expected = {s['name'] for p in required for s in config['profiles'][p]}
    actual = {s['name'] for s in receipt['stages'] if s['status'] == 'passed'}
    if expected != actual or any(s['status'] != 'passed' for s in receipt['stages']):
        raise ValueError('CI阶段未全部通过')
    # 提交由开发者按明确文件清单完成；快进合入保留准确被测内容。
    untracked = git(root, 'ls-files', '-z', '--others', '--exclude-standard').strip(b'\0')
    modified = git(root, 'diff', '--name-only', '-z', 'HEAD').split(b'\0')
    actual_changes = []
    for raw in modified:
        if not raw:
            continue
        name = os.fsdecode(raw)
        path = root / name
        # Git属性变化可能给原字节完全相同的旧文件打M；原始内容相等时可复用。
        if not path.is_file() or path.read_bytes() != git(root, 'show', 'HEAD:' + name):
            actual_changes.append(name)
    staged = git(root, 'diff', '--cached', '--name-only', '-z', 'HEAD').strip(b'\0')
    if untracked or actual_changes or staged:
        raise ValueError('请先提交候选源码；CI支持先测试后提交，内容相同可复用结果')
    candidate = git(root, 'rev-parse', 'HEAD').decode().strip()
    # 快进指向不可变提交；核对该提交树，避免只验证可变索引/工作目录。
    committed = {}
    for entry in git(root, 'ls-tree', '-r', '--full-tree', '-z', candidate).split(b'\0'):
        if entry:
            info, name = entry.split(b'\t', 1)
            mode, kind, blob = info.split()
            committed[os.fsdecode(name)] = mode.decode() + ':' + blob.decode()
    if committed != receipt['source']['files']:
        raise ValueError('候选提交内容与已测试源码不一致')
    if git(target, 'branch', '--show-current').decode().strip() != 'master':
        raise ValueError('目标工作区应检出master')
    if git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir') != git(target, 'rev-parse', '--path-format=absolute', '--git-common-dir'):
        raise ValueError('候选与master须属于同一本地仓库')
    master = git(target, 'rev-parse', 'HEAD').decode().strip()
    if master != receipt['master']:
        raise ValueError('master已推进，请更新候选并重验')
    git(root, 'merge-base', '--is-ancestor', master, candidate)
    git(target, 'merge', '--ff-only', candidate)
    if git(target, 'rev-parse', 'HEAD').decode().strip() != candidate:
        raise RuntimeError('合入结果未指向被测提交')
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check')
    check.add_argument('--output', type=Path)
    check.add_argument('--settings', type=Path, default=ROOT / '.local-ci.json')
    merge = commands.add_parser('integrate')
    merge.add_argument('--master-worktree', type=Path, required=True)
    merge.add_argument('--receipt', type=Path, help='复用内容仍匹配的成功结果；省略时先自动运行CI')
    merge.add_argument('--settings', type=Path, default=ROOT / '.local-ci.json')
    merge.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'check':
        output = args.output or ROOT / 'build/local-ci' / uuid4().hex
        print(str(run_check(ROOT, output, args.settings.resolve())))
    else:
        receipt = args.receipt.resolve() if args.receipt else run_check(
            ROOT, args.output or ROOT / 'build/local-ci' / uuid4().hex, args.settings.resolve())
        print('local master: ' + integrate(ROOT, args.master_worktree.resolve(), receipt))


if __name__ == '__main__':
    main()
