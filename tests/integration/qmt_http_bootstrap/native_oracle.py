"""人工可核算的源行oracle：原SPI值、公开限额结果及原统计日志互相约束。"""
import json,re

def verify(path,rows,result,cfg,check):
    observer=json.loads((path/'native-observer.json').read_text(encoding='utf-8'))
    def unique(kind):
        found={}
        for raw in rows[kind]:
            key=raw['m_strOrderSysID'] if kind=='order' else (raw['m_strTradeID'],raw['m_strOrderSysID'],raw['m_strInstrumentID'],raw['m_strExchangeID'],raw['m_strTradeDate'].replace('-',''))
            found.setdefault(key,raw)
        return list(found.values())
    orders=unique('order') if result.get('delivered',0)&2 else []
    deals=unique('deal') if result.get('delivered',0)&4 else []
    check(len(observer['orders'])==len(orders),'original-order-SPI-cardinality')
    check(len(observer['trades'])==len(deals),'original-trade-SPI-cardinality')
    # WT私有买卖/拒单数量槽没有公开getter；此处核实际SPI输入，不冒称读取了私有统计。
    raw_totals={side:dict(count=0,quantity=0,cancels=0,cancel_quantity=0,rejects=0,reject_quantity=0) for side in ('buy','sell')}
    for index,(actual,raw) in enumerate(zip(observer['orders'],orders)):
        status=raw['m_nOrderStatus'];q,f=raw['m_nVolumeTotalOriginal'],raw['m_nVolumeTraded'];active=status in (49,50,51,52,55)
        state=48 if status==56 else 53 if status in (53,54,57) else 98 if status in (51,52) else 49 if f else 51
        side='buy' if raw['m_nOffsetFlag']==48 else 'sell';slot=raw_totals[side];slot['count']+=1;slot['quantity']+=q
        if status==57:slot['rejects']+=1;slot['reject_quantity']+=q-f
        elif status in (53,54):slot['cancels']+=1;slot['cancel_quantity']+=q-f
        expected=dict(id=raw['m_strOrderSysID'],tag='',code=raw['m_strInstrumentID'],direction=48,offset=48 if side=='buy' else 49,state=state,flag=48,error=status==57,alive=active,quantity=q,filled=f,left=q-f if active else 0)
        check(actual==expected,'original-order-SPI-fields-'+str(index))
        view=json.loads((path/f'view-2-{index}.json').read_text(encoding='utf-8'))
        for name in ('m_nOrderStatus','m_nOffsetFlag','m_nVolumeTotalOriginal','m_nVolumeTraded','m_nVolumeTotal'):
            check(view['facts'][name]['value']==raw[name],'order-v2-raw-'+name+'-'+str(index))
        for name,value in (('orderState',state),('volLeft',expected['left']),('offsetType',expected['offset']),('userTag','')):
            check(view['abi'][name]['value']==value,'order-v2-ABI-'+name+'-'+str(index))
        check(view['price_type']['availability']=='unknown','order-unknown-price-type-'+str(index))
    totals={}
    for index,(actual,raw) in enumerate(zip(observer['trades'],deals)):
        side=raw['m_nOffsetFlag'];check(actual['code']==raw['m_strInstrumentID'] and actual['order']==raw['m_strOrderSysID'] and actual['direction']==48 and actual['offset']==(48 if side==48 else 49) and actual['quantity']==raw['m_nVolume'],'original-trade-SPI-fields-'+str(index))
        market='SSE' if raw['m_strExchangeID']=='SH' else 'SZSE';code=market+('.ETF.' if raw['m_strInstrumentID']=='510300' else '.STK.')+raw['m_strInstrumentID']
        slot=totals.setdefault(code,[0,0,0,0,0,0]);slot[0 if side==48 else 1]+=raw['m_nVolume']
        view=json.loads((path/f'view-3-{index}.json').read_text(encoding='utf-8'));check(view['facts']['m_nOffsetFlag']['value']==side and view['abi']['offsetType']['value']==(48 if side==48 else 49),'trade-v2-side-'+str(index))
    if result.get('delivered',0)&4:
        for raw in orders:
            code=('SSE' if raw['m_strExchangeID']=='SH' else 'SZSE')+'.STK.'+raw['m_strInstrumentID'];totals.setdefault(code,[0,0,0,0,0,0])
        pattern=re.compile(r'\[nqb\] (\S+) action stats updated, long opened: ([^,]+), long closed: ([^,]+), new long closed: ([^,]+), short opened: ([^,]+), short closed: ([^,]+), new short closed: (\S+)')
        observed={m[1]:list(map(float,m.groups()[1:])) for text in observer['native_logs'] if (m:=pattern.search(text))}
        check(observed==totals,'original-private-action-stat-log-oracle')
    risk=cfg['riskmon']['policy']['default'];order_count=len(orders);cancel_count=sum(r['m_nOrderStatus'] in (53,54) for r in orders)
    order_pass=order_count<risk['order_total_limits'];cancel_pass=order_pass and cancel_count<risk['cancel_total_limits']
    check(result.get('native_order_limit')==int(order_pass),'original-public-order-limit-count')
    check(result.get('native_cancel_limit')==int(cancel_pass),'original-public-cancel-limit-count')
    if not order_pass:check(any(f'entrust {order_count} times totally' in line for line in observer['native_logs']),'original-order-count-log')
    elif not cancel_pass:check(any(f'cancel {cancel_count} times totaly' in line for line in observer['native_logs']),'original-cancel-count-log')
    if result.get('delivered',0)&1:
        stock=next((row for row in rows['position'] if row['m_strInstrumentID']=='600000'),None);check(result.get('position')==(stock['m_nVolume'] if stock else 0) and result.get('available')==(stock['m_nCanUseVolume'] if stock else 0),'history-never-readds-position')
    (path/'native-oracle.json').write_text(json.dumps(dict(source_order_oracle=raw_totals,source_action_oracle=totals,public_order_count=order_count,public_cancel_count=cancel_count,private_quantity_getter='unavailable; actual SPI plus fixed native consumer source only'),indent=2),encoding='utf-8')
