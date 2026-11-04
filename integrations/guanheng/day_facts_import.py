"""WT数据侧复用已准入的公开历史原件；只物化参考事实，不计算指标或请求行情。"""
from decimal import Decimal,localcontext
import hashlib,json,re,time
from pathlib import Path
from ..guanheng_market_client import strict_json
from ..guanheng_market_client.daily_facts import FIELDS,validate_day_facts
from ..guanheng_market_client.market_snapshot import _hash
from .day_facts_prepare import prepare_facts_catalog


def prepare_archive_facts(official_recipe_sha256,float_capture_sha256,qualification_sha256,
        read_object,recent_days,output,*,deadline,maximum_input_bytes=536870912):
    """复用已审日K/沪深日表/历史上市池及当前修订逐日股本，最多366日。

    read_object只读固定SHA原件；本函数再次核SHA、字节预算和逐日资格。
    三个SHA分别为原官方历史recipe、股本捕获描述和来源审查原件。
    recent_days是同日完整事实，覆盖重构同日时优先，旧原件始终保留。
    首次可见/逐事件真实生效日保持未知；仅声明当前公开修订序列重构。
    """
    if type(maximum_input_bytes)is not int or not 16777216<=maximum_input_bytes<=1073741824:
        raise ValueError('day facts archive input budget invalid')
    total=0;used=set()
    def check():
        if time.monotonic()>=deadline:raise TimeoutError('day facts archive deadline expired')
    def read(identity):
        nonlocal total
        check();_hash(identity);body=read_object(identity);total+=len(body)
        if len(body)>16777216 or total>maximum_input_bytes or hashlib.sha256(body).hexdigest()!=identity:
            raise ValueError('day facts archive original identity or capacity')
        used.add(identity)
        # 官方日K可为JSONP；只移除有界标识符包装，JSON合同复用SDK严格解码。
        text=body.decode('utf8').strip()
        if not text.startswith(('[','{')):
            match=re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]{0,127}\((.*)\);?\s*',text,re.S)
            if match is None:raise ValueError('day facts archive JSON wrapper invalid')
            text=match[1]
        return strict_json(text.encode('utf8'))
    official=read(official_recipe_sha256);capital=read(float_capture_sha256);review=read(qualification_sha256)
    if (official.get('schema')!='oar.official-ashare-history-extension.v1'
            or capital.get('status')!='captured'
            or review.get('decision')!='source_qualified_for_explicit_vendor_reconstruction_only_adoption_pending'):
        raise ValueError('day facts archive source qualification differs')
    floats=read(capital['canonical_sha256']);shares={}
    if type(floats)is not list or len(floats)>100000:raise ValueError('day facts archive capital capacity')
    for row in floats:
        check();key=(row['TRADE_DATE'][:10],row['SECURITY_CODE'])
        if key in shares:raise ValueError('day facts archive capital identity repeated')
        shares[key]=row
    dates={row['date']:row for row in official['shsz_daily']}
    if not 1<=len(dates)<=366 or len(dates)!=len(official['shsz_daily']):raise ValueError('day facts archive dates invalid')
    received=[record['retrieved_at']for record in read(capital['records_sha256'])if record.get('retrieved_at')]
    history={}
    for descriptor in official['public_bse_captures']:
        check();code=descriptor['code']
        if code in history:raise ValueError('day facts archive BSE identity repeated')
        rows=read(descriptor['sha256'])['data'];selected={}
        for row in rows:
            label=str(row['jsrq']);day=label[:4]+'-'+label[4:6]+'-'+label[6:8]
            if day not in dates:continue
            if day in selected:raise ValueError('day facts archive BSE day repeated')
            selected[day]=row
        history[code]=selected
    # 原接收时刻从原捕获记录读取；原piece身份仍由source_inputs保持。
    for identity in sorted({d['source_manifest']for d in official['public_bse_captures']}):
        received.extend(record['retrieved_at']for record in read(identity)if record.get('retrieved_at'))
    binding=dict(schema='guanheng.daily-facts-history-binding.v1',
        official_recipe_sha256=official_recipe_sha256,  # 官方日K/沪深日表及上市区间原recipe。
        float_capture_sha256=float_capture_sha256,  # 当前修订逐日非限售股本的原捕获描述。
        qualification_sha256=qualification_sha256)  # 原来源审查说明，资格不扩大至PIT。
    encode=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    binding_body=encode(binding);binding_sha=hashlib.sha256(binding_body).hexdigest()
    convert=lambda s:{'sh':'SSE','sz':'SZSE','bj':'BSE'}[s[:2]]+'.'+s[3:]
    recent={value['date']:value for value in recent_days}
    if len(recent)!=len(recent_days):raise ValueError('day facts recent dates repeated')
    def days():
        for day,item in sorted(dates.items()):
            check()
            if day in recent:continue
            universe_sha=official['universe_payloads'][day];universe=read(universe_sha)
            members=set(universe['members']);unverified=universe['unverified_members'];table=read(item['sha256'])
            if len(members)>20000 or type(table.get('rows'))is not list or len(table['rows'])>20000:
                raise ValueError('day facts archive day capacity')
            rows=[];state_unknown=0
            for values in table['rows']:
                check()
                if len(values)!=len(table['fields']):raise ValueError('day facts archive row fields differ')
                row=dict(zip(table['fields'],values));code=row['code']
                if code not in members:continue
                if row['date']!=day:raise ValueError('day facts archive SHSZ date differs')
                qualification='identity_unverified'if code in unverified else'qualified'
                status=row['tradestatus']
                if status not in ('0','1')and qualification=='qualified':qualification='state_unverified';state_unknown+=1
                rows.append([day,convert(code),row['close'],row['preclose'],row['volume'],row['turn'],status,qualification])
            for code in sorted(s for s in members if s.startswith('bj.')):
                check();symbol=code[3:];raw=history.get(symbol,{}).get(day);capital_row=shares.get((day,symbol))
                if raw is None:continue
                if capital_row is None:raise ValueError('day facts archive dated capital missing')
                close=Decimal(str(raw['jrsp']));prior=Decimal(str(raw['zrsp']));volume=Decimal(str(raw['cjl']))
                denominator=Decimal(str(capital_row['FREE_SHARES_A']))
                if (close!=Decimal(str(capital_row['CLOSE_PRICE']))or not close>0 or not prior>0
                        or not volume>0 or volume!=volume.to_integral_value()or not denominator>0
                        or denominator!=denominator.to_integral_value()):
                    raise ValueError('day facts archive dated capital or quote differs')
                with localcontext()as context:
                    context.prec=60;turn=volume*100/denominator
                if (turn>5)!=(20*volume>denominator):raise ValueError('day facts archive exact threshold differs')
                rows.append([day,convert(code),str(close),str(prior),str(volume),str(turn),'1',
                    'identity_unverified'if code in unverified else'qualified'])
            value=dict(schema='guanheng.daily-source-facts.v1',date=day,members=sorted(convert(s)for s in members),fields=FIELDS,rows=rows,
                units=dict(close_reference='CNY',preclose='CNY',volume='share',turn='percent_of_float'),
                stats=dict(identity_unverified_count=len(unverified),state_unverified_count=state_unknown,missing_float_count=0,
                    special_reference_count=None,halted_with_trades_count=None),
                provenance=dict(packet_sha256=binding_sha,universe_sha256=universe_sha,source_received_at=max([item['received_at'],*received])),
                qualification=dict(membership_method='listing_intervals_latest_identity',membership_as_of=universe['history_reconstructed_as_of'],
                    turnover_method='vendor_current_revised_date_series',point_in_time=False,first_available_at=None))
            yield validate_day_facts(value)
        for value in sorted(recent.values(),key=lambda v:v['date']):check();yield validate_day_facts(value)
    descriptor=prepare_facts_catalog(days(),output)
    output=Path(output);(output/'history-binding.json').write_bytes(binding_body)
    (output/'source-inputs.json').write_bytes(encode(dict(schema='guanheng.daily-facts-inputs.v1',
        binding_sha256=binding_sha,  # 该重构的完整来源绑定。
        source_objects=sorted(used),  # 本次实际读取并核SHA的全部原始对象，原仓库保留。
        SDK_calls=0,  # 本入口只消费已归档字节。
        original_received_times_preserved=True)))  # source_received_at保留各供应商原记录时刻。
    return descriptor
