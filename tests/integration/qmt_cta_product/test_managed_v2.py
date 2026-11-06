"""可选九标的桥：实际Native证据由显式隔离制品路径启用。"""
from __future__ import annotations

import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


def _api():
    from guanheng_wt_runtime import execution_strategy
    return execution_strategy


def test_binding_capacity_and_legacy_layout():
    api = _api()
    symbols = tuple('SSE.ETF.' + str(510300 + n) for n in range(10))
    callback = lambda context: None
    old = api.StrategyBinding('old', symbols[0], symbols[:8], symbols[:8], callback)
    assert old.native_config_abi == 1
    assert C.sizeof(api._Config) == 1680 and api._Config.execution_symbols.offset == 1168
    assert C.sizeof(api._ConfigV2) == 1744 and api._ConfigV2.execution_symbols.offset == 1168
    with pytest.raises(api.CtaBridgeError):
        api.StrategyBinding('old', symbols[0], symbols[:9], symbols[:9], callback)
    api.StrategyBinding('new', symbols[0], symbols[:9], symbols[:9], callback, native_config_abi=2)
    api.StrategyBinding('read', symbols[0], symbols[:9], (), callback, native_config_abi=2)
    for version in (0, True, 3):
        with pytest.raises(api.CtaBridgeError):
            api.StrategyBinding('new', symbols[0], symbols[:9], symbols[:9], callback, native_config_abi=version)
    with pytest.raises(api.CtaBridgeError):
        api.StrategyBinding('new', symbols[0], symbols, symbols, callback, native_config_abi=2)


