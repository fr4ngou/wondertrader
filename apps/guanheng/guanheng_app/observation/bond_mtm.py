"""原基金样本45日假定重估续接；不改变已有模型行或推定真实每日持仓。"""
from bisect import bisect_right
from datetime import date, datetime, timezone
import math
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .source_fetch import SourceFailure
from .provider_tables import parse_json

INDEX_ID='8a8b2ca0332abed20134ea76d8885831'
URL='https://yield.chinabond.com.cn/cbweb-mn/indices/singleIndexQuery'
TABLE='source.chinabond_wealth'
METRIC='bond.mtm45'


def history(fetch,config,start,end):
    """原新综合/财富/总值公开POST；全历史供季度基准匹配，原请求和总截止继续生效。"""
    tree=parse_json(fetch.post_readonly('https://yield.chinabond.com.cn/cbweb-mn/indices/queryTree?locale=zh_CN',{'locale':'zh_CN'}))
    matches=[row for row in tree if row.get('id')==INDEX_ID] if type(tree) is list else []
    if len(matches)!=1 or matches[0].get('name')!='中债-新综合指数':
        raise SourceFailure('bond_index_identity')
    params=dict(indexid=INDEX_ID,qxlxt='00',ltcslx='',zslxt='CFZS',lx='1',locale='')
    data=parse_json(fetch.post_readonly(config['url']+'?'+urlencode(params),{'locale':''}))
    if type(data) is not dict:
        raise SourceFailure('bond_index_schema')
    if data.get('dqcName')!={'00':'总值'} or data.get('dqcList')!=['00']:
        raise SourceFailure('bond_index_scope')
    values=data.get('CFZS_00')
    if type(values) is not dict or not 1<=len(values)<=20000:
        raise SourceFailure('bond_index_schema')
    rows,seen=[],set()
    for stamp,value in values.items():
        fetch.budget.remaining()
        if re.fullmatch(r'\d{13}',stamp) is None or type(value) not in (int,float) or not math.isfinite(value) or not 0<value<100000:
            raise SourceFailure('bond_index_value')
        local=datetime.fromtimestamp(int(stamp)/1000,timezone.utc).astimezone(ZoneInfo('Asia/Shanghai'))
        if (local.hour,local.minute,local.second,local.microsecond)!=(0,0,0,0) or local.date().year<2002:
            raise SourceFailure('bond_index_timestamp')
        day=local.date().isoformat()
        if day in seen:
            raise SourceFailure('bond_index_duplicate_date')
        seen.add(day)
        if day<=end:
            rows.append(dict(
                date=day,  # 原毫秒时间戳转上海交易日期；不顺延或补造日期。
                close=float(value),  # 原中债-新综合财富指数CFZS、总值00，单位指数点。
                available_at=None))  # 历史首次可知时刻未核实；本轮抓取时间归原Fetcher。
    if not rows:
        raise SourceFailure('bond_index_no_observations')
    fetch.records[-1]['parsed_document']=dict(index_id=INDEX_ID,index_name='中债-新综合指数',indicator='CFZS',term='00',unit='index_points',latest=max(row['date'] for row in rows))
    return {TABLE:sorted(rows,key=lambda row:row['date'])}


