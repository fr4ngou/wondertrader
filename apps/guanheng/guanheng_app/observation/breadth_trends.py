"""广度趋势的单一公式：原RANA口径、EMA预热和MSI累计起点分别登记。"""
import math
from .contracts import ObservationError


class _EMA:
    def __init__(self, period):
        self.period,self.count,self.total,self.value=period,0,0.0,None

    def add(self,value):
        self.count+=1
        if self.count<=self.period:
            self.total+=value
            if self.count==self.period:self.value=self.total/self.period
        else:self.value+=2/(self.period+1)*(value-self.value)
        return self.value


def trend_rows(breadth, rana, *, trading_days=(), check=lambda:None):
    """按完整历史计算后才筛选查询日期；缺值/缺交易日切段并重新预热。"""
    indexed={row['date']:row for row in rana}
    positions={day:index for index,day in enumerate(sorted(set(trading_days)))}
    results=[];previous=None;start=None;count=0;cumulative=0.0;anchor=None
    fast,slow,thrust=_EMA(19),_EMA(39),_EMA(10)
    for row in breadth:
        check();day=row['date'];a=row.get('advancing_count');d=row.get('declining_count')
        ratio=indexed.get(day,{}).get('rana')
        valid=all(type(v) in (int,float) and math.isfinite(v) for v in (a,d,ratio)) and a>=0 and d>=0 and a+d>0
        gap=previous in positions and day in positions and positions[day]!=positions[previous]+1
        if not valid or gap:
            fast,slow,thrust=_EMA(19),_EMA(39),_EMA(10)
            start=None;count=0;cumulative=0.0;anchor=None
        output=dict(date=day,msi=None,oscillator=None,breadth_thrust=None,net_advances=None,
            warmup_observations=0,seed_start=None,cumulative_start=None,
            market_count=row.get('market_count'),unclassified_count=row.get('unclassified_count'),available_at=None)
        if valid:
            if not math.isclose(ratio,1000*(a-d)/(a+d),rel_tol=1e-10,abs_tol=1e-8):
                raise ObservationError('breadth_ratio_mismatch','RANA与同日涨跌家数口径不一致',422)
            start=start or day;count+=1
            f,s,b=fast.add(ratio),slow.add(ratio),thrust.add(a/(a+d))
            oscillator=None if f is None or s is None else f-s
            if oscillator is not None:
                anchor=anchor or day;cumulative+=oscillator
            output.update(msi=cumulative if oscillator is not None else None,oscillator=oscillator,
                breadth_thrust=b,net_advances=a-d,warmup_observations=count,seed_start=start,cumulative_start=anchor)
        results.append(output);previous=day
    return results