@pytest.mark.parametrize('case', ('normal', 'partial', 'legacy', 'missing-v2'))
def test_actual_native_contexts(tmp_path, case):
    required = ('GH_MANAGED_V2_DLL', 'GH_MANAGED_V2_PROBE', 'GH_MANAGED_RUNTIME_DLL')
    if not all(os.environ.get(key) for key in required):
        pytest.skip('requires explicitly built isolated Native strategy/probe/runtime')
    if case in ('legacy', 'missing-v2') and not os.environ.get('GH_MANAGED_LEGACY_DLL'):
        pytest.skip('requires explicit legacy native artifact')
    env=dict(os.environ, GH_MANAGED_V2_CASE=case)
    result = subprocess.run([sys.executable, '-B', __file__, str(tmp_path)],
                            capture_output=True, text=True, timeout=60, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((tmp_path / 'ACTUAL-NATIVE.json').read_text())['passed']


def _native_main(root):
    import shutil
    api = _api()
    from guanheng_wt_runtime.execution_process import ExecutionProcessConfig
    case=os.environ.get('GH_MANAGED_V2_CASE','normal')
    app = root / 'installation/app';(app / 'strategies').mkdir(parents=True)
    library=os.environ['GH_MANAGED_LEGACY_DLL'] if case in ('legacy','missing-v2') else os.environ['GH_MANAGED_V2_DLL']
    shutil.copyfile(library, app / 'strategies/GuanhengManagedStrategy.dll')
    shutil.copyfile(os.environ['GH_MANAGED_RUNTIME_DLL'], app / 'GuanhengCtaRuntime.dll')
    files = tuple((p.relative_to(app.parent).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
                  for p in app.rglob('*.dll'))
    codes = ('510300', '510050', '510500', '512100', '515080', '588000', '589680', '159780', '159352')
    symbols = tuple(('SZSE' if c.startswith('159') else 'SSE') + '.ETF.' + c for c in codes)
    legacy_symbols=tuple('SSE.ETF.588030' if c=='SSE.ETF.589680' else c for c in symbols[:8])
    reads=tuple(dict.fromkeys((*symbols,*legacy_symbols)))
    names = ('legacy8',) if case=='legacy' else ('original9',) if case in ('partial','missing-v2') else ('legacy8', 'original9', 'readonly9')
    configuration = root / 'execution.json'
    configuration.write_text(json.dumps(dict(schema_version='guanheng.cta-execution.v1',
        installation_root=str(app), strategies=[dict(id=n, module='strategies/GuanhengManagedStrategy.dll',
            factory='GuanhengManagedStrategy', name='Core') for n in names])), encoding='utf-8')
    config = ExecutionProcessConfig(app.parent, configuration, hashlib.sha256(configuration.read_bytes()).hexdigest(),
                                    root, 20, 8, files)
    events, values, rejected, contexts, ctx_ids = [], {}, [], [], {}
    runtime = None
    def reject(call, reason):
        try:call()
        except api.CtaBridgeError:rejected.append(reason)
        else:raise AssertionError('expected rejection: '+reason)
    def callback(context):
        event=context.event;name=context._binding.strategy_id
        ctx_ids[name]=event.ctx_id
        events.append((name, event.kind))
        contexts.append(context)
        if event.kind == 1:
            assert len(context.bars(symbols[0], 'm1', 1, main=True)) == 1
            reject(lambda:context.set_targets(()),'phase')
        elif event.kind == 4:
            own=legacy_symbols if name=='legacy8' else symbols
            count=len(own)
            multiplier=1 if name=='legacy8' else 2
            vector=tuple((code,100*multiplier*(index+1)) for index,code in enumerate(own))
            before=runtime.status()['setters']
            if name=='readonly9':
                reject(lambda:context.set_targets(vector),'readonly')
                assert runtime.status()['setters']==before
                return
            if case=='normal':
                reject(lambda:context.set_targets(vector[:-1]),'missing')
                reject(lambda:context.set_targets((*vector[:-1],vector[0])),'duplicate')
                raw=(api.Target*count)();out=(api.Target*count)()
                for i,(code,qty) in enumerate(vector):raw[i].symbol=code.encode();raw[i].quantity=qty
                def native():return runtime._api.gh_ms_set_targets(event.epoch,raw,count,out,count)
                raw[-1].quantity=float('nan');assert native()==-1
                raw[-1].quantity=vector[-1][1];raw[-1].symbol=b'SSE.ETF.999999';assert native()==-1
                raw[-1].symbol=raw[0].symbol;assert native()==-1
                raw[-1].symbol=vector[-1][0].encode()
                assert runtime._api.gh_ms_set_targets(event.epoch,raw,count,out,count+1)==-7
                assert runtime._api.gh_ms_set_targets(0,raw,count,out,count)==-4
                import threading
                foreign=[]
                t=threading.Thread(target=lambda:foreign.append(native()));t.start();t.join(2)
                assert not t.is_alive() and foreign==[-4]
                assert runtime.status()['setters']==before
                rejected.extend(('native-invalid','capacity','stale-epoch','thread'))
            if case=='partial':
                reject(lambda:context.set_targets(vector),'partial')
                after=runtime.status()['setters'];assert after==before+2
                reject(lambda:context.set_targets(vector),'failure-latched')
                assert runtime.status()['setters']==after
                return
            result=context.set_targets(vector)
            assert dict(result)==dict(vector)
            assert runtime.status()['setters']==before+count
            for code,qty in vector:assert context.position(code).enum_target==qty
            values[name]=dict(result)
    bindings=tuple(api.StrategyBinding(name,symbols[0],reads,
        () if name=='readonly9' else legacy_symbols if name=='legacy8' else symbols,callback,
        native_config_abi=1 if name=='legacy8' else 2) for name in names)
    if case=='missing-v2':
        try:api.CtaRuntime(config,bindings,deadline=time.monotonic()+20)
        except api.CtaBridgeError as error:assert str(error)=='configuration_v2_capability'
        else:raise AssertionError('legacy native accepted V2')
        native=C.CDLL(str(app/'strategies/GuanhengManagedStrategy.dll'))
        status=api._Status();status.size=C.sizeof(status)
        assert native.gh_ms_status(C.byref(status))==0
        assert status.configured==status.created==status.setters==status.failure==0
        (root/'ACTUAL-NATIVE.json').write_text(json.dumps(dict(passed=True,case=case,configured=0,setters=0)),encoding='utf-8')
        return
    runtime=api.CtaRuntime(config,bindings,deadline=time.monotonic()+20)
    assert runtime._api.gh_ms_abi_version()==1 and runtime._api.gh_ms_layout(9)==0
    probe=C.CDLL(os.environ['GH_MANAGED_V2_PROBE'])
    run=probe.gh_managed_v2_probe
    run.argtypes=[C.c_char_p,C.c_char_p,C.POINTER(C.c_char_p),C.c_uint32];run.restype=C.c_int
    if case=='partial':probe.gh_managed_v2_probe_fault(2)
    ids=(C.c_char_p*len(names))(*(n.encode() for n in names))
    output=root/'native-output';output.mkdir()
    rc=run(str(app/'strategies/GuanhengManagedStrategy.dll').encode(),(str(output)+'/').encode(),ids,len(names))
    assert rc==0, (rc,runtime._last_error)
    assert runtime._last_error is None
    status=runtime.status()
    expected_setters=2 if case=='partial' else 8 if case=='legacy' else 17
    assert status['created']==status['destroyed']==len(names) and status['setters']==expected_setters
    assert status['failure']==(-5 if case=='partial' else 0)
    if case=='normal':assert len(values['legacy8'])==8 and len(values['original9'])==9 and 'readonly' in rejected
    if case=='legacy':assert len(values['legacy8'])==8
    assert len(set(ctx_ids.values()))==len(names)
    read=probe.gh_managed_v2_probe_target
    read.argtypes=[C.c_char_p,C.c_char_p];read.restype=C.c_double
    for name,targets in values.items():
        for code,qty in targets.items():assert read(name.encode(),code.encode())==qty
    for context in contexts:reject(context.facts,'expired-context')
    (root/'ACTUAL-NATIVE.json').write_text(json.dumps(dict(passed=True,case=case,events=events,ctx_ids=ctx_ids,targets=values,
        status=status,rejections=rejected,qualification='actual CtaRuntime/Factory/CtaStraContext; synthetic bars/quotes, direct native schedule, no ticker/executor/broker',
        source_requests=0,orders=0),indent=2),encoding='utf-8')


if __name__ == '__main__':
    _native_main(Path(sys.argv[1]))
