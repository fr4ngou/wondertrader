"""策略持仓表的最近报价只读投影。"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
from time import monotonic
from zoneinfo import ZoneInfo

from guanheng_market_client import API_VERSION, MarketClient, MarketUnavailable, validate_response


def project_latest_position_values(strategy, settings, deadline, client_factory=None):
    """沿本轮实际归属份额及报价原时钟投影；估值和交易继续使用各自原口径。"""
    now = datetime.now(timezone.utc)
    valuation = strategy.get('owned_valuation') or {}
    expires = valuation.get('price_valid_until')
    current = (valuation.get('state') in ('actual', 'reference-fee-pending')
        and expires is not None and datetime.fromisoformat(expires) > now)
    rows = {}
    for row in strategy['positions']:
        if not row['broker_quantity'] or current and 'market_value_cny' in row:
            continue
        if 'market_value_cny' in row:
            row['market_value_basis'] = 'last-quote'
        code, exchange = row['symbol'].split('.')
        rows[{'SH': 'SSE', 'SZ': 'SZSE'}[exchange] + '.' + code] = row
    url = getattr(settings, 'position_quote_url', '')
    if not rows or not url or monotonic() >= deadline:
        return
    try:
        timeout = min(deadline - monotonic(), settings.wondertrader_market_timeout_seconds)
        if timeout <= 0:
            return
        client = (client_factory or MarketClient)(url, settings.position_quote_token.get_secret_value(), timeout=timeout)
        symbols = sorted(rows)
        request = dict(api_version=API_VERSION, action='quotes.query', symbols=symbols)
        reply = validate_response(client.quotes_query(symbols), request)
        if reply['status']['code'] != 'Ok' or reply['data']['metadata']['qualification'] not in (
            'NativeVerified', 'ProductionQualified',
        ):
            return
        observed = datetime.now(timezone.utc)
        for quote in reply['data']['snapshots']:
            row = rows[quote['symbol']]
            clock = quote['action_time']
            stamp = datetime.strptime(f"{quote['date']}{clock // 1000:06d}", '%Y%m%d%H%M%S').replace(
                tzinfo=ZoneInfo('Asia/Shanghai'), microsecond=(clock % 1000) * 1000)
            previous = row.get('market_value_observed_at')
            if stamp > observed or previous is not None and stamp < datetime.fromisoformat(previous):
                continue
            with localcontext() as context:
                context.prec = 48
                value = (Decimal(str(quote['price'])) * row['broker_quantity']).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
            row.update(market_value_cny=format(value, 'f'),
                market_value_observed_at=stamp.isoformat(), market_value_basis='last-quote')
    except (MarketUnavailable, ValueError, OSError, ArithmeticError, KeyError, TypeError):
        # 报价连接失败仅影响本列，本轮原持仓和估值继续返回。
        return
