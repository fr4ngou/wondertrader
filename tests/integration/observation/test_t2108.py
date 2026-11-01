"""来源准入、SMA40口径及原统一发布失败保旧；实际QMT资格另外验收。"""
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pytest

from guanheng_app.observation.collection import refresh
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.publication import adopt_snapshot
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from guanheng_app.observation.storage import digest,encode
from guanheng_app.observation.t2108_source import history
from guanheng_app.observation import collection,t2108_models
from guanheng_app.observation.admission import admit_dataset

DAY='2026-10-30'


def inputs(tmp_path, *, count=40, last=12, front=None, event=None):
    tmp_path.mkdir(exist_ok=True)
    files={}
    def save(name,value):
        body=encode(value);(tmp_path/name).write_bytes(body);files[name]=value
        return dict(path=name,sha256=digest(body))
    days=[(date.fromisoformat(DAY)-timedelta(days=count-1-i)).strftime('%Y%m%d') for i in range(count)]
    def prices(adjustment):
        values={}
        for i,day in enumerate(days):
            close=last if i==count-1 else 10
            if front is not None and adjustment=='front_ratio':close=front
            values[day]=dict(open=close,high=close,low=close,close=close,volume=100,amount=1000)
        return {'000001.SZ':values}
    def receipt(operation,data):
        rid=str(uuid4())
        return dict(request_id=rid,requested_at='2026-10-30T07:10:00Z',received_at='2026-10-30T07:10:01Z',
            reply=dict(request_id=rid,operation_id=operation,ok=True,error_code=None,data=data))
    entry=dict(symbol='000001.SZ',arguments=dict(start_date=days[0],end_date='20261030',max_rows=100),
        raw=save('raw.json',receipt('market.market_data',prices('none'))),
        front_ratio=save('front.json',receipt('market.market_data',prices('front_ratio'))),
        factors=save('factors.json',receipt('market.divid_factors',event or {})))
    entry.update(adjustment_qualified=True,adjustment_evidence=save('qualification.json',dict(
        symbol=entry['symbol'],source_binding_sha256='a'*64,qualified=True,scope='t2108-current-visible-close-reference/1',qualification='explicit SDK substitute only',
        **{kind+'_sha256':entry[kind]['sha256'] for kind in ('raw','front_ratio','factors')})))
    manifest=dict(schema='guanheng.observation-qas-inputs.v1',observation_date=DAY,closed_through=DAY,
        closure_observed_at='2026-10-30T15:20:00+08:00',closure_evidence='explicit protocol substitute',
        source_binding_sha256='a'*64,universe=save('universe.json',dict(date=DAY,members=['sz.000001'],market_count=1)),
        entries=[entry],original_package=None)
    descriptor=save('CAPTURE.json',manifest)
    source=dict(id='qmt.t2108',kind='qmt_t2108',input_manifest=str(tmp_path/'CAPTURE.json'),input_sha256=descriptor['sha256'],
        datasets=['t2108.ashare'],tables=['source.t2108_ashare_universe'])
    return source,files


class Fetch:
    def __init__(self, reader, *, deadline=None, max_bytes=16777216, cancelled=None):
        self.objects=reader.objects;self.records=[]
        self.budget=CollectionBudget(deadline or monotonic()+30,max_bytes=max_bytes,cancelled=cancelled)


def reader_at(path):
    reader=build_reader(path);reader.repository.initialize();return reader


def rewrite(source,files,name,change):
    change(files[name]);body=encode(files[name]);path=Path(source['input_manifest'])
    (path.parent/name).write_bytes(body)
    manifest=files['CAPTURE.json']
    for entry in manifest['entries']:
        for key in ('raw','front_ratio','factors'):
            if entry[key]['path']==name:entry[key]['sha256']=digest(body)
    if name=='universe.json':manifest['universe']['sha256']=digest(body)
    if name in ('raw.json','front.json','factors.json'):
        proof=files['qualification.json']
        for kind in ('raw','front_ratio','factors'):
            proof[kind+'_sha256']=manifest['entries'][0][kind]['sha256']
        proof_body=encode(proof);(path.parent/'qualification.json').write_bytes(proof_body)
        manifest['entries'][0]['adjustment_evidence']['sha256']=digest(proof_body)
    body=encode(manifest);path.write_bytes(body);source['input_sha256']=digest(body)


