"""从实际retained发行闭包构建行情等待回归，Common读取为无网络替身。"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    work, build = args.work.resolve(), args.build.resolve()
    work.mkdir(parents=True, exist_ok=False)
    stage = work / 'source'
    stage.mkdir()
    for name in ('Includes', 'Share', 'FasterLibs'):
        shutil.copytree(ROOT / 'src' / name, stage / name)
    variant = ROOT / 'config/native-data-variants/parser_retained_v6/src'
    for name in ('GuanhengCommon', 'GuanhengData'):
        shutil.copytree(variant / name, stage / name)
    shutil.copyfile(Path(__file__).with_name('probe.cpp'), stage / 'probe.cpp')
    env = json.loads((build / 'TOOLCHAIN.json').read_bytes())['environment']
    compiler = shutil.which('cl.exe', path=env['PATH'])
    linker = shutil.which('link.exe', path=env['PATH'])
    assert compiler and linker
    includes = [stage, build / 'deps/rapidjson/include', build / 'deps/spdlog/include',
                *list((build / 'deps/boost/libs').glob('*/include'))]
    flags = ['/nologo', '/std:c++17', '/EHsc', '/MD', '/O1', '/utf-8', '/DNOMINMAX',
             '/DWIN32_LEAN_AND_MEAN', '/DBOOST_ALL_NO_LIB', '/D_CRT_SECURE_NO_WARNINGS',
             '/FIobjbase.h', *['/I' + str(p) for p in includes]]
    names = ['probe.cpp', 'GuanhengData/QmtPollingParser.cpp', 'GuanhengData/MarketParser.cpp',
             'GuanhengData/QmtHttpEndpoint.cpp', 'GuanhengData/QmtHttpClient.cpp',
             'GuanhengData/QmtTickMapping.cpp', 'GuanhengCommon/QmtReadTransport.cpp',
             'GuanhengCommon/BoundedSignedHttp.cpp', 'GuanhengData/QmtHostEndpoint.cpp']
    objects = []
    for n, name in enumerate(names):
        obj = work / (str(n) + '.obj')
        objects.append(obj)
        native.run([compiler, *flags, '/c', stage / name, '/Fo' + str(obj)], env=env,
                   cwd=work, log=work / (str(n) + '.log'), timeout=60, private_console=True)
    exe = work / 'probe.exe'
    native.run([linker, '/nologo', '/out:' + str(exe), *objects, 'winhttp.lib', 'bcrypt.lib',
                'rpcrt4.lib', 'ole32.lib', 'ws2_32.lib'], env=env, cwd=work,
               log=work / 'link.log', timeout=60, private_console=True)
    native.run([exe], env=env, cwd=work, log=work / 'run.log', timeout=30, private_console=True)
    result = dict(passed=True, cases=[json.loads(line) for line in (work / 'run.log').read_text().splitlines()
                                    if line.startswith('{')],
                  source_sha256={name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in names},
                  qualification='Actual retained HostEndpoint/MarketParser/PollingParser; synthetic Common results; no broker or production calls')
    assert len(result['cases']) == 12
    (work / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
