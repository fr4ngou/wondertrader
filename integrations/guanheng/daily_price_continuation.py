"""价格接续资格归数据owner；原未知责任与当前已可读价格分别判断。"""
from .daily_data_update import _load
from .daily_gap_plan import load_gap_plan


def _pending_symbols(descriptor,progress,*,deadline=None,cancelled=lambda:False):
    """完整时点快照才授已返回资格；旧稀疏进度无法证明与回读同时，保守保留责任。"""
    plan=load_gap_plan(descriptor,deadline=deadline,cancelled=cancelled)
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
                                stock_progress=None,deadline=None,cancelled=lambda:False):
    """股票和额外价格共用责任判断；stock_progress固定于股票回读前，不随恢复的新观察覆盖。"""
    reference_pending=False  # 名册来源恢复责任，与原价格/HPR责任分别核验后共同决定接续。
    history=price_result.get('strategy_history')
    if history is not None and _load(history)['continuation_required']:
        return True  # 额外长窗口Source/预算待续核，即使本日短窗口已有价格也保持同日重试。
    scope=price_result.get('scope')
    if scope is not None:
        reference=_load(scope).get('reference_state',{})
        # 价格完成只证明已知名单；名册暂缺仍归原owner接续。captured的合法unsupported不触发空转。
        reference_pending=reference.get('state')in('waiting_reference_capability','reference_source_unavailable')
    pending=set(prior_pending_symbols)
    if stock_plan is not None:
        pending.update(_pending_symbols(stock_plan,stock_progress,deadline=deadline,cancelled=cancelled))
    if price_result['inputs']is not None:
        inputs=_load(price_result['inputs'])
        pending.update(_pending_symbols(inputs['plan'],inputs['preparation'],deadline=deadline,cancelled=cancelled))
    return reference_pending or any(symbol in price_result['securities']and not price_result['securities'][symbol]['target_readable']
               and price_result['securities'][symbol].get('reason')not in('source_halted_no_trade','before_listing','after_expiry','not_price_instrument')
               for symbol in pending)
