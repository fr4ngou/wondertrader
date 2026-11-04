"""价格接续资格归数据owner；原未知责任与当前已可读价格分别判断。"""
from .daily_data_update import _load


def _pending_symbols(descriptor,progress):
    """完整时点快照才授已返回资格；旧稀疏进度无法证明与回读同时，保守保留责任。"""
    plan=_load(descriptor)
    frozen=progress is not None and progress.get('schema')=='guanheng.daily-gap-readback-progress.v1'
    observed={row['index']:row['state']for row in progress['rows']}if frozen else{}
    if frozen and (progress.get('plan_sha256')!=descriptor['sha256']
            or len(observed)!=len(progress['rows'])or set(observed)!={task['index']for task in plan['tasks']}):
        raise ValueError('price continuation complete readback progress differs')
    pending=set()
    for task in plan['tasks']:
        state=observed.get(task['index'],'unattempted')
        if state=='call_returned':continue
        code,market=task['symbol'].split('.')
        pending.add({'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[market]+'.'+code)
    return pending


def requires_price_continuation(price_result,prior_pending_symbols=(),*,stock_plan=None,
                                stock_progress=None):
    """股票和额外价格共用责任判断；stock_progress固定于股票回读前，不随恢复的新观察覆盖。"""
    pending=set(prior_pending_symbols)
    if stock_plan is not None:
        pending.update(_pending_symbols(stock_plan,stock_progress))
    if price_result['inputs']is not None:
        inputs=_load(price_result['inputs'])
        pending.update(_pending_symbols(inputs['plan'],inputs['preparation']))
    return any(symbol in price_result['securities']and not price_result['securities'][symbol]['target_readable']
               and price_result['securities'][symbol].get('reason')not in('source_halted_no_trade','before_listing','after_expiry','not_price_instrument')
               for symbol in pending)
