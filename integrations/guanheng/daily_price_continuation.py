"""价格接续资格归数据owner；原未知责任与当前已可读价格分别判断。"""
from .daily_data_update import _load
from pathlib import Path
from .market_generation import read_fixed
from ..guanheng_market_client import strict_json


def requires_price_continuation(price_result,prior_pending_symbols=()):
    """仅对有原责任且目标Native仍缺的证券请求同日后继；不重派原SDK调用。"""
    pending=set(prior_pending_symbols)
    if price_result['inputs']is not None:
        inputs=_load(price_result['inputs']);plan=_load(inputs['plan']);progress=inputs['preparation']
        observed={}
        if progress is not None:observed={row['index']:row['state']for row in progress['rows']}
        for task in plan['tasks']:
            state=observed.get(task['index'])
            if state is None:
                path=Path(price_result['inputs']['path']).parent/'gap-work'/'observations'/('%06d.json'%task['index'])
                if path.exists():
                    original=strict_json(read_fixed(path,maximum=1048576))
                    if original['plan_sha256']!=inputs['plan']['sha256']or original['row']['index']!=task['index']:
                        raise ValueError('price continuation original observation differs')
                    state=original['row']['state']
            if state=='call_returned':continue
            code,market=task['symbol'].split('.')
            pending.add({'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[market]+'.'+code)
    return any(symbol in price_result['securities']and not price_result['securities'][symbol]['target_readable']
               and price_result['securities'][symbol].get('reason')not in('source_halted_no_trade','before_listing','after_expiry')
               for symbol in pending)