def definition(kind,scope):
    msi=kind=='msi';metric=kind+'.'+scope
    label=('MSI · 麦克莱伦累计指标' if msi else 'Breadth Thrust · 广度推力')+(' · 沪深北A股' if scope=='ashare' else ' · 沪深A股')
    primary='msi' if msi else 'breadth_thrust'
    formula=('沿原RANA=1000×(上涨−下跌)/(上涨+下跌)；震荡器=EMA19(RANA)−EMA39(RANA)；MSI为震荡器逐日累计。'
        if msi else 'Breadth Thrust=EMA10(上涨家数/(上涨家数+下跌家数))；平盘不进入分母。')
    schema=dict(date=dict(label='观察日',unit='日期'),available_at=dict(label='历史首次可知时间',unit='时间，未知留空'),
        msi=dict(label='MSI累计值',unit='无量纲',required=False),oscillator=dict(label='麦克莱伦震荡器',unit='无量纲'),
        breadth_thrust=dict(label='广度推力',unit='无量纲',required=False),net_advances=dict(label='上涨减下跌家数',unit='只'),
        warmup_observations=dict(label='本段连续有效观察数',unit='条',data_type='integer'),
        seed_start=dict(label='EMA预热起始日',unit='日期'),cumulative_start=dict(label='MSI累计起始日',unit='日期'),
        market_count=dict(label='同日股票池数量',unit='只'),unclassified_count=dict(label='涨跌分类尚缺数',unit='只'))
    return dict(id=metric,board='breadth',label=label,definition_version=metric+'/1',frequency='交易日日终',
        source='同一冻结版本的广度与RANA观察，股票池范围保持',
        source_url='https://chartschool.stockcharts.com/table-of-contents/market-indicators/mcclellan-summation-index' if msi else 'https://www.mcoscillator.com/learning_center/weekly_chart/a_breadth_thrust_signal/',
        unit='无量纲',parameters=False,primary_field=primary,field_schema=schema,formula=formula,
        input_metrics=['breadth.'+scope,'rana.'+scope],
        reading='比较同一股票池广度的变化；预热、累计起点和分类尚缺数分别保留。',
        lines=[dict(key=primary,name='MSI' if msi else 'Breadth Thrust',unit='无量纲',color='#d68b24' if msi else '#2479b6',
            panel='main',shown=True,formula=formula,reading='同一数据起点内观察趋势；不按可见窗口重新计算。')],
        reference_levels=[dict(value=0,name='累计零点',color='#8993a0')] if msi else [dict(value=.4,name='0.40',color='#4f9e76'),dict(value=.615,name='0.615',color='#bf626c')],
        limitations=['EMA以本段最初N个有效观察的算术均值为种子；MSI至少39期，广度推力至少10期，预热阶段留空。',
            'MSI在首个可计算震荡器之前以0为累计基准，首值等于首个震荡器；日期逐行显示，切换窗口不改变起点。',
            '本系统采用原千倍RANA尺度；累计起点和股票池改变会改变MSI绝对水平，不直接套用其他市场阈值。',
            '缺值或已知交易日缺口切断连续段并重新预热，不跨缺口累计。历史首次可知时间未知。',
            '广度推力0.40和0.615为参考水平；两线并不单独构成已确认的十日推力事件。'],
        how_to_read=dict(purpose=label,signals=[],boundary='同时核对股票池、有效观察数及累计起点。'))


def attach_trends(datasets,definitions,tables,*,check=lambda:None):
    calendar=tables.get('source.cn_calendar',[])
    days=[r['date'] for r in calendar if r.get('is_open') == 1]
    for scope in ('shsz','ashare'):
        breadth=datasets.get('breadth.'+scope,[]);rana=datasets.get('rana.'+scope,[])
        if not breadth or not rana:continue
        rows=trend_rows(breadth,rana,trading_days=days,check=check)
        for kind in ('msi','breadth.thrust'):
            metric=kind+'.'+scope;definitions[metric]=definition(kind,scope);datasets[metric]=rows


def attach_benchmark(datasets,definitions,tables):
    """原market.sh000001表的只读投影；指数身份与源表继续保持唯一。"""
    key='market.sh000001';prices=tables.get(key,[])
    if not prices:return
    datasets[key]=[dict(date=r['date'],close=r.get('close'),open=r.get('open'),high=r.get('high'),low=r.get('low'),available_at=None) for r in prices]
    schema=dict(date=dict(label='交易日',unit='日期'),available_at=dict(label='历史首次可知时间',unit='时间，未知留空'))
    schema.update({k:dict(label='上证指数'+label,unit='指数点',required=k=='close') for k,label in [('close','收盘'),('open','开盘'),('high','最高'),('low','最低')]})
    definitions[key]=dict(id=key,board='breadth',label='上证指数 · 原始日线基准',definition_version='market.sh000001/1',
        frequency='交易日日频',source='现有统一指数来源表market.sh000001',source_url='https://www.sse.com.cn/market/price/trends/',
        unit='指数点',parameters=False,primary_field='close',field_schema=schema,
        formula='原始上证指数日线，同日原值，不插值、不跨日沿用。',reading='四组观察共用同一上证基准。',
        lines=[dict(key='close',name='上证指数',unit='指数点',color='#c65761',panel='main',shown=True,formula='原始收盘',reading='基准与指标各自保留实际缺口。')],
        trading_days=sorted({row['date'] for row in tables.get('source.cn_calendar',[]) if row.get('is_open')==1}),
        limitations=['保持原market.sh000001身份和原始单位；数据补齐由指数来源owner提供。'])