def config(source):
    return dict(schema_version='guanheng.observation-sources.v1',timeout_seconds=15,max_days_per_batch=31,
        allowed_hosts=['www.baostock.com'],models={},schedule=dict(timezone='Asia/Shanghai',times=['09:00'],poll_seconds=5),
        retry_seconds=60,max_window_attempts=2,
        budget=dict(seconds=60,max_requests=1,max_bytes=16777216,response_bytes=4194304),sources=[source])


@pytest.mark.parametrize('last,expected',[(12,(1,0,0)),(10,(0,1,0)),(8,(0,0,1))])
def test_exact_current_included_and_equality_separate(tmp_path,last,expected):
    source,_=inputs(tmp_path/'input',last=last);reader=reader_at(tmp_path/'data')
    result=history(Fetch(reader),source,DAY,DAY)['t2108.ashare'][0]
    assert tuple(result[k] for k in ('above_count','equal_count','below_count'))==expected
    assert result['coverage_pct']==100 and result['market_above_sma40_pct']==result['above_sma40_pct']
    assert result['available_at'] is None and result['source_received_at']=='2026-10-30T07:10:01Z'


def test_39_periods_and_nonpositive_window_never_create_empty_metric(tmp_path):
    reader=reader_at(tmp_path/'data')
    for name,kwargs in [('short',dict(count=39)),('nonpositive',dict(last=0))]:
        source,_=inputs(tmp_path/name,**kwargs)
        with pytest.raises(SourceFailure,match='t2108_no_qualified_observations'):
            history(Fetch(reader),source,DAY,DAY)


def test_strict_sma_comparison_preserves_tiny_positive_residual(tmp_path):
    source,files=inputs(tmp_path/'input',last=1);reader=reader_at(tmp_path/'data')
    def residual(value):
        bars=value['reply']['data']['000001.SZ'];days=sorted(bars)
        for day in days:bars[day]['close']=1e-100
        bars[days[0]]['close']=39;bars[days[-1]]['close']=1
    rewrite(source,files,'raw.json',residual);rewrite(source,files,'front.json',residual)
    row=history(Fetch(reader),source,DAY,DAY)['t2108.ashare'][0]
    # 40*1 < 39+1+38e-100；有限精度求和会错误地得到相等。
    assert row['below_count']==1 and row['equal_count']==0 and row['above_count']==0


def test_current_supplier_sequence_does_not_require_factor_qualification(tmp_path):
    source,files=inputs(tmp_path/'input');reader=reader_at(tmp_path/'data')
    def unqualified(value):
        value['entries'][0].update(adjustment_qualified=False,adjustment_evidence=None)
    rewrite(source,files,'CAPTURE.json',unqualified)
    row=history(Fetch(reader),source,DAY,DAY)['t2108.ashare'][0]
    assert row['eligible_count']==1 and row['above_count']==1 and row['available_at'] is None


@pytest.mark.parametrize('scale',[0.001,0.5,1,1000])
@pytest.mark.parametrize('last,expected',[(12,'above_count'),(10,'equal_count'),(8,'below_count')])
def test_one_supplier_sequence_is_invariant_under_positive_normalization(tmp_path,scale,last,expected):
    source,files=inputs(tmp_path/'input',last=last)
    def normalize(value):
        for bar in value['reply']['data']['000001.SZ'].values():
            for field in ('open','high','low','close'):bar[field]*=scale
    rewrite(source,files,'front.json',normalize)
    row=history(Fetch(reader_at(tmp_path/'data')),source,DAY,DAY)['t2108.ashare'][0]
    assert row[expected]==1 and row['eligible_count']==1


def test_legacy_factor_material_does_not_gate_current_supplier_sequence(tmp_path):
    stamp=str(int(datetime(1991,5,2,tzinfo=timezone(timedelta(hours=8))).timestamp()*1000))
    source,_=inputs(tmp_path/'input',event={stamp:[0,0,0,0,0,0,2]})
    row=history(Fetch(reader_at(tmp_path/'data')),source,DAY,DAY)['t2108.ashare'][0]
    assert row['eligible_count']==1 and row['above_count']==1


