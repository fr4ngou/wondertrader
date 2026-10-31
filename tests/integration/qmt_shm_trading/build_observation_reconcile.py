"""显式固定工具链/包含路径的独立Common QA构建，不修改原安装或默认产品构建。"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
import native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'toolchain', 'compile-database'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--trade-source', type=Path)
    args = parser.parse_args(); work = args.work.resolve()
    if work.drive.upper() != 'E:' or not work.is_relative_to(ROOT/'build'):
        raise ValueError('explicit E build root required')
    work.mkdir(); temp=work/'temp'; temp.mkdir(); objects=work/'objects'; objects.mkdir()
    config=json.loads(args.toolchain.read_bytes()); env=config['environment'].copy()
    env.update(TEMP=str(temp),TMP=str(temp))
    entry=next(x for x in json.loads(args.compile_database.read_bytes()) if x['file'].endswith('StandardQmtTrader.cpp'))
    count=ctypes.c_int(); parse=ctypes.WinDLL('shell32').CommandLineToArgvW
    parse.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]; parse.restype=ctypes.POINTER(ctypes.c_wchar_p)
    vector=parse(entry['command'],ctypes.byref(count)); parts=[vector[i] for i in range(count.value)]
    ctypes.WinDLL('kernel32').LocalFree(vector)
    includes=[x for x in parts if x.startswith('-I')]+['/I'+str(ROOT/'src/GuanhengCommon')]
    names=['BoundedSignedHttp','QmtReadTransport','QmtHostReadClient','QmtHostCodec','QmtHostTradeClient',
           'QmtBoundReadCore','QmtHostHistoryClient','QmtHostAccountClient']
    inputs={}; sources=[]; sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    for name in names:
        source=args.trade_source if name=='QmtHostTradeClient' and args.trade_source else ROOT/'src/GuanhengCommon'/(name+'.cpp')
        raw=source.read_bytes(); inputs[str(source)]=sha(source)
        if name=='BoundedSignedHttp':
            constructor=b'BoundedSignedHttp::BoundedSignedHttp(QmtHttpConfig config) : impl_(new Impl(std::move(config))) {}'
            measured=(b'namespace { std::size_t qa_observation_http_impl_size=0; }\n'
                b'extern "C" __declspec(dllexport) std::size_t gh_qmt_observation_test_http_impl_size() noexcept '
                b'{ return qa_observation_http_impl_size; }\n'
                b'BoundedSignedHttp::BoundedSignedHttp(QmtHttpConfig config) : impl_(new Impl(std::move(config))) '
                b'{ qa_observation_http_impl_size=sizeof(Impl); }')
            assert raw.count(constructor)==1
            raw=raw.replace(constructor,measured)
        if name=='QmtBoundReadCore':
            constructor=b':impl_(new Impl(std::move(config),profile,control,expected)){}'
            assert raw.count(constructor)==1
            raw=raw.replace(constructor,b':impl_(new Impl(std::move(config),profile,control,expected)){ qa_observation_bound_impl_size=sizeof(Impl); }')
            marker=b'QmtBoundReadCore::QmtBoundReadCore(QmtHttpConfig config'
            measure=(b'namespace { std::size_t qa_observation_bound_impl_size=0; }\n'
                b'extern "C" __declspec(dllexport) std::size_t gh_qmt_observation_test_bound_impl_size() noexcept '
                b'{ return qa_observation_bound_impl_size; }\n')
            assert raw.count(marker)==1
            raw=raw.replace(marker,measure+marker)
        if name=='QmtHostTradeClient' and b'gh_qmt_trade_test_core_size' not in raw:
            raw+=b'\nextern "C" __declspec(dllexport) std::size_t gh_qmt_trade_test_core_size() noexcept { return sizeof(guanheng::QmtTradeClientCore); }\n'
        target=work/(name+'.cpp');target.write_bytes(raw);sources.append(str(target))
    probe=ROOT/'tests/integration/qmt_shm_trading/native_observation_reconcile.cpp';inputs[str(probe)]=sha(probe)
    cl=Path(env['VCTOOLSINSTALLDIR'])/'bin/Hostx64/x64/cl.exe'; dll=work/'observation_reconcile.dll'
    native.run([str(cl),'/nologo','/EHsc','/MD','/O2','/std:c++17','/utf-8','/LD','/DGH_QMT_HTTP_DRAIN_TESTING',
        '/DNOMINMAX','/DWIN32_LEAN_AND_MEAN',*includes,*sources,str(probe),'/Fo'+str(objects)+'/',
        '/Fe'+str(dll),'/link','bcrypt.lib','winhttp.lib'],cwd=work,env=env,timeout=180,
        log=work/'build.log',private_console=True)
    assert all(sha(Path(p))==h for p,h in inputs.items())
    (work/'RESULT.json').write_text(json.dumps(dict(passed=True,dll=str(dll),dll_sha256=sha(dll),
        source=inputs,SDK_calls=0,product_build=False),indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,SDK_calls=0)))


if __name__=='__main__':
    main()
