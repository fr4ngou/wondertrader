"""价格接续资格归数据owner；原未知责任与当前已可读价格分别判断。"""
from .daily_data_update import _load
from pathlib import Path
from .market_generation import read_fixed
from ..guanheng_market_client import strict_json


def _pending_symbols(descriptor,progress,observations):
    """按实际回读时固定的进度判定责任；缺省项续核原单项观察，不依赖本次rows长度。"""
    plan=_load(descriptor);observed={row['index']:row['state']for row in progress['rows']}if progress is not None else{}
    frozen=progress is not None and progress.get('schema')=='guanheng.daily-gap-readback-progress.v1'
    if frozen and (progress.get('plan_sha256')!=descriptor['sha256']
            or len(observed)!=len(progress['rows'])or set(observed)!={task['index']for task in plan['tasks']}):
        raise ValueError('price continuation complete readback progress differs')
    pending=set()
    for task in plan['tasks']:
        state=observed.get(task['index'])
        if state is None and not frozen:
            path=Path(observations)/('%06d.json'%task['index'])
            if path.exists():
                original=strict_json(read_fixed(path,maximum=1048576))
                if original['plan_sha256']!=descriptor['sha256']or original['row']['index']!=task['index']:
                    raise ValueError('price continuation original observation differs')
                state=original['row']['state']
        if state=='call_returned':continue
        code,market=task['symbol'].split('.')
        pending.add({'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[market]+'.'+code)
    return pending


def requires_price_continuation(price_result,prior_pending_symbols=(),*,stock_plan=None,
                                stock_progress=None,stock_observations=None):
    """股票和额外价格共用责任判断；stock_progress固定于股票回读前，不随恢复的新观察覆盖。"""
    pending=set(prior_pending_symbols)
    if stock_plan is not None:
        pending.update(_pending_symbols(stock_plan,stock_progress,stock_observations))
    if price_result['inputs']is not None:
        inputs=_load(price_result['inputs'])
        pending.update(_pending_symbols(inputs['plan'],inputs['preparation'],
            Path(price_result['inputs']['path']).parent/'gap-work'/'observations'))
    return any(symbol in price_result['securities']and not price_result['securities'][symbol]['target_readable']
               and price_result['securities'][symbol].get('reason')not in('source_halted_no_trade','before_listing','after_expiry')
               for symbol in pending)
