"""已核WT原件的轻量按日索引；只保存展示值，不保存第二份请求或完整报告。"""
from dataclasses import dataclass
from fractions import Fraction
import json
from types import MappingProxyType

from .backtest_performance import _fraction
from .strategy_replay_facts import _decimal

POSITION_FIELDS=('date','symbol','quantity','realized_cny','floating_cny')
TRADE_FIELDS=('index','date','time','symbol','side','direction','action','price','quantity','fee_cny')


@dataclass(frozen=True)
class DayView:
    """单报告可重建索引；外层owner逐次重核原件SHA后才允许读取。"""
    identity: tuple  # run/receipt/report三个固定身份；不绑定路径别名或展示名称。
    proof: tuple  # (相对文件路径,SHA,原读取上限)；原请求/结果/安装/基材/输出完整集合。
    dates: frozenset  # 真实报告交易日YYYYMMDD；不补日期。
    captures: frozenset  # 具有原报告capture的日期；与CSV可用性联合解释。
    positions: object  # 只读日期映射，值为原CSV字段不可变tuple，外部投影均复制。
    trades: tuple | None  # 原成交顺序不可变tuple；None表示未适配而非无成交。
    by_day: object  # 只读日期到原成交tuple集合；避免按日请求反复扫描全历史。
    positions_available: bool  # 原positions.csv已适配，缺失保持未知。
    summary_json: str  # 紧凑逐日悬停投影；仅字符串缓存，不暴露可变对象。
    visuals_json: str  # 同身份日收益/回撤/成交计数投影；原WT资金仍由报告owner持有。
    configuration_json: str | None = None  # 同一原件的轻量模型DTO；未知/派生失败仍走原配置读取。

    def ledger(self,day,offset,limit):
        """返回独占小DTO；全体成交仍沿原分页，不从摘要补金融事实。"""
        rows=self.trades if day is None else self.by_day.get(day,())
        rows=rows or ()
        return dict(schema='nbw-ledger-v1',run_id=self.identity[0],receipt_sha256=self.identity[1],
            report_sha256=self.identity[2],date=day,positions_available=self.positions_available and day in self.captures,
            positions=[dict(zip(POSITION_FIELDS,row)) for row in self.positions.get(day,())],
            trades_available=self.trades is not None,total=len(rows),offset=offset,
            trades=[dict(zip(TRADE_FIELDS,row)) for row in rows[offset:offset+limit]])


def build_day_view(*,receipt,receipt_sha,report,trades,positions,proof,visuals,check,configuration=None):
    """由完整原件准入后的值构建一次；数量聚合使用有理数，保持原CSV精度。"""
    identity=(receipt['run_id'],receipt_sha,receipt['report_sha256'])
    dates=frozenset(row['trading_date'] for row in report['records'])
    captures=frozenset(row['trading_date'] for row in report['records'] if row.get('capture') is not None)
    by_position={};by_trade={};trade_values=None if trades is None else []
    for row in positions or ():
        check();by_position.setdefault(row['date'],[]).append(tuple(row[k] for k in POSITION_FIELDS))
    for row in trades or ():
        check();value=tuple(row[k] for k in TRADE_FIELDS)
        trade_values.append(value);by_trade.setdefault(row['date'],[]).append(value)
    points=[]
    for day in sorted(dates):
        check();holdings=None
        if positions is not None and day in captures:
            holdings=[[row[1],row[2]] for row in by_position.get(day,())]
        sides={'buy':{},'sell':{}};other=0
        for row in by_trade.get(day,()):
            check();symbol,side,quantity=row[3],row[4],row[8]
            if side in sides:sides[side][symbol]=sides[side].get(symbol,Fraction(0))+_fraction(quantity)
            else:other+=1
        # [交易日,持仓(code/份)或未知,当日买入(code/份)或未知,卖出或未知,其它成交笔数或未知]。
        points.append([day,holdings,*([[symbol,_decimal(quantity)] for symbol,quantity in sorted(sides[side].items())]
            if trades is not None else None for side in ('buy','sell')),other if trades is not None else None])
    summary=dict(schema='nbw-day-summaries-v1',run_id=identity[0],receipt_sha256=identity[1],report_sha256=identity[2],points=points)
    encode=lambda value:json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False)
    return DayView(identity,tuple(proof),dates,captures,MappingProxyType({day:tuple(rows) for day,rows in by_position.items()}),
        None if trade_values is None else tuple(trade_values),MappingProxyType({day:tuple(rows) for day,rows in by_trade.items()}),
        positions is not None,encode(summary),encode(visuals),None if configuration is None else encode(configuration))
