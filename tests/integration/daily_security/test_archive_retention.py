"""部分补充档叠加后的两个真实日更入口；保留完整档及原请求身份。"""
from pathlib import Path
from copy import deepcopy
import importlib.util
import json
import time

import pytest

from integrations.guanheng import daily_data_inputs as inputs
from integrations.guanheng import daily_price_refresh as refresh
from integrations.guanheng.daily_data_update import _save, _descriptor, _load
from integrations.guanheng.market_generation import GenerationPublisher
from integrations.guanheng.market_snapshot_prepare import price_archive_layers
from integrations.guanheng.analysis_price_capture import capture_metadata


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    _save(path, value)
    return _descriptor(path)


def archive_chain(root):
    def archive(name, schema, bases):
        return write(root/(name+'.json'), dict(schema='guanheng.daily-native-archive.'+schema,
            entries=[dict(symbol='SSE.%06d'%(510300+i), provenance=[dict(metadata=dict(adjustment=basis))])
                     for i, basis in enumerate(bases)]))
    # 同一原价/复权口径均有部分覆盖层和较早完整层；股票原档以下保持原Reader归属。
    native = archive('native', 'v2', ['none', 'front_ratio'])
    lower = archive('baseline', 'v1', ['none'])
    layers = [archive('partial-raw','v1',['none']), archive('partial-front','v2',['front_ratio']),
              archive('full-raw','v1',['none','none']), archive('full-front','v2',['front_ratio','front_ratio'])]
    base = dict(mode='source-daily-overlay', archive=lower, base=dict(mode='source-catalog'))
    for item in reversed([*layers, native]):
        base = dict(mode='source-daily-overlay', archive=item, base=base)
    return base, layers, native, lower