def calculate(day,quarters,stocks,bonds,common):
    """复用原季度选择、共同源日期基准与净资产分母；缺源返回未知。"""
    eligible=[row for row in quarters if (date.fromisoformat(day)-date.fromisoformat(row['date'])).days>=45
              and row.get('fund_records',0)>=1000]
    if not eligible:
        return None
    quarter=max(eligible,key=lambda row:row['date'])
    index=bisect_right(common,quarter['date'])-1
    if index<0:
        return None
    base=common[index]
    if day not in stocks or day not in bonds:
        return None
    B,S,C=(quarter.get(k) for k in ['bond_pct','stock_pct','cash_pct'])
    if any(type(value) not in (int,float) or not math.isfinite(value) or value<0 for value in [B,S,C]):
        raise SourceFailure('bond_model_quarter_value')
    if any(value<=0 for value in [stocks[base],bonds[base],stocks[day],bonds[day]]):
        raise SourceFailure('bond_model_index_value')
    rb,rs=bonds[day]/bonds[base],stocks[day]/stocks[base]
    other=100-B-S-C
    nav=B*rb+S*rs+C+other
    if not math.isfinite(nav) or nav<=0:
        raise SourceFailure('bond_model_denominator')
    return dict(
        estimate=100*B*rb/nav,  # 债券重估金额/假设净资产，百分数；沿原浮点运算次序。
        anchor_period=quarter['date'],  # 使用的基金季度报告期末；不是披露时间。
        anchor_date=base,  # 不晚于报告期末的最后股债共同日期，ISO日期。
        model_eligible_date=date.fromordinal(date.fromisoformat(quarter['date']).toordinal()+45).isoformat(),  # 原45自然日假定生效日，不声称实际可知。
        bond_index_value=bonds[day],  # 本日中债新综合财富指数原值，指数点。
        bond_index_base=bonds[base],  # 同源季度基准日指数原值，指数点。
        stock_index_base=stocks[base])  # 中证全指季度基准日收盘原值，指数点。


def extend(tables,datasets,*,check):
    """只追加旧尾日之后有完整真实输入的行；独立运行时缺少此表保持原模型。"""
    if TABLE not in tables or METRIC not in datasets:
        return
    stocks={row['date']:row['close'] for row in tables.get('source.csi_all',[])}
    bonds={row['date']:row['close'] for row in tables[TABLE]}
    common=sorted(set(stocks)&set(bonds))
    quarters=datasets.get('holdings_fund',[])
    reference={row['date']:row['close'] for row in tables.get('market.sh000001',[])}
    old=datasets[METRIC]
    last=max((row['date'] for row in old),default='2023-01-01')
    additions=[]
    for day in common:
        check()
        if day<=last:
            continue
        value=calculate(day,quarters,stocks,bonds,common)
        if value is None:
            continue
        additions.append(dict(
            date=day,  # 两个真实指数共有的观察日期，不补缺失日。
            reference=reference.get(day),  # 同日上证收盘，指数点；缺失时null。
            csi_all_reference=stocks[day],  # 同日中证全指原收盘，指数点。
            available_at=None,  # 模型历史首次可知时刻未知；45日是独立假定。
            **value))  # 同一纯公式产出的比例及基准说明；字段语义沿calculate。
    datasets[METRIC]=[*old,*additions]


def update_definition(definition):
    """沿原方法版本补充输入基准说明；旧行缺新元数据继续为未知。"""
    definition['input_metrics']=['holdings_fund']
    fields={
        'anchor_period':('基金季度报告期末','日期','原基金配置季度，不代表实际披露日'),
        'anchor_date':('股债共同基准日','日期','不晚于季度末的最后共同源日期'),
        'model_eligible_date':('模型假定可用日','日期','季度末加45自然日，实际披露时间未知'),
        'bond_index_value':('中债财富指数本日原值','指数点','中债-新综合、CFZS、总值00'),
        'bond_index_base':('中债财富指数基准原值','指数点','同一指数在共同基准日的原值'),
        'stock_index_base':('中证全指基准收盘','指数点','原中证全指共同基准日收盘'),
    }
    for key,(label,unit,description) in fields.items():
        definition['field_schema'][key]=dict(label=label,unit=unit,required=False,nullable=True,
            source='原模型已核股债输入及季度基准',formula=description,missing='旧行未登记时为空，区别于0')
    definition['limitations']=[text for text in definition.get('limitations',[]) if '最新性' not in text]
    note='新增模型使用已核中债新综合财富指数与同日中证全指；45自然日可用仍为模型假定。'
    if note not in definition['limitations']:
        definition['limitations'].append(note)
    definition['how_to_read']['boundary']='黄色是基金样本按原45日假定重估的模型，绿色是同日中证全指；真实日持仓与历史当时可得时间未知。'
    definition['reading']='基金季度样本按原45自然日假定，以中债新综合财富指数及中证全指重估；两条线分别读取百分比与指数点轴。'