def legacy_snapshot(reader, source):
    """明确旧/1合成点：一个合格，一个原因子待核，保留原分母和计数。"""
    row=history(Fetch(reader),source,DAY,DAY)['t2108.ashare'][0]
    row.pop('method_version',None);row.pop('source_kind',None)
    row.update(date='2026-10-29',market_count=2,adjustment_unverified_count=1,
        coverage_pct=50.0,confirmed_market_lower_bound_pct=50.0,market_above_sma40_pct=None)
    definition=t2108_models.definition();definition['definition_version']='t2108.ashare/1'
    definition['field_schema'].pop('method_version',None);definition['field_schema'].pop('source_kind',None)
    definition['field_schema']['adjustment_unverified_count']['label']='复权待核数量'
    item=admit_dataset(reader.objects,definition,[row],[])
    manifest=dict(schema_version='market-observation/1',published_at=datetime.now(timezone.utc).isoformat(),
        boards=[dict(id='breadth',label='市场广度')],preferences=dict(default_board='breadth',default_datasets={'breadth':'t2108.ashare'}),
        datasets={'t2108.ashare':item},assets={})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+20)
    return row,item


def test_next_day_retains_legacy_method_values_and_marks_new_method(tmp_path):
    source,_=inputs(tmp_path/'input');reader=reader_at(tmp_path/'data')
    old,_=legacy_snapshot(reader,source)
    assert refresh(reader,config(source),as_of=DAY,deadline=monotonic()+60)['status']=='success'
    _,manifest=reader.snapshot();rows=reader.rows(manifest['datasets']['t2108.ashare']['partition'])
    assert {key:rows[0][key] for key in old}==old
    assert rows[0]['method_version']=='t2108.ashare/1' and rows[0]['adjustment_unverified_count']==1
    assert rows[1]['method_version']=='t2108.ashare/2' and rows[1]['adjustment_unverified_count']==0
    assert rows[0]['market_count']==2 and rows[1]['market_count']==1


def test_refresh_retains_reconstructed_history_and_admits_current_source(tmp_path):
    """已发布重建点与新日终点共存，字段契约重建后仍能发布。"""
    source,_=inputs(tmp_path/'input');reader=reader_at(tmp_path/'data')
    legacy_snapshot(reader,source)
    previous,manifest=reader.snapshot();item=manifest['datasets'][t2108_models.METRIC]
    rows=reader.rows(item['partition']);rows[0]['reconstruction_as_of']=DAY
    definition=item['definition']
    definition['field_schema']['reconstruction_as_of']=dict(label='历史重建资料截止日',unit='日期',required=False)
    manifest['datasets'][t2108_models.METRIC]=admit_dataset(reader.objects,definition,rows,[])
    adopt_snapshot(reader,manifest,digest(encode(manifest)),previous,monotonic()+20)
    run=refresh(reader,config(source),as_of=DAY,deadline=monotonic()+60)
    assert run['status']=='success'
    _,result=reader.snapshot();item=result['datasets'][t2108_models.METRIC]
    loaded=reader.rows(item['partition'])
    assert loaded[0]['reconstruction_as_of']==DAY
    assert loaded[0]['market_count']==2 and loaded[0]['coverage_pct']==50
    assert loaded[1]['reconstruction_as_of'] is None
    assert loaded[1]['market_count']==1 and loaded[1]['coverage_pct']==100
    assert any('不能用于因果回测' in value for value in item['definition']['limitations'])