def owner_fixture(root, monkeypatch):
    path = Path(__file__).parents[1]/'market_supplement'/'test_daily_owner.py'
    spec = importlib.util.spec_from_file_location('archive_retention_daily_owner_fixture', path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    config, pool, facts, original = fixture.owner_fixture(root)
    config['inputs'].pop('supplement_facts')
    fixture.patch_owner_dependencies(monkeypatch, config, pool, facts, original)
    return config, pool['date']


def test_full_update_keeps_all_supplement_layers_before_native(tmp_path, monkeypatch):
    config, day = owner_fixture(tmp_path, monkeypatch)
    base, layers, native, lower = archive_chain(tmp_path/'archives')
    config['price_scope'] = dict(baseline_reference={}, reference_connection=None, scope={},
                               authorized_from='20261104', maximum_history_rows=10000)
    # 同一固定清单重复引用只交给合并一次；显式配置的额外档仍保留。
    extra = write(tmp_path/'extra.json', dict(schema='guanheng.daily-native-archive.v1',entries=[]))
    config['template']['additional_archives'] = [layers[0], extra]
    prior = write(tmp_path/'source.json', dict(base=base, daily_facts=config['template']['daily_facts']))
    pointer = Path(config['template']['publication_directory'])/'CURRENT.json'
    pointer.parent.mkdir(exist_ok=True); pointer.write_bytes(b'{}')
    monkeypatch.setattr(inputs, 'read_generation', lambda *_: (dict(configuration=prior,snapshot_id='a'*64),'b'*64))
    monkeypatch.setattr('integrations.guanheng.daily_price_scope.prepare_price_scope',
                        lambda *a,**k: write(tmp_path/'scope.json',dict(securities={})))
    result = _load(inputs.prepare_update(config,day,tmp_path/'inputs',deadline=time.monotonic()+20))
    assert result['additional_archives'] == [*layers, extra]
    assert result['price_maintenance']['previous_archives'] == [*layers, extra]
    assert result['previous_archives'] == [native]
    assert lower not in result['additional_archives']


def test_price_first_keeps_all_layers_and_original_request(tmp_path, monkeypatch):
    config, day = owner_fixture(tmp_path, monkeypatch)
    base, layers, native, lower = archive_chain(tmp_path/'archives')
    config['price_scope'] = dict(authorized_from='20261104',maximum_history_rows=10000)
    prior = write(tmp_path/'source.json', dict(mode='source-market-snapshot',base=base))
    root = tmp_path/'refresh'
    write(root/'PARENT.json',dict(generation=dict(configuration=prior,snapshot_id='a'*64),sha256='b'*64))
    monkeypatch.setattr(refresh,'prepare_price_scope',lambda *a,**k:dict(path='synthetic-scope',sha256='c'*64))
    observed = []
    class StopBeforeNative(RuntimeError): pass
    def capture(request,*args,**kwargs):
        observed.append(deepcopy(request));raise StopBeforeNative()
    monkeypatch.setattr(refresh,'prepare_price_update',capture)
    selections=[];select=refresh.price_archive_layers
    def choose(*a,**k):selections.append(True);return select(*a,**k)
    monkeypatch.setattr(refresh,'price_archive_layers',choose)
    with GenerationPublisher(config['template']['publication_directory']) as publisher:
        for _ in range(2):
            with pytest.raises(StopBeforeNative):
                refresh.price_refresh(config,day,root,publisher=publisher,deadline=time.monotonic()+10,
                                      cancelled=lambda:False)
    assert observed[0]['previous_archives'] == layers
    assert observed[0]['replaced_archives'] == layers
    assert native not in observed[0]['replaced_archives'] and lower not in observed[0]['replaced_archives']
    assert observed[0] == observed[1]
    assert len(selections)==1


def test_fixed_price_first_input_is_not_reselected_after_program_change(tmp_path,monkeypatch):
    config,day=owner_fixture(tmp_path,monkeypatch)
    base,layers,_,_=archive_chain(tmp_path/'archives')
    config['price_scope']=dict(authorized_from='20261104',maximum_history_rows=10000)
    prior=write(tmp_path/'source.json',dict(mode='source-market-snapshot',base=base))
    root=tmp_path/'refresh'
    write(root/'PARENT.json',dict(generation=dict(configuration=prior,snapshot_id='a'*64),sha256='b'*64))
    monkeypatch.setattr(refresh,'prepare_price_scope',lambda *a,**k:dict(path='synthetic-scope',sha256='c'*64))
    class StopBeforeNative(RuntimeError):pass
    observed=[]
    def capture(request,*a,**k):observed.append(deepcopy(request));raise StopBeforeNative()
    monkeypatch.setattr(refresh,'prepare_price_update',capture)
    with GenerationPublisher(config['template']['publication_directory']) as publisher:
        with pytest.raises(StopBeforeNative):
            refresh.price_refresh(config,day,root,publisher=publisher,deadline=time.monotonic()+10,cancelled=lambda:False)
        # 已派发任务具有当时冻结的输入集合，程序更新继续原集合及全部原件。
        request=_load(_descriptor(root/'REQUEST.json'))
        request['price_maintenance'].update(previous_archives=layers[:2],replaced_archives=layers[:2])
        write(root/'REQUEST.json',request);original=(root/'REQUEST.json').read_bytes()
        with pytest.raises(StopBeforeNative):
            refresh.price_refresh(config,day,root,publisher=publisher,deadline=time.monotonic()+10,cancelled=lambda:False)
    assert observed[-1]['previous_archives']==layers[:2]
    assert observed[-1]['replaced_archives']==layers[:2]
    assert (root/'REQUEST.json').read_bytes()==original


def test_layer_selection_deduplicates_and_checks_original_files(tmp_path):
    base, layers, native, lower = archive_chain(tmp_path)
    repeated = dict(mode='source-daily-overlay',archive=layers[0],base=base)
    assert price_archive_layers(repeated,deadline=time.monotonic()+5) == (layers,native)
    Path(layers[2]['path']).write_bytes(b'{}')
    with pytest.raises(ValueError,match='file changed'):
        price_archive_layers(base,deadline=time.monotonic()+5)


@pytest.mark.parametrize('cancelled,expired',[(True,False),(False,True)])
def test_layer_selection_keeps_original_stop_and_deadline(tmp_path,cancelled,expired):
    base,*_ = archive_chain(tmp_path)
    with pytest.raises(InterruptedError if cancelled else TimeoutError):
        price_archive_layers(base,deadline=time.monotonic()+(-1 if expired else 5),cancelled=lambda:cancelled)


def test_empty_supplement_is_preserved_and_unknown_schema_rejected(tmp_path):
    empty=write(tmp_path/'empty.json',dict(schema='guanheng.daily-native-archive.v1',entries=[]))
    base=dict(mode='source-daily-overlay',archive=empty,base=dict(mode='source-catalog'))
    assert price_archive_layers(base,deadline=time.monotonic()+5)==([empty],None)
    invalid=write(tmp_path/'invalid.json',dict(schema='unknown',entries=[]))
    with pytest.raises(ValueError,match='schema'):
        price_archive_layers(dict(base,archive=invalid),deadline=time.monotonic()+5)


@pytest.mark.parametrize('published',[False,True])
def test_actual_front_merge_keeps_new_reference_when_capture_is_empty(tmp_path,monkeypatch,published):
    """执行真实价格/前复权合并；仅以JSON替代Native编解码及外部捕获。"""
    from integrations.guanheng import daily_price_update as update,daily_front_archive as front
    symbol='SSE.510300';dates=[20261105,20261106]
    manifest=dict(source_kind='sdk-synthetic',request=dict(capture_id='00000000-0000-4000-8000-000000000001'))
    layers=[];expected=None
    for name,identity,price in [('new','a',2.),('old','b',1.)]:
        meta=capture_metadata(manifest,identity*64,'front_ratio')
        rows=[dict(date=day,open=price,high=price,low=price,close=price,volume=3.,amount=6.)for day in dates]
        file=write(tmp_path/(name+'.dsb'),dict(rows=rows))
        archive=write(tmp_path/(name+'.json'),dict(schema='guanheng.daily-native-archive.v2',entries=[dict(
            symbol=symbol,path=Path(file['path']).name,sha256=file['sha256'],rows=2,first=dates[0],last=dates[-1],
            provenance=[dict(offset=0,count=2,metadata=meta)])]))
        layers.append(archive)
        if name=='new':expected=(rows,meta)
    reader=dict(library='synthetic-codec',sha256='d'*64)
    base=dict(mode='source-catalog',native_reader=reader,stores=[])
    source=write(tmp_path/'base.json',base)
    scope=write(tmp_path/'scope.json',dict(universe=write(tmp_path/'universe.json',dict(securities={symbol:{}})),
        reference={},observation_date='2026-11-06',source_members=[symbol],groups=[],securities={symbol:dict(security_type='etf')}))
    cache=dict(directory=str(tmp_path/'capture'),sha256='c'*64)
    prepared=write(tmp_path/'inputs.json',dict(cache=cache,securities={symbol:dict(reason='target_not_in_cache',source_state='empty')}))
    request=dict(scope=scope,current_configuration=source,snapshot_id='a'*64,calendar={},connections={},
        protected_slots=[],authorized_from='20261105',source_kind='sdk-synthetic',maximum_history_rows=10000,
        previous_archives=layers,helper=dict(path='synthetic-helper',sha256='e'*64))
    if published:
        result=write(tmp_path/'published.json',dict(schema='guanheng.daily-price-update.v1',scope=scope,
            inputs=prepared,additional_archives=[]))
        request['published_prices']=dict(result=result)
    monkeypatch.setattr(update,'prepare_price_inputs',lambda *a,**k:prepared)
    monkeypatch.setattr(front,'load_price_capture',lambda *_:manifest)
    monkeypatch.setattr(front,'price_batches',lambda *a,**k:iter(()))
    class Market:
        def __init__(self,config):self.config=config
        def close(self):pass
        def call(self,request):
            q=request['request'];layer=self.config
            while isinstance(layer,dict):
                if layer.get('archive'):
                    for entry in _load(layer['archive'])['entries']:
                        if entry['symbol']==symbol and q.get('adjustment','none')=='front_ratio':
                            rows=json.loads((Path(layer['archive']['path']).parent/entry['path']).read_bytes())['rows']
                            meta=entry['provenance'][0]['metadata']
                            return dict(status=dict(code='Ok'),data=dict(bars=rows,metadata=meta,provenance=entry['provenance'],
                                archive=dict(first_date=entry['first'],last_date=entry['last'],count=entry['rows'])))
                layer=layer.get('base')
            return dict(status=dict(code='Unavailable'),data={})
    monkeypatch.setattr(update,'create_native_source_market',Market)
    class Reference:
        def __init__(self,*a):pass
        def close(self):pass
        def assess(self,*a):return dict(no_trade_dates=[],before_listing_dates=[],after_expiry_dates=[],missing_dates=[])
    monkeypatch.setattr(update,'SecurityReference',Reference)
    monkeypatch.setattr(update,'materialize_price_archive',lambda *a,**k:write(a[3]/'archive.json',
        dict(schema='guanheng.daily-native-archive.v1',entries=[])))
    written={}
    def codec(securities,metadata,output,*a,**kwargs):
        written.update(rows=securities,provenance=kwargs['provenance'])
        return write(output/'archive.json',dict(schema='guanheng.daily-native-archive.v2',entries=[]))
    monkeypatch.setattr(front,'prepare_daily_archive',codec)
    update.prepare_price_update(request,None,source,tmp_path/'work',deadline=time.monotonic()+10,cancelled=lambda:False)
    assert written['rows'][symbol]==expected[0]
    assert written['provenance'][symbol]==[dict(offset=0,count=2,metadata=expected[1])]
