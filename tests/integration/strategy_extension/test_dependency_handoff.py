"""显式依赖续接→真实Native比较/准入；Source版本来自合成原Journal owner。"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json,sqlite3,sys,time
import pytest
from guanheng_wt_runtime import execution_recovery as recovery
from guanheng_wt_runtime.execution_dependency_handoff import ADDITIONS,TRANSPORT
import test_strategy_extension as base


@pytest.fixture(scope='module',params=[False,True],ids=['ascii','utf8'])
def source_versions(tmp_path_factory,request):
    """原Source owner在合成库实际prepare/adopt，未生成任何生产Source收据。"""
    location=tmp_path_factory.mktemp('source-owner')
    source_tests=Path(__file__).parents[1]/'qmt_shm_trading'
    sys.path.insert(0,str(source_tests))
    import test_trade_binding_extension as source
    from guanheng_qmt_shm.trading_journal import HostTradingJournal
    from guanheng_qmt_shm.trade_binding_extension import _profile
    path,route,kw=source.make(location)
    old=deepcopy(kw['trade_binding']);rule=deepcopy(old['symbol_rules'][source.OLD])
    if request.param:old['strategy_name']='合成原策略'
    symbols=['159780.SZ','510050.SH','510300.SH','510500.SH','512100.SH','515080.SH','588000.SH','588030.SH','589680.SH','588120.SH']
    old['symbol_rules']={s:deepcopy(rule)for s in symbols}
    kw.update(trade_binding=old,read_profile=_profile(kw['read_profile'],old,kw['max_result_bytes']))
    owner=HostTradingJournal(path,route,**kw)
    saved=source.seed(owner,route,kw,56);owner.close()
    owner=source.maintain(path,route,kw)
    try:
        new=deepcopy(old);new['symbol_rules']['159352.SZ']=dict(rule,sell_min=1,sell_step=1);changes={}
        for symbol in symbols:
            if symbol=='588120.SH':continue
            before=deepcopy(new['symbol_rules'][symbol]);new['symbol_rules'][symbol].update(sell_min=1,sell_step=1)
            changes[symbol]=dict(before=before,after=deepcopy(new['symbol_rules'][symbol]),security_type='ETF',security_reference_sha256='c'*64)
        plan=owner.prepare_binding_extension(new,'d'*64,changes,deadline=source.end())
        receipt=owner.adopt_binding_extension(plan,deadline=source.end())
        assert all(owner.get_trade(r['command_id'],deadline=source.end())==r for r in saved)
    finally:owner.close()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)as db:
        rows=db.execute('SELECT version,value,sha256 FROM trade_binding_versions ORDER BY version').fetchall()
    refs={}
    for version,raw,h in rows:
        assert sha256(raw).hexdigest()==h
        p=location/('version-%d.json'%version);p.write_bytes(raw);refs[version]=dict(file=str(p),sha256=h)
    refs['receipt']=base.put(location/'adoption.json',receipt)
    p=location/'plan.json';p.write_bytes(source.canonical(plan))
    refs['plan']=dict(file=str(p),sha256=sha256(p.read_bytes()).hexdigest())
    from guanheng_qmt_shm.trade_deployment_identity import reference_deployment_identity
    deployment=dict(schema_version='qmt.trade-deployment.v1',host=dict(journal_path=str(path),trade_binding=old),
        credentials=dict(ipc_secret_hex='a'*64,http_keys={'synthetic':'b'*64}),reconnect_seconds=1,
        connection_continuity=source.CONTINUITY_VERSION)
    deployment_raw=source.canonical(deployment);p=location/'deployment.json';p.write_bytes(deployment_raw)
    refs['deployment']=dict(file=str(p),sha256=sha256(deployment_raw).hexdigest())
    refs['identity']=base.put(location/'origin-identity.json',reference_deployment_identity(deployment_raw))
    return dict(old=old,new=new,refs=refs,commands=56,journal_sha256=sha256(path.read_bytes()).hexdigest())


def fixture(root,source):
    from guanheng_qmt_shm_agent.protocol import canonical as source_canonical
    old,current=base.fixture(root)
    old['installation_root']=str(root/'previous-install/app')
    old['environment']=dict(filters='retired-role-filter.json',fees='fees.json')
    rows=[dict(std_code=('SZSE'if s.endswith('.SZ')else'SSE')+'.ETF.'+s[:6],symbol=s)
          for s in ('159780.SZ','510050.SH','510300.SH','510500.SH','512100.SH','515080.SH','588000.SH','588030.SH')]
    old['data']=dict(store=dict(module='GuanhengRealtimeReader',symbols=rows,timeout_ms=5000))
    old['base_data']={k:k+'.json'for k in ('sessions','commodities','contracts','holidays','policy')}
    old['trader'].update(expected_account='SYNTHETIC',environment='simulation',profile='cny_cash_shsz_v1',
        binding_id=source['old']['binding_id'],binding_sha256=sha256(source_canonical(source['old'])).hexdigest(),
        base_url='http://127.0.0.1:19001',instance_id='a'*32,key_id_env='OLD_KEY',hmac_secret_env='OLD_SECRET',max_rows=256)
    addition=dict(exchg='SZSE',expiredate=20991231,name='synthetic approved ETF',opendate=20241015,product='ETF')
    contracts=dict(SSE={'589680':dict(exchg='SSE',expiredate=20991231,name='existing',opendate=20250305,product='ETF')},
        SZSE={'159780':dict(exchg='SZSE',expiredate=20991231,name='existing',opendate=20000101,product='ETF')})
    artifacts={}
    for which in ('previous','current'):
        app=root/(which+'-install')/'app';app.mkdir(parents=True)
        files={}
        for key,name in old['base_data'].items():
            value=deepcopy(contracts)if key=='contracts'else dict(business=key,original_fee='5')
            if key=='contracts'and which=='current':value['SZSE']['159352']=addition
            p=app/name;base.put(p,value);files['app/'+name]=sha256(p.read_bytes()).hexdigest()
        p=app/'retired-role-filter.json';base.put(p,dict(code_filters={'SSE.ETF.589680':dict(action='ignore')}));files['app/'+p.name]=sha256(p.read_bytes()).hexdigest()
        p=app/'fees.json';base.put(p,dict(original_fee='5',currency='CNY'));files['app/'+p.name]=sha256(p.read_bytes()).hexdigest()
        artifacts[which]=base.put(app.parent/'execution-install.json',dict(schema='guanheng.execution-install.v1',files=files))
    reference=base.put(root/'security.json',dict(schema='guanheng.security-reference.v1',securities={'SZSE.159352':dict(
        symbol='SZSE.159352',name=addition['name'],market='SZSE',security_type='etf',listed_on='2024-10-15',expires_on=None,
        observed_at='2026-11-06T00:00:00Z')},provenance=dict(catalog_sha256='a'*64,details_sha256='b'*64,indices_sha256=None)))
    origin=base.put(root/'old/execution.json',old)
    added=deepcopy(current['strategies'][1]);marker=deepcopy(current['strategy_extension_origin']);marker.update(origin)
    current=deepcopy(old);current['strategies'].append(added);current['recovery']=dict(mode='resume_reconciled')
    current['strategy_extension_origin']=marker;current['installation_root']=str(root/'current-install/app')
    current['data']['store']['symbols']+=deepcopy(ADDITIONS)
    current['trader'].update(binding_sha256=sha256(source_canonical(source['new'])).hexdigest(),base_url='http://127.0.0.1:19002',
        instance_id='b'*32,key_id_env='NEW_KEY',hmac_secret_env='NEW_SECRET')
    dependencies=dict(schema='guanheng.strategy-dependency-handoff.v1',origin_configuration_sha256=origin['sha256'],
        previous_installation=artifacts['previous'],current_installation=artifacts['current'],reader_additions=deepcopy(ADDITIONS),
        contract_addition=addition,contract_reference=reference,source_extension=dict(previous_version=source['refs'][1],current_version=source['refs'][2],
            adoption_receipt=source['refs']['receipt'],plan=source['refs']['plan'],origin_deployment=source['refs']['deployment'],
            origin_identity=source['refs']['identity'],transport={k:current['trader'][k]for k in TRANSPORT}))
    marker['dependency_handoff']=base.put(root/'dependencies.json',dependencies)
    return old,current,dependencies


def test_explicit_full_dependency_main(tmp_path,source_versions):
    old,current,proof=fixture(tmp_path,source_versions)
    assert recovery.compatible_business_configuration(current,old)
    assert recovery.market_origin_configuration(current)=={**old,'recovery':current['recovery']}
    base.native(dict(mode='compare',previous=old,current=current),tmp_path)
    assert source_versions['commands']==56
    assert recovery.compatible_business_configuration(current,current)
    base.native(dict(mode='compare',previous=current,current=current),tmp_path)


def test_actual_native_reconciled_dependency_admission(tmp_path,monkeypatch,source_versions):
    old,current,proof=fixture(tmp_path,source_versions)
    monkeypatch.setattr(base,'fixture',lambda root:(old,current))
    base.test_native_actual_fault_admission_preserves_files(tmp_path,None)


def test_missing_environment_fees_keeps_original_default(tmp_path,source_versions):
    old,current,proof=fixture(tmp_path,source_versions)
    old['environment'].pop('fees');current['environment'].pop('fees')
    reference=base.put(tmp_path/'old/execution.json',old)
    current['strategy_extension_origin'].update(reference)
    proof['origin_configuration_sha256']=reference['sha256']
    current['strategy_extension_origin']['dependency_handoff']=base.put(tmp_path/'dependencies.json',proof)
    assert recovery.compatible_business_configuration(current,old)
    base.native(dict(mode='compare',previous=old,current=current),tmp_path)


@pytest.mark.parametrize('kind',['old_contract','fees','filters','reader_replace','reader_extra','reader_other','account','profile','budget','query',
    'contract_reference','source_receipt','source_binding','source_copy','missing_source','install_sha','marker_missing','marker_removed'])
def test_dependency_changes_outside_exact_proof_rejected(tmp_path,source_versions,kind):
    old,current,proof=fixture(tmp_path,source_versions)
    if kind in('old_contract','fees','filters'):
        name='contracts.json'if kind=='old_contract'else'fees.json'if kind=='fees'else'retired-role-filter.json'
        p=Path(current['installation_root'])/name;value=json.loads(p.read_bytes())
        if kind=='old_contract':value['SZSE']['159780']['opendate']=20200101
        else:value['changed']=True
        base.put(p,value)
        manifest=json.loads(Path(proof['current_installation']['file']).read_bytes());manifest['files']['app/'+name]=sha256(p.read_bytes()).hexdigest()
        proof['current_installation']=base.put(Path(proof['current_installation']['file']),manifest)
    elif kind=='reader_replace':current['data']['store']['symbols'][0]['symbol']='OTHER.SZ'
    elif kind=='reader_extra':current['data']['store']['symbols'].append(dict(std_code='SSE.ETF.588120',symbol='588120.SH'))
    elif kind=='reader_other':current['data']['store']['timeout_ms']=6000
    elif kind=='account':current['trader']['expected_account']='OTHER'
    elif kind=='profile':current['trader']['profile']='other'
    elif kind=='budget':current['trader']['max_rows']=257
    elif kind=='query':current['trader']['position_by_query']=True
    elif kind=='contract_reference':
        ref=json.loads(Path(proof['contract_reference']['file']).read_bytes());ref['securities']['SZSE.159352']['listed_on']='2024-10-16'
        proof['contract_reference']=base.put(tmp_path/'wrong-reference.json',ref)
    elif kind=='source_receipt':
        receipt=json.loads(Path(proof['source_extension']['adoption_receipt']['file']).read_bytes());receipt['adopted']=False
        proof['source_extension']['adoption_receipt']=base.put(tmp_path/'wrong-receipt.json',receipt)
    elif kind=='source_binding':
        current['trader']['binding_sha256']='e'*64;proof['source_extension']['transport']['binding_sha256']='e'*64
    elif kind=='source_copy':
        plan=json.loads(Path(proof['source_extension']['plan']['file']).read_bytes());plan['journal_path']=str(tmp_path/'copied.sqlite')
        proof['source_extension']['plan']=base.put(tmp_path/'copy-plan.json',plan)
    elif kind=='missing_source':proof['source_extension']=None
    elif kind=='install_sha':proof['current_installation']['sha256']='f'*64
    elif kind=='marker_missing':current['strategy_extension_origin'].pop('dependency_handoff')
    elif kind=='marker_removed':
        old=deepcopy(current);current['strategy_extension_origin'].pop('dependency_handoff')
    if kind not in('marker_missing','marker_removed'):
        current['strategy_extension_origin']['dependency_handoff']=base.put(tmp_path/'bad-dependencies.json',proof)
    with pytest.raises((ValueError,KeyError)):recovery.compatible_business_configuration(current,old)
    base.native(dict(mode='compare',previous=old,current=current),tmp_path,False)


@pytest.mark.parametrize('changed',['journal_path','trade_binding'])
def test_origin_projection_must_be_derived_from_actual_deployment(tmp_path,source_versions,changed):
    # 只重绑原部署raw及其摘要，保留旧投影/plan/版本/采用证明；自报身份不能认领另一owner。
    old,current,proof=fixture(tmp_path,source_versions)
    source=proof['source_extension'];deployment=json.loads(Path(source['origin_deployment']['file']).read_bytes())
    if changed=='journal_path':deployment['host']['journal_path']=str(tmp_path/'different-owner.sqlite')
    else:deployment['host']['trade_binding']['strategy_name']='changed actual binding'
    source['origin_deployment']=base.put(tmp_path/'changed-deployment.json',deployment)
    projection=json.loads(Path(source['origin_identity']['file']).read_bytes())
    projection['deployment_sha256']=source['origin_deployment']['sha256']
    source['origin_identity']=base.put(tmp_path/'contradictory-projection.json',projection)
    current['strategy_extension_origin']['dependency_handoff']=base.put(tmp_path/'dependencies.json',proof)
    from guanheng_qmt_shm import reference_deployment_identity
    assert reference_deployment_identity(Path(source['origin_deployment']['file']).read_bytes())!=projection
    with pytest.raises(ValueError):recovery.compatible_business_configuration(current,old)
    base.native(dict(mode='compare',previous=old,current=current),tmp_path,success=False)


def test_default_no_source_handoff_does_not_import_source_owner(tmp_path,source_versions,monkeypatch):
    # 未声明Source变化仍走旧读取/比较；不能因新增依赖触发Source构造或权限逻辑。
    old,current,proof=fixture(tmp_path,source_versions)
    for name in TRANSPORT:current['trader'][name]=old['trader'][name]
    proof['source_extension']=None
    current['strategy_extension_origin']['dependency_handoff']=base.put(tmp_path/'dependencies.json',proof)
    import builtins
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        assert not name.startswith('guanheng_qmt_shm'),'default branch imported Source owner'
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    assert recovery.compatible_business_configuration(current,old)
    base.native(dict(mode='compare',previous=old,current=current),tmp_path)


def test_deployment_binding_key_order_keeps_source_canonical_identity(tmp_path,source_versions):
    # Host原decoder按语义读绑定，正文对象键顺序与原canonical绑定摘要分别解释。
    old,current,proof=fixture(tmp_path,source_versions);source=proof['source_extension']
    deployment=json.loads(Path(source['origin_deployment']['file']).read_bytes())
    def reverse(value):
        return {k:reverse(v)for k,v in reversed(list(value.items()))}if isinstance(value,dict)else value
    deployment['host']['trade_binding']=reverse(deployment['host']['trade_binding'])
    raw=json.dumps(deployment,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    p=tmp_path/'reordered-deployment.json';p.write_bytes(raw)
    source['origin_deployment']=dict(file=str(p),sha256=sha256(raw).hexdigest())
    from guanheng_qmt_shm import reference_deployment_identity
    source['origin_identity']=base.put(tmp_path/'reordered-identity.json',reference_deployment_identity(raw))
    current['strategy_extension_origin']['dependency_handoff']=base.put(tmp_path/'dependencies.json',proof)
    assert recovery.compatible_business_configuration(current,old)
    base.native(dict(mode='compare',previous=old,current=current),tmp_path)