def test_failed_source_prepare_keeps_legacy_definition_with_partial_publication(tmp_path,monkeypatch):
    source,_=inputs(tmp_path/'input');reader=reader_at(tmp_path/'data')
    _,item=legacy_snapshot(reader,source)
    original_merge=collection.merge
    def failed_metric_prepare(old,rows,**kwargs):
        if rows and 'above_sma40_pct' in rows[0]:raise SourceFailure('explicit_prepare_failure')
        return original_merge(old,rows,**kwargs)
    monkeypatch.setattr(collection,'merge',failed_metric_prepare)
    monkeypatch.setitem(collection.PARSERS,'disclosure',lambda *args:{})
    configuration=config(source)
    configuration['sources'].append(dict(id='disclosure.check',kind='disclosure',datasets=[],tables=[]))
    run=refresh(reader,configuration,as_of=DAY,deadline=monotonic()+60)
    assert run['status']=='partial' and run['sources'][0]['error_code']=='explicit_prepare_failure'
    retained=reader.snapshot()[1]['datasets']['t2108.ashare']
    assert retained['partition']==item['partition']
    assert retained['definition']['definition_version']=='t2108.ashare/1'
    assert retained['definition']['field_schema']['adjustment_unverified_count']['label']=='复权待核数量'


@pytest.mark.parametrize('case', ['wrong_uuid','duplicate_request','wrong_symbol','future_clock','unclosed','preclose_request','escape','sha'])
def test_invalid_source_identity_and_clocks(tmp_path,case):
    source,files=inputs(tmp_path/'input');reader=reader_at(tmp_path/'data')
    if case=='wrong_uuid':rewrite(source,files,'raw.json',lambda v:v['reply'].update(request_id=str(uuid4())))
    if case=='duplicate_request':
        rid=files['raw.json']['request_id']
        def duplicate(v):v.update(request_id=rid);v['reply'].update(request_id=rid)
        rewrite(source,files,'front.json',duplicate)
    if case=='wrong_symbol':rewrite(source,files,'raw.json',lambda v:v['reply'].update(data={'000002.SZ':{}}))
    if case=='future_clock':rewrite(source,files,'raw.json',lambda v:v.update(received_at='2099-01-01T00:00:00Z'))
    if case=='unclosed':rewrite(source,files,'CAPTURE.json',lambda v:v.update(closure_observed_at='2026-10-30T14:59:00+08:00'))
    if case=='preclose_request':rewrite(source,files,'raw.json',lambda v:v.update(requested_at='2026-10-30T06:59:00Z'))
    if case=='escape':rewrite(source,files,'CAPTURE.json',lambda v:v['entries'][0]['raw'].update(path='../outside.json'))
    if case=='sha':source['input_sha256']='f'*64
    with pytest.raises(SourceFailure):history(Fetch(reader),source,DAY,DAY)


def test_original_deadline_cancellation_and_total_bytes(tmp_path):
    source,_=inputs(tmp_path/'input');reader=reader_at(tmp_path/'data')
    for kwargs,code in [(dict(deadline=monotonic()-1),'collection_timeout'),
            (dict(cancelled=lambda:True),'collection_stopped'),(dict(max_bytes=10),'capture_budget_exceeded')]:
        with pytest.raises(SourceFailure,match=code):history(Fetch(reader,**kwargs),source,DAY,DAY)


def test_config_and_failed_revision_keep_same_snapshot(tmp_path):
    source,files=inputs(tmp_path/'input');reader=reader_at(tmp_path/'data')
    configuration=config(source);validate_configuration(configuration)
    configuration['allowed_hosts']=[];validate_configuration(configuration)
    manifest=dict(schema_version='market-observation/1',published_at=datetime.now(timezone.utc).isoformat(),
        boards=[],preferences=dict(default_board='',default_datasets={}),datasets={},assets={})
    adopt_snapshot(reader,manifest,digest(encode(manifest)),None,monotonic()+20)
    good=refresh(reader,configuration,as_of=DAY,deadline=monotonic()+60)
    assert good['status']=='success';before=reader.repository.current()
    source['input_sha256']='f'*64
    failed=refresh(reader,configuration,as_of=DAY,deadline=monotonic()+60)
    assert failed['status']=='failed' and reader.repository.current()==before
    assert failed['sources'][0]['error_code']=='t2108_source_identity'
    source['input_sha256']=digest((tmp_path/'input/CAPTURE.json').read_bytes())
    assert refresh(reader,configuration,as_of=DAY,deadline=monotonic()+60)['status']=='success'
    source['kind']='baostock'
    with pytest.raises(ObservationError):validate_configuration(configuration)
