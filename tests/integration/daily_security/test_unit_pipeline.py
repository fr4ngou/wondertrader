"""Data27双入口、原意图恢复与逐证券单位接线；来源/Native边界均明确替身。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

import pytest

from integrations.guanheng import daily_data_inputs as inputs
from integrations.guanheng import daily_price_update as update
from integrations.guanheng import daily_price_refresh as refresh
from integrations.guanheng.daily_data_update import _descriptor, _load, _save
from integrations.guanheng.daily_gap_plan import write_gap_plan
from integrations.guanheng.market_generation import GenerationPublisher, encode


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    _save(path, value)
    return _descriptor(path)


def unit_descriptor(root):
    return dict(path=str(root/"approved-unit-evidence.json"), sha256="e"*64)


def service_config(root):
    return dict(schema="guanheng.daily-data-service.v1", directory=str(root/"tasks"),
        raw_store=str(root/"raw"), template=dict(schema="guanheng.daily-data-update.v1"),
        inputs=dict(connections=dict(batch={}, hpr={}), cache_from="20261104", max_rows=40,
            source_kind="sdk-synthetic", public_facts=dict(source={}, allowed_hosts=[], seconds=30,
            max_requests=10, max_bytes=1024, response_bytes=1024, timeout_seconds=1)),
        schedule=dict(timezone="Asia/Shanghai", at="09:00", poll_seconds=1), cycle_seconds=60,
        retry_seconds=1, price_scope=dict(baseline_reference={}, reference_connection=None,
            scope={}, authorized_from="20261104", maximum_history_rows=10000))


def test_service_and_scope_accept_only_explicit_descriptor_shape(tmp_path, monkeypatch):
    from integrations.guanheng.daily_data_service import validate_configuration
    from integrations.guanheng import daily_price_scope as scope
    config=service_config(tmp_path);config["price_scope"]["unit_evidence"]=unit_descriptor(tmp_path)
    assert validate_configuration(config) is config
    class SourceBoundary(RuntimeError): pass
    def reached(*args, **kwargs): raise SourceBoundary()
    monkeypatch.setattr("integrations.guanheng.security_reference.SecurityReference", reached)
    with pytest.raises(SourceBoundary):
        scope.prepare_price_scope(config["price_scope"],"2026-11-06",{}, {}, tmp_path/"scope",
            deadline=time.monotonic()+3,cancelled=lambda:False)
    for bad in (dict(path="relative",sha256="e"*64), dict(path=str(tmp_path/"x"),sha256="bad"),
                dict(path=str(tmp_path/"x"),sha256="e"*64,unit="CNY")):
        broken=deepcopy(config);broken["price_scope"]["unit_evidence"]=bad
        with pytest.raises(ValueError):validate_configuration(broken)


@pytest.mark.parametrize("original_selection", [None, "old"])
def test_full_input_resume_preserves_original_optional_choice_and_source_bytes(tmp_path, original_selection):
    original=dict(price_scope={}, template=dict(publication_directory=str(tmp_path/'publication')))
    if original_selection:
        original["price_scope"]["unit_evidence"]=unit_descriptor(tmp_path/"old")
    work=tmp_path/"inputs";work.mkdir()
    intent=work/"INPUTS.json";write(intent,dict(configuration=original,day="2026-11-06",previous_requests=[]))
    final=write(work/"UPDATE.json",dict(schema="synthetic-retained-result",capture_id="fixed-original-id"))
    slot=work/"slots"/"old.json";write(slot,dict(request_id="00000000-0000-4000-8000-000000000001",pending=True))
    before=(intent.read_bytes(),slot.read_bytes())
    live=deepcopy(original);live["price_scope"]["unit_evidence"]=unit_descriptor(tmp_path/"new")
    assert inputs.prepare_update(live,"2026-11-06",work,deadline=time.monotonic()+5)==final
    assert (intent.read_bytes(),slot.read_bytes())==before
    live["unrelated_change"]=True
    with pytest.raises(ValueError,match="configuration differs"):
        inputs.prepare_update(live,"2026-11-06",work,deadline=time.monotonic()+5)


@pytest.mark.parametrize('bad',[None,[],{'price_scope':'invalid'}])
def test_broken_original_configuration_cannot_acquire_new_selection(bad):
    if type(bad)is dict:
        # 相同字段仍交入口完整比较，不能重写原坏shape为live结构。
        assert inputs.fixed_price_input_configuration({'price_scope':{}},bad)!=bad
    else:
        with pytest.raises(ValueError):inputs.fixed_price_input_configuration({'price_scope':{}},bad)


@pytest.mark.parametrize("resuming", [False, True])
def test_price_first_binds_new_selection_and_retains_old_choice(tmp_path, monkeypatch, resuming):
    config=service_config(tmp_path);root=tmp_path/"refresh";root.mkdir()
    config["template"].update(publication_directory=str(tmp_path/"publication"),protected_slots=[],
                              universe={},calendar={},helper={})
    original=deepcopy(config)
    config["price_scope"]["unit_evidence"]=unit_descriptor(tmp_path)
    old_config=write(tmp_path/"old-source.json",dict(mode="source-market-snapshot",base=dict(mode="source-catalog")))
    write(root/"PARENT.json",dict(generation=dict(configuration=old_config,snapshot_id="a"*64),sha256="b"*64))
    prior=tmp_path/"previous"
    returned=str(prior/"returned.json")
    pending=str(prior/"pending.json")
    unclassified=str(prior/"unclassified.json")
    previous_requests=[write(prior/"REQUEST.json",dict(protected_slots=[returned,pending,unclassified]))["path"]]
    def committed_states(pending_state, leaf):
        records=[dict(slot=path,request_id=f"request-{index}",operation_id="market.history_prepare",
            arguments=dict(symbol="510300.SH",period="1d",start_time="20261106",end_time="20261106"),
            request_sha256="d"*64,execution_state=state)
            for index,(path,state) in enumerate(((returned,"call_returned"),(pending,pending_state)))]
        plan=write_gap_plan(prior/leaf,dict(schema="guanheng.daily-gap-plan.v1",
            capture=dict(directory=str(prior/"capture"),sha256="a"*64),snapshot_id="b"*64,
            authorized_from="20261106",authorized_to="20261106",
            tasks=[],exclusions=[],protected_requests=records),deadline=time.monotonic()+5)
        write(prior/"work"/"STATE.json",dict(stages=dict(gap_plan=plan)))
    committed_states("unknown","first")
    if resuming:
        write(root/"inputs"/"INPUTS.json",dict(configuration=original,day="2026-11-06",previous_requests=previous_requests))
    before=(root/"inputs"/"INPUTS.json").read_bytes()if resuming else None
    publisher=object.__new__(GenerationPublisher)
    publisher.directory=tmp_path/"publication";publisher._lock=object()  # 只替代原租约边界，不启动发布。
    monkeypatch.setattr(refresh,"prepare_price_scope",lambda *a,**k:dict(path="scope",sha256="c"*64))
    seen={}
    class StopBeforeNative(RuntimeError): pass
    def capture(request,*args,**kwargs):
        seen.update(request=request);raise StopBeforeNative()
    monkeypatch.setattr(refresh,"prepare_price_update",capture)
    with pytest.raises(StopBeforeNative):
        refresh.price_refresh(config,"2026-11-06",root,publisher=publisher,
            deadline=time.monotonic()+5,cancelled=lambda:False,previous_requests=previous_requests)
    saved=json.loads((root/"REQUEST.json").read_bytes())["price_maintenance"]
    assert seen["request"]["protected_slots"]==[pending,unclassified]
    original_request=(root/"REQUEST.json").read_bytes()
    committed_states("not_executed","second")
    with pytest.raises(StopBeforeNative):
        refresh.price_refresh(config,"2026-11-06",root,publisher=publisher,
            deadline=time.monotonic()+5,cancelled=lambda:False,previous_requests=previous_requests)
    assert seen["request"]["protected_slots"]==[pending,unclassified]
    assert (root/"REQUEST.json").read_bytes()==original_request
    if resuming:
        assert "unit_evidence"not in seen["request"] and "unit_evidence"not in saved
        assert (root/"inputs"/"INPUTS.json").read_bytes()==before
    else:
        assert seen["request"]["unit_evidence"]==saved["unit_evidence"]==unit_descriptor(tmp_path)


@pytest.mark.parametrize("same_capture", [False, True])
def test_price_owner_loads_once_qualifies_unique_captures_and_shares_with_both_archives(tmp_path, monkeypatch, same_capture):
    symbol="SSE.510300";ordinary=dict(directory=str(tmp_path/"ordinary"),sha256="a"*64)
    hot=dict(directory=str(tmp_path/"hot"),sha256=("a"if same_capture else"b")*64)
    universe=write(tmp_path/"universe.json",dict(securities={symbol:{}}))
    scope=write(tmp_path/"scope.json",dict(universe=universe,securities={symbol:dict(security_type="etf")},
        reference={},observation_date="2026-11-06",source_members=[symbol],groups=[]))
    source=write(tmp_path/"source.json",dict(mode="synthetic"))
    maintenance=dict(scope=scope,current_configuration=source,snapshot_id="a"*64,calendar={},connections={},
        protected_slots=[],authorized_from="20261106",source_kind="sdk-synthetic",maximum_history_rows=10000,
        previous_archives=[],helper={},unit_evidence=unit_descriptor(tmp_path),strategy_history=dict(symbols=[symbol]))
    def ordinary_inputs(request, root, **kwargs):
        return write(root/"INPUTS.json",dict(cache=ordinary,securities={symbol:dict(
            reason="available",source_state="observed",before=dict(last_date=20261106))}))
    monkeypatch.setattr(update,"prepare_price_inputs",ordinary_inputs)
    monkeypatch.setattr("integrations.guanheng.daily_strategy_history.prepare_strategy_history",
        lambda *a,**k:write(tmp_path/"hot-result.json",dict(cache=hot,coverage={})))
    calls=[];token=object()
    def load(*a,**k):calls.append(("load",a[0]));return token
    def qualify(capture, evidence, **kw):assert evidence is token;calls.append(("qualify",capture["sha256"]));return object()
    monkeypatch.setattr("integrations.guanheng.analysis_price_units.load_unit_evidence",load)
    monkeypatch.setattr("integrations.guanheng.analysis_price_units.qualify_capture_units",qualify)
    class Market:
        def call(self, request):return dict(status=dict(code="Unavailable"),data=dict(bars=[],archive=None))
        def close(self):pass
    class Reference:
        def __init__(self,*a):pass
        def assess(self,*a):return dict(no_trade_dates=[],before_listing_dates=[],after_expiry_dates=[],missing_dates=[])
        def close(self):pass
    monkeypatch.setattr(update,"create_native_source_market",lambda *a:Market())
    monkeypatch.setattr(update,"SecurityReference",Reference)
    monkeypatch.setattr(update,"_catalog",lambda b:dict(native_reader={}))
    monkeypatch.setattr(update,"compose_static_archive",lambda b,*a,**k:b)
    seen={}
    def raw(*a,**kw):seen["raw"]=kw["unit_evidence_by_capture"];return write(a[3]/"archive.json",dict(entries=[]))
    def front(*a,**kw):
        seen["front"]=kw["unit_evidence_by_capture"]
        return write(a[3]/"RESULT.json",dict(archive=write(a[3]/"data"/"archive.json",dict(entries=[]))))
    monkeypatch.setattr(update,"materialize_price_archive",raw)
    monkeypatch.setattr(update,"prepare_front_archive",front)
    result=update.prepare_price_update(maintenance,None,source,tmp_path/"work",
        deadline=time.monotonic()+10,cancelled=lambda:False)
    assert _load(result)["strategy_history"]["sha256"]
    assert len([x for x in calls if x[0]=="load"])==1
    assert len([x for x in calls if x[0]=="qualify"])==(1 if same_capture else 2)
    assert seen["raw"] is seen["front"]


def test_raw_new_records_get_selected_units_while_old_priority_is_preserved(tmp_path, monkeypatch):
    from integrations.guanheng import daily_price_archive as raw
    bar=lambda value:dict(open=value,high=value,low=value,close=value,volume=3.,amount=6.)
    cache=dict(directory="cache",sha256="a"*64)
    manifest=dict(source_kind="actual-qmt")
    descriptor=write(tmp_path/"inputs.json",dict(schema="guanheng.daily-price-input-result.v1",cache=cache))
    monkeypatch.setattr(raw,"load_price_capture",lambda d:manifest)
    monkeypatch.setattr(raw,"price_batches",lambda *a,**k:iter([(None,{
        "510300.SH":dict(data={"20261105":bar(2),"20261106":bar(3)}),
        "000300.SH":dict(data={"20261106":bar(4000)})})]))
    token=object();calls=[]
    def metadata(m,sha,basis,**kw):
        calls.append(kw);return dict(price_unit="CNY"if kw.get("symbol")=="510300.SH"else"unknown",
            volume_unit="lot"if kw else"unknown",amount_unit="unknown")
    monkeypatch.setattr(raw,"capture_metadata",metadata)
    seen={}
    def merge(market,rows,fallback,out,*a,**kw):
        seen.update(rows=rows,parts=kw["addition_provenance"]);return write(out/"archive.json",dict(entries=[]))
    monkeypatch.setattr(raw,"merge_original_price_rows",merge)
    raw.materialize_price_archive(descriptor,None,[],tmp_path/"raw",{'path':'synthetic-helper','sha256':'d'*64}, {},
        deadline=time.monotonic()+5,unit_evidence_by_capture={cache["sha256"]:token})
    assert seen["parts"]["SSE.510300"][0]["metadata"]["price_unit"]=="CNY"
    assert seen["parts"]["SSE.000300"][0]["metadata"]["price_unit"]=="unknown"
    assert all(part["metadata"]["amount_unit"]=="unknown"for parts in seen["parts"].values()for part in parts)
    assert all(x.get("unit_evidence")is token for x in calls if x)


def test_full_facts_new_input_fixes_descriptor_into_price_request(tmp_path, monkeypatch):
    """沿既有完整输入fixture跑到UPDATE；公开事实/Source均为原测试替身。"""
    import importlib.util
    fixture_path=Path(__file__).parents[1]/'market_supplement'/'test_daily_owner.py'
    spec=importlib.util.spec_from_file_location('unit_pipeline_daily_owner_fixture',fixture_path)
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    config,pool,facts,original_request=fixture.owner_fixture(tmp_path)
    day=pool['date']
    config['inputs'].pop('supplement_facts')
    fixture.patch_owner_dependencies(monkeypatch,config,pool,facts,original_request)
    config['price_scope']=dict(baseline_reference={},reference_connection=None,scope={},
        authorized_from='20261104',maximum_history_rows=10000,unit_evidence=unit_descriptor(tmp_path))
    current=Path(config['template']['publication_directory'])/'CURRENT.json'
    current.parent.mkdir(exist_ok=True);current.write_bytes(b'{}')
    prior=write(tmp_path/'prior.json',dict(daily_facts=config['template']['daily_facts'],base=dict(mode='synthetic')))
    monkeypatch.setattr(inputs,'read_generation',lambda p:(dict(configuration=prior,snapshot_id='a'*64),'b'*64))
    def scope(configuration,*a,**kw):
        assert configuration['unit_evidence']==unit_descriptor(tmp_path)
        return write(tmp_path/'scope.json',dict(securities={}))
    monkeypatch.setattr('integrations.guanheng.daily_price_scope.prepare_price_scope',scope)
    result=inputs.prepare_update(config,day,tmp_path/'inputs',deadline=time.monotonic()+20)
    assert _load(result)['price_maintenance']['unit_evidence']==unit_descriptor(tmp_path)
    assert json.loads((tmp_path/'inputs'/'INPUTS.json').read_bytes())['configuration']['price_scope']['unit_evidence']==unit_descriptor(tmp_path)


@pytest.mark.parametrize('changed_after_read',[False,True])
def test_front_passes_native_read_rows_as_reuse_hint_and_rejects_changed_file(tmp_path,monkeypatch,changed_after_read):
    from integrations.guanheng import daily_front_archive as front
    from integrations.guanheng.daily_archive_prepare import price_rows_identity
    symbol='SSE.510300';path=tmp_path/'original.dsb';path.write_bytes(b'synthetic native boundary')
    identity=hashlib.sha256(path.read_bytes()).hexdigest()
    row=dict(date=20261106,open=2.,high=2.1,low=1.9,close=2.,volume=5.,amount=10.)
    old={20261106:(row,dict(adjustment='front_ratio'))}
    previous=write(tmp_path/'archive.json',dict(entries=[dict(symbol=symbol,path=path.name,sha256=identity,rows=1,first=20261106,last=20261106,
        provenance=[dict(metadata=dict(adjustment='front_ratio'))])]))
    cache=dict(directory='synthetic',sha256='a'*64)
    prepared=write(tmp_path/'inputs.json',dict(cache=cache))
    monkeypatch.setattr(front,'load_price_capture',lambda d:{})
    monkeypatch.setattr(front,'capture_metadata',lambda *a,**k:dict(adjustment='front_ratio'))
    monkeypatch.setattr(front,'price_batches',lambda *a,**k:iter([]))
    def read(*a,**kw):
        if changed_after_read:path.write_bytes(b'changed after original native read')
        return old
    monkeypatch.setattr(front,'read_price_history',read)
    seen={}
    def prepare(rows,metadata,out,*a,**kw):
        seen.update(kw);return write(out/'archive.json',dict(entries=[]))
    monkeypatch.setattr(front,'prepare_daily_archive',prepare)
    from integrations.guanheng.source_archive_identity import archive_entry_identity
    class Market:
        def static_archive_identity(self,*args,**kw):return archive_entry_identity(previous,_load(previous)['entries'][0])
    call=lambda:front.prepare_front_archive(prepared,Market(),[previous],tmp_path/'front',{'path':'helper','sha256':'f'*64},
        deadline=time.monotonic()+5,maximum_history_rows=10000,cancelled=lambda:False)
    if changed_after_read:
        with pytest.raises(ValueError):call()
        assert not seen
    else:
        call();hint=seen['reusable_files'][symbol]
        assert hint==dict(path=str(path.resolve()),sha256=identity,rows_sha256=price_rows_identity([row]))


def test_reuse_screen_still_rejects_different_full_native_bar_field(tmp_path,monkeypatch):
    """原verify方法处理真实ctypes回调形态；Codec由普通DLL主链另验。"""
    import ctypes as C
    import struct
    from integrations.guanheng import daily_archive_prepare as archive
    from integrations.guanheng.analysis_price_capture import capture_metadata
    from integrations.guanheng.qmt_minute_import import _Native,ImportFailure
    from integrations.guanheng.native_history import WTSBar
    row=dict(date=20261106,open=2.,high=2.1,low=1.9,close=2.,volume=5.,amount=10.)
    old=tmp_path/'old.dsb';old.write_bytes(struct.pack('<8sHHQ',b'&^%$#@!\0',23,4,0))
    bar=WTSBar();bar.date=row['date']
    for name in ('open','high','low','close'):setattr(bar,name,row[name])
    bar.vol=row['volume'];bar.money=row['amount'];bar.hold=9.  # 六价量摘要看不见的真实额外字段差异。
    class Library:
        def read_dsb_bars(self,path,callback,count,logger):
            count(1);callback(C.pointer(bar),1,True);return 1
    class Native(_Native):
        def __init__(self,*a):self.lib=Library();self.directory=None
        def write_verify(self,*a,**k):raise AssertionError('unexpected encoder')
    monkeypatch.setattr(archive,'_Native',Native)
    metadata=capture_metadata(dict(source_kind='actual-qmt',request=dict(capture_id='00000000-0000-4000-8000-000000000001')),'a'*64,'front_ratio')
    with pytest.raises(ImportFailure):
        archive.prepare_daily_archive({'SSE.510300':[row]},metadata,tmp_path/'output','unused','b'*64,
            deadline=time.monotonic()+5,reusable_files={'SSE.510300':dict(path=str(old),
                sha256=hashlib.sha256(old.read_bytes()).hexdigest(),rows_sha256=archive.price_rows_identity([row]))})
