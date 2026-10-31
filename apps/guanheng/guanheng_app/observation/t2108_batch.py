"""原QAB批次slot的只读证券投影；一个SDK身份只验证一次。"""
import base64
from pathlib import Path
import re

from .storage import digest,encode
from .t2108_source import _need,_day,_receipt,_prices,decode

STATUSES={'observed','empty','missing','invalid','requires_partition'}


def _slots(capture, descriptor, manifest, day):
    """只核已公开的请求/结果身份与原字节；认证和consume继续归来源owner。"""
    request=manifest['request'];symbols=request['symbols']
    _need(type(symbols) is list and 1<=len(symbols)<=10000 and len(set(symbols))==len(symbols)
        and all(type(s) is str and re.fullmatch(r'[0-9]{6}\.(SH|SZ|BJ)',s) for s in symbols))
    first=request['start_date'];last=request['end_date'];maximum=request['max_rows']
    _need(type(first) is str and re.fullmatch('[0-9]{8}',first) and last==day.replace('-','')
        and type(maximum) is int and 1<=maximum<=20000)
    first=_day(first[:4]+'-'+first[4:6]+'-'+first[6:]);_need(first<=day)
    records=manifest['batches'];_need(type(records) is list and 1<=len(records)<=20000)
    result={};seen_requests=set();parent=Path(descriptor['path']).parent
    binding_sha=manifest['_expected_binding_sha256']
    for batch in records:
        capture.fetch.budget.remaining();identity=batch['batch_id']
        _need(type(identity) is str and re.fullmatch('[a-zA-Z0-9_.-]{1,100}',identity) and identity not in result)
        name=batch['slot'];_need(type(name) is str and not Path(name).is_absolute() and '..' not in Path(name).parts)
        slot,record=capture.read(dict(path=(parent/name).as_posix(),sha256=batch['sha256']),'qmt_analysis_batch_slot')
        original=slot['request'];reply_envelope=slot['result'];arguments=original['arguments']
        adjustment=batch['adjustment'];selected=batch['symbols']
        _need(adjustment in ('none','front_ratio') and type(selected) is list and 1<=len(selected)<=len(symbols)
            and len(set(selected))==len(selected) and set(selected)<=set(symbols))
        expected=dict(symbols=selected,start_date=request['start_date'],end_date=last,max_rows=maximum,adjustment=adjustment)
        _need(slot['consumed'] is True and original['operation_id']=='market.market_data'
            and original['policy_id']=='qmt.daily-batch-read.v1' and original['policy_version']=='1.0'
            and original['request_id']==batch['request_id'] and arguments==expected
            and digest(encode(original))==slot['request_body_sha256']==batch['request_body_sha256']
            and digest(encode(slot['binding']))==binding_sha and slot['binding']==batch['binding']
            and reply_envelope['state']=='terminal' and reply_envelope['operation_id']=='market.market_data'
            and reply_envelope['request_id']==batch['request_id']
            and reply_envelope['request_body_sha256']==batch['request_body_sha256']
            and all(reply_envelope[key]==batch['binding'] for key in ('admitted_binding','dispatch_binding','result_binding'))
            and slot['requested_at']==batch['requested_at'] and slot['received_at']==batch['received_at'],
            't2108_batch_identity')
        text=reply_envelope['result_body_b64']
        _need(type(text) is str and len(text)<=4*((capture.fetch.budget.response_bytes+2)//3))
        body=base64.b64decode(text,validate=True);capture.fetch.budget.expand(len(body))
        _need(digest(body)==reply_envelope['result_body_sha256']==batch['result_body_sha256'],'t2108_batch_identity')
        reply=decode(body)
        data,received=_receipt(dict(request_id=batch['request_id'],requested_at=batch['requested_at'],
            received_at=batch['received_at'],reply=reply),'market.market_data',seen_requests,day)
        _need(data.get('schema')=='qmt.daily-batch-result.v1' and data.get('adjustment')==adjustment
            and type(data.get('securities')) is dict and set(data['securities'])==set(selected))
        record['retrieved_at']=received
        result[identity]=dict(data=data['securities'],received=received,sha256=batch['sha256'],
            adjustment=adjustment,request_id=batch['request_id'])
    return result,seen_requests,first,maximum,symbols


def entries(capture, index, day, *, market_count):
    """按原指针读取QMT前复权序列；原none与比较声明仅作包身份核对。"""
    descriptor=index['batch_capture'];manifest,_=capture.read(descriptor,'qmt_analysis_batch_capture')
    _need(type(manifest) is dict and manifest.get('schema')=='guanheng.observation-qas-batch-capture.v1')
    _need(manifest.get('source_kind') in ('actual-qmt','sdk-synthetic'))
    capture.source_kind=manifest['source_kind']
    universe=manifest.get('universe')
    if universe is None:
        _need(manifest.get('source_kind')=='sdk-synthetic')
    else:
        _need(type(universe) is dict and universe.get('date')==day
            and universe.get('market_count')==market_count and universe.get('sha256')==index['universe']['sha256']
            and universe.get('selected_count')==len(manifest['request']['symbols'])
            and manifest['request'].get('universe')==universe,'t2108_batch_universe_identity')
    # 仅内部消费上下文；原清单已经逐字进入内容对象。
    manifest=dict(manifest,_expected_binding_sha256=index['source_binding_sha256'])
    slots,_,first,maximum,symbols=_slots(capture,descriptor,manifest,day)
    securities=manifest['securities'];comparisons=manifest['comparison'];qualifications=index['qualifications']
    _need(type(securities) is dict and set(securities)==set(symbols)
        and type(comparisons) is dict and set(comparisons)==set(symbols)
        and type(qualifications) is dict and set(qualifications)<=set(symbols))
    for symbol,projections in securities.items():
        capture.fetch.budget.remaining();_need(type(projections) is dict and set(projections)=={'none','front_ratio'})
        values={};received=[];statuses={}
        for adjustment in ('none','front_ratio'):
            projection=projections[adjustment]
            _need(type(projection) is dict and set(projection)=={'batch_id','status','data_pointer'})
            batch=slots[projection['batch_id']]
            _need(batch['adjustment']==adjustment and projection['status'] in STATUSES
                and projection['data_pointer']=='/data/securities/'+symbol)
            value=batch['data'][symbol]
            _need(type(value) is dict and value.get('status')==projection['status'] and type(value.get('data')) is dict)
            _need(value['status']=='observed' or not value['data'])
            values[adjustment]=_prices({symbol:value['data']},symbol,maximum,first,day,capture.fetch.budget.remaining)
            statuses[adjustment]=value['status']
            received.append(batch['received'])
        common=sorted(set(values['none']) & set(values['front_ratio']))
        expected=dict(common_dates=[d.replace('-','') for d in common],basis=common[-1].replace('-','') if common else None,
            rows=len(common),at_least_40=len(common)>=40,adjustment_qualified=False,closed_basis_qualified=False,factors='not_requested')
        _need(comparisons[symbol]==expected,'t2108_batch_comparison_identity')
        yield dict(symbol=symbol,adjusted=values['front_ratio'],received=received,status=statuses['front_ratio'])
