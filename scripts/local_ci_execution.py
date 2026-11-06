"""本地执行CI：复用已核工具/依赖源码，重新构建当前C++并跑隔离共享内存链。"""
from pathlib import Path
import argparse
import contextlib
import hashlib
import io
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native
from execution_product import source_files
from native_support.qmt_readonly_fixed import verify_snapshot, write_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(args.settings.read_bytes())
    seed = Path(settings['execution_inputs']).resolve()
    legacy = Path(settings['legacy_fixtures']).resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = json.loads((seed / 'TOOLCHAIN.json').read_bytes())['environment']
    cmake = shutil.which('cmake.exe', path=env['PATH'])
    compiler = Path(shutil.which('cl.exe', path=env['PATH']))
    upstream = seed / 'inputs/upstream'
    upstream_identity = verify_snapshot(upstream)
    recipe = json.loads((ROOT / 'config/execution-product-build.json').read_bytes())
    old = json.loads((seed / 'SOURCE.json').read_bytes())
    if old['upstream_commit'] != recipe['upstream_commit'] or old['overlays'] != recipe['overlays']:
        raise ValueError('本地依赖基线与已批准框架覆盖不一致，请更新构建缓存')
    # 使用原产品冻结函数创建当前源码副本；依赖源码缓存保持原位置。
    files = source_files(recipe)
    owned = output / 'inputs/owned'
    owned.parent.mkdir()
    # 相邻Includes等WT头也来自同一已批准快照，保持原产品构建的头文件布局。
    entries = dict(files)
    for name, identity in upstream_identity['files'].items():
        if name in entries:
            raise ValueError('自有源码与WT快照路径重复')
        entries[name] = {'sha256': identity['sha256'], 'data': (upstream / name).read_bytes()}
    write_snapshot(owned, entries)
    (output / 'TOOLCHAIN.json').write_bytes((seed / 'TOOLCHAIN.json').read_bytes())
    helper = output / 'helpers'
    helper.mkdir()
    shutil.copyfile(legacy / 'qmt_standard_trader/standard_probe.cpp', helper / 'standard_probe.cpp')
    build = output / 'cmake'

    def run(argv, label, seconds=300):
        print('execution CI: ' + label, flush=True)
        with contextlib.redirect_stdout(io.StringIO()):
            native.run(argv, cwd=ROOT, env=env, timeout=seconds,
                       log=output / (label + '.log'), private_console=True)

    run([cmake, '-S', owned / recipe['source_cmake'], '-B', build, '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_COMPILER=' + str(compiler),
         '-DCMAKE_C_COMPILER=' + str(compiler), '-DCMAKE_MAKE_PROGRAM=' + shutil.which('ninja.exe', path=env['PATH']),
         '-DWT_DEPS_DIR=' + str(seed / 'deps'), '-DGH_FIXED_UPSTREAM_ROOT=' + str(upstream),
         '-DGH_FIXED_OWN_ROOT=' + str(owned), '-DPython3_EXECUTABLE=' + sys.executable], 'configure')
    run([cmake, '--build', build, '--target', recipe['target'], '--parallel', '2'], 'build', 600)
    includes = [owned / 'src', upstream / 'src', helper, seed / 'deps/rapidjson/include', seed / 'deps/spdlog/include',
                *list((seed / 'deps/boost/libs').glob('*/include')),
                *list((seed / 'deps/boost/libs/numeric').glob('*/include'))]
    probe = output / 'cancel_refresh_probe.exe'
    run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/O2', '/utf-8',
         '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/DBOOST_ALL_NO_LIB', '/D_CRT_SECURE_NO_WARNINGS',
         '/D_SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS', '/FIobjbase.h',
         *['/I' + str(p) for p in includes], '/c', owned / 'tests/integration/qmt_broker_context/cancel_refresh_probe.cpp',
         '/Fo' + str(output / 'probe.obj')], 'probe-compile')
    libraries = [build / 'lib/GuanhengBrokerQueryContext.lib', build / 'build_x64/Release/libs/WtCore.lib',
                 build / 'lib/WTSTools.lib', build / 'lib/WTSUtils.lib',
                 *list((build / 'product/readonly-support/deps/boost').rglob('*.lib'))]
    run([compiler.with_name('link.exe'), '/nologo', '/MACHINE:X64', '/OUT:' + str(probe), output / 'probe.obj',
         *libraries, 'winhttp.lib', 'bcrypt.lib', 'synchronization.lib', 'ws2_32.lib', 'psapi.lib',
         'dbghelp.lib', 'version.lib', 'user32.lib', 'shell32.lib', 'advapi32.lib', 'ole32.lib'], 'probe-link')
    results = []
    for scenario in ('cancel-false', 'cancel-error', 'partial', 'missing-current'):
        directory = output / scenario
        run([sys.executable, '-I', '-B', ROOT / 'tests/integration/qmt_broker_context/run_cancel_refresh.py',
             '--legacy-fixtures', legacy, '--exe', probe, '--dll', build / 'bin/traders/TraderQMTStandard.dll',
             '--factory', build / 'bin/executers/WtExeFact.dll', '--scenario', scenario, '--output', directory], scenario, 65)
        result = json.loads((directory / 'RESULT.json').read_bytes())
        if result['passed'] is not True:
            raise ValueError('执行链未通过：' + scenario)
        results.append({'scenario': scenario, 'outcome': result['case_outcome']})
    verify_snapshot(owned)
    verify_snapshot(upstream)
    (output / 'RESULT.json').write_text(json.dumps({'passed': True, 'cases': results,
        'standard_source_sha256': hashlib.sha256((owned / 'src/TraderQMT/StandardQmtTrader.cpp').read_bytes()).hexdigest(),
        'real_broker_calls': 0, 'historical_reconciliation_qualified': False,
        'business_strategy_qualified': False}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
