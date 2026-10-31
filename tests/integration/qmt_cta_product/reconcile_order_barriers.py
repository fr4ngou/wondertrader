"""编译并执行真实收束helper的定向原红/新绿；不启动SDK或产品实例。"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import native

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    args.output.mkdir(parents=True)
    env, _ = native.environment(args.output)
    compiler = shutil.which('cl.exe', path=env['PATH'])
    assert compiler
    template_path = Path(__file__).with_suffix('.cpp')
    template = template_path.read_text(encoding='utf-8')
    deadline = time.monotonic() + 90
    results = []
    for label, source in [('before', args.before), ('after', args.after)]:
        cpp = source / 'src/GuanhengExecution/CtaProcess.cpp'
        header = source / 'src/TraderQMT/StandardQmtTrader.h'
        text = cpp.read_text(encoding='utf-8')
        start = text.index('bool own_orders_empty(')
        end = text.index('void bootstrap_takeover(', start)
        helpers = text[start:end]
        struct = re.search(r'struct StandardQmtRecoveryV1\s*\{.*?\n\};', header.read_text(encoding='utf-8'), re.S).group()
        patched = 'last_account_query' in struct
        fixture = template.replace('// @@RECOVERY_STRUCT@@', struct).replace('// @@REAL_HELPERS@@', helpers)
        fixture = fixture.replace('// @@OLD_ACCOUNT@@', 'state.last_account_query = 42;' if patched else '')
        fixture = fixture.replace('// @@NEW_ACCOUNT@@', 'state.last_account_query = waiting_id;' if patched else '')
        invocation = 'reconcile_own_orders(execution, check, advance);' if patched else 'reconcile_own_orders(execution, advance);'
        fixture = fixture.replace('// @@INVOKE@@', invocation)
        path = args.output / (label + '.cpp')
        path.write_text(fixture, encoding='utf-8')
        exe = args.output / (label + '.exe')
        native.run([compiler, '/nologo', '/std:c++17', '/EHsc', '/W4', '/O2', '/MD',
            '/Fo' + str(args.output / (label + '.obj')), '/Fe' + str(exe), str(path),
            '/link', '/machine:x64', '/INCREMENTAL:NO'], cwd=args.output, env=env,
            log=args.output / (label + '-build.log'), timeout=max(.1, deadline-time.monotonic()), private_console=True)
        failed = False
        try:
            native.run([exe], cwd=args.output, env=env, log=args.output / (label + '-run.log'),
                timeout=max(.1, deadline-time.monotonic()), private_console=True)
        except RuntimeError:
            failed = True
        log = (args.output / (label + '-run.log')).read_text(encoding='utf-8')
        verdicts = {name:bool(re.search(r'^'+name+r' PASS$', log, re.M))
            for name in ('late_order', 'late_position', 'late_cancel', 'old_account')}
        assert failed == (label == 'before') and all(verdicts.values()) == (label == 'after')
        assert ('recovery_size ' + ('64' if label == 'before' else '72')) in log
        results.append(dict(label=label,source_root=str(source),source_sha256=sha256(cpp.read_bytes()).hexdigest(),
            header_sha256=sha256(header.read_bytes()).hexdigest(),fixture_sha256=sha256(path.read_bytes()).hexdigest(),
            verdicts=verdicts,expected_failure=failed))
    result = dict(passed=True,scope='actual reconciliation helper, controlled deadline and old ACCOUNT delivery',
        results=results,SDK_calls=0,real_orders=0,real_cancels=0)
    (args.output/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
