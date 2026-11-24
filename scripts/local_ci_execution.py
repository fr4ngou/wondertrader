"""本地执行CI：复用已核工具/依赖源码，重新构建当前C++并跑隔离共享内存链。"""
from pathlib import Path
import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
from uuid import uuid4

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
    # 夹具的同步Journal和C++中间件可落到独立高速临时盘，报告仍归本次CI输出。
    workspace = output
    if 'execution_scratch' in settings:
        scratch = Path(settings['execution_scratch'])
        if not scratch.is_absolute() or not scratch.is_dir():
            raise ValueError('执行CI临时根必须是现有绝对目录')
        workspace = scratch.resolve() / ('wt-execution-' + uuid4().hex)
        workspace.mkdir(exist_ok=False)
    env = json.loads((seed / 'TOOLCHAIN.json').read_bytes())['environment']
    cmake = shutil.which('cmake.exe', path=env['PATH'])
    compiler = Path(shutil.which('cl.exe', path=env['PATH']))
    upstream = seed / 'inputs/upstream'
    upstream_identity = verify_snapshot(upstream)
    recipe = json.loads((ROOT / 'config/execution-product-build.json').read_bytes())
    old = json.loads((seed / 'SOURCE.json').read_bytes())
    if old['upstream_commit'] != recipe['upstream_commit'] or old['overlays'] != recipe['overlays']:
        raise ValueError('本地依赖基线与已批准框架覆盖不一致，请更新构建缓存')
    for overlay in recipe['overlays']:
        if hashlib.sha256((ROOT / overlay['path']).read_bytes()).hexdigest() != overlay['sha256']:
            raise ValueError('框架覆盖文件与构建配方不同：' + overlay['path'])
    for name, identity in recipe['patched_files'].items():
        runtime = ROOT / 'config/native-reader-overlays/runtime' / name
        if runtime.is_file() and hashlib.sha256(runtime.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != identity['normalized_result_sha256']:
            raise ValueError('当前框架覆盖源码与构建配方不同：' + name)
    # 使用原产品冻结函数创建当前源码副本；依赖源码缓存保持原位置。
    files = source_files(recipe)
    owned = workspace / 'inputs/owned'
    owned.parent.mkdir()
    # 相邻Includes等WT头也来自同一已批准快照，保持原产品构建的头文件布局。
    entries = dict(files)
    for name, identity in upstream_identity['files'].items():
        if name in entries:
            raise ValueError('自有源码与WT快照路径重复')
        entries[name] = {'sha256': identity['sha256'], 'data': (upstream / name).read_bytes()}
    write_snapshot(owned, entries)
    (output / 'TOOLCHAIN.json').write_bytes((seed / 'TOOLCHAIN.json').read_bytes())
    helper = workspace / 'helpers'
    helper.mkdir()
    shutil.copyfile(legacy / 'qmt_standard_trader/standard_probe.cpp', helper / 'standard_probe.cpp')
    # 外部C++帮助文件参与编译；冻结副本摘要须与结果一起留存，而非仅登记Python夹具。
    helper_sha256 = hashlib.sha256((helper / 'standard_probe.cpp').read_bytes()).hexdigest()
    build = workspace / 'cmake'

    def run(argv, label, seconds=300, *, environment=None):
        print('execution CI: ' + label, flush=True)
        with contextlib.redirect_stdout(io.StringIO()):
            native.run(argv, cwd=ROOT, env=env if environment is None else environment, timeout=seconds,
                       log=output / (label + '.log'), private_console=True)

    run([cmake, '-S', owned / recipe['source_cmake'], '-B', build, '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_COMPILER=' + str(compiler),
         '-DCMAKE_C_COMPILER=' + str(compiler), '-DCMAKE_MAKE_PROGRAM=' + shutil.which('ninja.exe', path=env['PATH']),
         '-DWT_DEPS_DIR=' + str(seed / 'deps'), '-DGH_FIXED_UPSTREAM_ROOT=' + str(upstream),
         '-DGH_FIXED_OWN_ROOT=' + str(owned), '-DPython3_EXECUTABLE=' + sys.executable], 'configure')
    run([cmake, '--build', build, '--target', recipe['target'], '--parallel', '2'], 'build', 600)
    run([sys.executable, '-I', '-B', ROOT / 'tests/integration/wt_runtime/check_execution_cache_startup.py',
         '--exe', build / 'bin/GuanhengCtaHost.exe', '--output', workspace / 'cache-startup'], 'cache-startup', 45)
    save_probe = workspace / 'native_state_save_probe.exe'
    run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/utf-8',
         '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/I' + str(owned / 'src'),
         owned / 'tests/integration/qmt_broker_context/native_state_save_probe.cpp',
         '/Fo' + str(workspace / 'native_state_save_probe.obj'), '/Fe' + str(save_probe)],
        'native-state-save-compile', 60)
    run([save_probe, workspace / 'native-state-save-files'], 'native-state-save', 30)
    source_probe = workspace / 'read_source_diagnostic_probe.exe'
    run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/utf-8',
         '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/I' + str(owned / 'src'),
         '/I' + str(seed / 'deps/rapidjson/include'),
         owned / 'tests/integration/qmt_broker_context/read_source_diagnostic_probe.cpp',
         '/Fo' + str(workspace / 'read_source_diagnostic_probe.obj'), '/Fe' + str(source_probe)],
        'read-source-diagnostic-compile', 60)
    run([source_probe], 'read-source-diagnostic', 30)
    fee_probe = workspace / 'trade_fee_probe.exe'
    run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/utf-8',
         '/I' + str(owned / 'src'), '/I' + str(seed / 'deps/rapidjson/include'),
         owned / 'tests/integration/qmt_broker_context/trade_fee_probe.cpp',
         '/Fo' + str(workspace / 'trade_fee_probe.obj'), '/Fe' + str(fee_probe)], 'trade-fee-compile', 60)
    run([fee_probe], 'trade-fee', 30)
    fee_env = dict(env, PYTHONPATH=os.pathsep.join(str(ROOT / path) for path in (
        'connectors/qmt_shm/agent', 'connectors/qmt_shm/host', str(legacy / 'qmt_shm_trading'))))
    run([sys.executable, '-B', '-m', 'pytest', ROOT / 'tests/integration/qmt_shm_account/test_current_fee_projection.py',
         ROOT / 'tests/integration/qmt_shm_trading/test_fee_profile_upgrade.py',
         '-q', '-p', 'no:cacheprovider', '--basetemp', workspace / 'fee-projection-temp'],
        'trade-fee-projection', 60, environment=fee_env)
    log_receipt = output / 'native-runtime-log'
    run([sys.executable, '-I', '-B', ROOT / 'tests/integration/native_runtime_log/run.py',
         '--build', seed, '--work', log_receipt], 'native-runtime-log', 120)
    includes = [owned / 'src', upstream / 'src', helper, seed / 'deps/rapidjson/include', seed / 'deps/spdlog/include',
                *list((seed / 'deps/boost/libs').glob('*/include')),
                *list((seed / 'deps/boost/libs/numeric').glob('*/include'))]
    probe = workspace / 'cancel_refresh_probe.exe'
    run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/O2', '/utf-8',
         '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/DBOOST_ALL_NO_LIB', '/D_CRT_SECURE_NO_WARNINGS',
         '/D_SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS', '/FIobjbase.h',
         *['/I' + str(p) for p in includes], '/c', owned / 'tests/integration/qmt_broker_context/cancel_refresh_probe.cpp',
         '/Fo' + str(workspace / 'probe.obj')], 'probe-compile')
    libraries = [build / 'lib/GuanhengBrokerQueryContext.lib', build / 'build_x64/Release/libs/WtCore.lib',
                 build / 'lib/WTSTools.lib', build / 'lib/WTSUtils.lib',
                 *list((build / 'product/readonly-support/deps/boost').rglob('*.lib'))]
    run([compiler.with_name('link.exe'), '/nologo', '/MACHINE:X64', '/OUT:' + str(probe), workspace / 'probe.obj',
         *libraries, 'winhttp.lib', 'bcrypt.lib', 'synchronization.lib', 'ws2_32.lib', 'psapi.lib',
         'dbghelp.lib', 'version.lib', 'user32.lib', 'shell32.lib', 'advapi32.lib', 'ole32.lib'], 'probe-link')
    fee_mapping = workspace / 'trade_fee_mapping.exe'
    run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/O2', '/utf-8',
         '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/DBOOST_ALL_NO_LIB', '/D_CRT_SECURE_NO_WARNINGS',
         '/D_SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS', '/FIobjbase.h',
         *['/I' + str(p) for p in includes], '/c', owned / 'tests/integration/qmt_broker_context/trade_fee_mapping_probe.cpp',
         '/Fo' + str(workspace / 'fee_mapping.obj')], 'trade-fee-mapping-compile')
    standard_link = (build / 'link-inputs/GuanhengStandardTrader.rsp').read_text(encoding='utf-16').splitlines()
    fee_objects = [Path(item.strip('"')) for item in standard_link
                   if item.strip('"').replace('\\', '/').endswith(('/AccountMapping.cpp.obj', '/EventDeliveryIndex.cpp.obj'))]
    if len(fee_objects) != 2:
        raise ValueError('费用映射回归需要本次真实mapper与交付索引对象')
    run([compiler.with_name('link.exe'), '/nologo', '/MACHINE:X64', '/OUT:' + str(fee_mapping),
         workspace / 'fee_mapping.obj', *fee_objects, *libraries, 'winhttp.lib', 'bcrypt.lib',
         'synchronization.lib', 'ws2_32.lib', 'psapi.lib', 'dbghelp.lib', 'version.lib',
         'user32.lib', 'shell32.lib', 'advapi32.lib', 'ole32.lib'], 'trade-fee-mapping-link')
    run([fee_mapping, workspace / 'trade-fee-mapping-files'], 'trade-fee-mapping', 30)
    model_source = helper / 'strategy_extension.cpp'
    shutil.copyfile(ROOT / 'tests/integration/strategy_extension/native_probe.cpp', model_source)
    model_source_sha = hashlib.sha256(model_source.read_bytes()).hexdigest()
    model_probe = workspace / 'strategy_extension.exe'
    model_object = workspace / 'strategy_extension.obj'
    run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/O2', '/utf-8',
         '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/DBOOST_ALL_NO_LIB', '/D_CRT_SECURE_NO_WARNINGS',
         '/D_SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS', '/FIobjbase.h',
         *['/I' + str(p) for p in includes], '/c', model_source, '/Fo' + str(model_object)], 'model-compile')
    # 复用本次真实运行库的链接依赖，仅用探针对象替换其 CtaProcess 对象。
    link_inputs = (build / 'link-inputs/GuanhengCtaRuntime.rsp').read_text(encoding='utf-16').splitlines()
    if not link_inputs or not link_inputs[0].strip('"').endswith('CtaProcess.cpp.obj'):
        raise ValueError('Native 模型探针需要本次运行库的固定链接清单')
    run([compiler.with_name('link.exe'), '/nologo', '/MACHINE:X64', '/OUT:' + str(model_probe),
         model_object, *[item.strip('"') for item in link_inputs[1:]]], 'model-link')
    model_env = dict(env)
    model_env['GH_STRATEGY_EXTENSION_PROBE'] = str(model_probe)
    model_env['PYTHONIOENCODING'] = 'utf-8'
    model_env['PYTHONPATH'] = os.pathsep.join(str(ROOT / path) for path in (
        'apps/wt_runtime', 'connectors/qmt_shm/host', 'connectors/qmt_shm/agent', 'integrations'))
    run([sys.executable, '-B', '-m', 'pytest', ROOT / 'tests/integration/strategy_extension/test_permission_storage.py',
         '-q', '-o', 'cache_dir=' + str(output / 'model-pytest-cache'),
         '--basetemp', workspace / 'model-pytest-temp', '--junitxml', output / 'model-junit.xml'],
        'model-regression', 90, environment=model_env)
    source_results = []
    polling_receipt = output / 'polling-lifecycle'
    run([sys.executable, '-I', '-B', ROOT / 'tests/integration/qmt_polling_lifecycle/run.py',
         '--work', polling_receipt, '--build', seed], 'polling-lifecycle', 240)
    core_receipt = output / 'polling-core-revalidation'
    run([sys.executable, '-I', '-B', ROOT / 'tests/integration/qmt_polling_lifecycle/core.py',
         '--work', core_receipt, '--build', seed], 'polling-core-revalidation', 180)
    for scenario, boundary in (('session', 'next-task'), ('authentication', 'next-task'),
                               ('authentication', 'pre-submit'), ('lost-read-response', 'next-task'),
                               ('stable-binding', 'next-task'), ('invalid-binding', 'next-task')):
        label = 'read-source-' + scenario + ('-pre-submit' if boundary=='pre-submit' else '')
        directory = workspace / label
        run([sys.executable, '-I', '-B', ROOT / 'tests/integration/qmt_read_source_diagnostics/run_native_source.py',
             '--source', ROOT, '--legacy-fixtures', legacy, '--candidate-app', build / 'bin',
             '--toolchain', seed / 'TOOLCHAIN.json', '--output', directory, '--scenario', scenario,
             '--switch-boundary', boundary], label, 90)
        receipt = json.loads((directory / 'RESULT.json').read_bytes())
        if receipt.get('passed') is not True:
            raise ValueError('Native读取来源诊断未通过：' + scenario)
        source_results.append(dict(scenario=scenario, switch_boundary=boundary, receipt=str(directory / 'RESULT.json')))
    results = []
    for scenario in ('cancel-false', 'cancel-error', 'partial', 'missing-current', 'account-rejected',
                     'account-result-unavailable', 'account-frontend', 'event-rejected'):
        directory = workspace / scenario
        run([sys.executable, '-I', '-B', ROOT / 'tests/integration/qmt_broker_context/run_cancel_refresh.py',
             '--legacy-fixtures', legacy, '--exe', probe, '--dll', build / 'bin/traders/TraderQMTStandard.dll',
             '--factory', build / 'bin/executers/WtExeFact.dll', '--scenario', scenario, '--output', directory], scenario, 65)
        result = json.loads((directory / 'RESULT.json').read_bytes())
        if result['passed'] is not True:
            raise ValueError('执行链未通过：' + scenario)
        results.append({'scenario': scenario, 'outcome': result['case_outcome'], 'receipt': str(directory / 'RESULT.json')})
    verify_snapshot(owned)
    verify_snapshot(upstream)
    if hashlib.sha256((helper / 'standard_probe.cpp').read_bytes()).hexdigest() != helper_sha256:
        raise ValueError('冻结的C++测试夹具在编译或运行期间发生变化')
    if hashlib.sha256(model_source.read_bytes()).hexdigest() != model_source_sha:
        raise ValueError('Native 模型探针源码在验证期间发生变化')
    (output / 'RESULT.json').write_text(json.dumps({'passed': True, 'cases': results, 'read_source_diagnostics': source_results, 'workspace': str(workspace),
        'polling_lifecycle': {'passed': True, 'receipt': str(polling_receipt / 'RESULT.json')},
        'polling_core_revalidation': {'passed': True, 'receipt': str(core_receipt / 'RESULT.json')},
        'native_state_save': {'passed': True, 'log': str(output / 'native-state-save.log')},
        'trade_fee': {'passed': True, 'log': str(output / 'trade-fee.log'),
                      'source_projection_log': str(output / 'trade-fee-projection.log'),
                      'mapper_log': str(output / 'trade-fee-mapping.log')},
        'native_runtime_log': {'passed': True, 'receipt': str(log_receipt / 'RESULT.json')},
        'permission_storage': {'passed': True, 'source_sha256': model_source_sha,
                               'log': str(output / 'model-regression.log')},
        'cache_startup': {'passed': True, 'log': str(output / 'cache-startup.log')},
        'cpp_fixture': {'path': str(helper / 'standard_probe.cpp'), 'sha256': helper_sha256},
        'standard_source_sha256': hashlib.sha256((owned / 'src/TraderQMT/StandardQmtTrader.cpp').read_bytes()).hexdigest(),
        'real_broker_calls': 0, 'historical_reconciliation_qualified': False,
        'business_strategy_qualified': False}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
