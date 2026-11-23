"""策略参考市值：页面只投影最近成功报价，网络读取由独立有界owner承担。"""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
import logging
from threading import Lock
from time import monotonic
from zoneinfo import ZoneInfo

from guanheng_market_client import API_VERSION, MAX_SYMBOLS, MarketClient, validate_response
from .reading import BoundedReader, ReadCapacityError

LOG = logging.getLogger(__name__)


def _rows(strategy):
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
    return rows


def _stamp(quote):
    clock = quote['action_time']
    return datetime.strptime(f"{quote['date']}{clock // 1000:06d}", '%Y%m%d%H%M%S').replace(
        tzinfo=ZoneInfo('Asia/Shanghai'), microsecond=(clock % 1000) * 1000)


def _apply_one(row, quote, observed):
    stamp = _stamp(quote)
    previous = row.get('market_value_observed_at')
    if stamp > observed or previous is not None and stamp < datetime.fromisoformat(previous):
        return False
    with localcontext() as context:
        context.prec = 48
        value = (Decimal(str(quote['price'])) * row['broker_quantity']).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
    row.update(market_value_cny=format(value, 'f'),
        market_value_observed_at=stamp.isoformat(), market_value_basis='last-quote')
    return True


def _apply(rows, snapshots):
    observed = datetime.now(timezone.utc)
    results = {}
    for quote in snapshots:
        row = rows.get(quote['symbol'])
        if row is None:
            continue
        try:
            if _apply_one(row, quote, observed):
                results[quote['symbol']] = None
        except (ValueError, ArithmeticError, KeyError, TypeError) as error:
            # 来源合法数值也可能超出当前金额表示能力；只隔离这一证券的可选市值。
            results[quote['symbol']] = type(error).__name__
    return results


class PositionQuoteOwner:
    """只拥有可重建的报价副本；实际份额每次取本轮策略记录，价格不参与交易。"""
    def __init__(self, settings, client_factory=None):
        self.settings = settings  # 本App固定的只读报价来源及原网络预算。
        self.factory = client_factory or MarketClient  # 每批在唯一worker中创建客户端。
        self.reader = BoundedReader(workers=1, capacity=1) if settings.position_quote_url else None  # 报价专用单worker，未配置来源时不创建。
        self.lock = Lock()  # 仅保护有界内存索引，不持锁进行网络读取或线程回收。
        self.cache = OrderedDict()  # 最近成功的完整已验报价，最多协议MAX_SYMBOLS项。
        self.pending = OrderedDict()  # 下批待刷证券，去重且同样有界；满额淘汰最旧展示需求。
        self.future = None  # 唯一已提交批次，未完成时所有页面合并需求。
        self.closing = False  # 停止后不再受理刷新，已有读取仍由原worker回收。
        self.last_error = None  # 最近失败阶段/类型；仅变化时记日志，成功恢复后清除。
        self.projection_errors = OrderedDict()  # 每证券最近投影错误，最多64项，按变化去重日志。

    def start(self):
        if self.reader is not None:
            self.reader.start()

    @staticmethod
    def _remember(index, key, value):
        index[key] = value
        index.move_to_end(key)
        while len(index) > MAX_SYMBOLS:
            index.popitem(last=False)

    def project(self, strategy):
        rows = _rows(strategy)
        if not rows or self.reader is None:
            return
        with self.lock:
            cached = []
            for symbol in rows:
                if symbol in self.cache:
                    cached.append(deepcopy(self.cache[symbol])); self.cache.move_to_end(symbol)
                if not self.closing:
                    self._remember(self.pending, symbol, None)
            if not self.closing and (self.future is None or self.future.done()):
                deadline = monotonic() + self.settings.wondertrader_market_timeout_seconds
                try:
                    self.future = self.reader.submit(lambda _remaining: self._refresh(deadline), deadline)
                except ReadCapacityError:
                    pass  # 后续页面读取仍可推进同一有界需求；已有报价继续可读。
        changes = []
        outcomes = _apply(rows, cached)
        with self.lock:
            for symbol, error in outcomes.items():
                previous = self.projection_errors.get(symbol)
                if error is None:
                    self.projection_errors.pop(symbol, None)
                else:
                    self._remember(self.projection_errors, symbol, error)
                if previous != error:
                    changes.append((symbol,error))
        for symbol, error in changes:
            if error is None:
                LOG.info('position_quote_projection_recovered symbol=%s',symbol)
            else:
                LOG.warning('position_quote_projection_unavailable symbol=%s error_type=%s',symbol,error)

    def _refresh(self, deadline):
        started = monotonic()
        symbols = []
        phase = 'select'
        try:
            with self.lock:
                if self.closing:
                    return
                symbols = list(self.pending)
                self.pending.clear()
            if not symbols or monotonic() >= deadline:
                return
            phase = 'client'
            client = self.factory(self.settings.position_quote_url,
                self.settings.position_quote_token.get_secret_value(), timeout=deadline-monotonic())
            request = dict(api_version=API_VERSION, action='quotes.query', symbols=symbols)
            phase = 'source_query'
            response = client.quotes_query(symbols)
            phase = 'validate'
            reply = validate_response(response, request)
            if reply['status']['code'] != 'Ok' or reply['data']['metadata']['qualification'] not in (
                'NativeVerified', 'ProductionQualified',
            ):
                raise ValueError('unqualified_position_quote')
            phase = 'publish'
            with self.lock:
                if self.closing:
                    return
                for quote in reply['data']['snapshots']:
                    if _stamp(quote) > datetime.now(timezone.utc):
                        continue  # 未来时钟不能覆盖最近成功报价，后续合法旧时点仍可恢复。
                    previous = self.cache.get(quote['symbol'])
                    if previous is None or (quote['date'], quote['action_time']) >= (previous['date'], previous['action_time']):
                        self._remember(self.cache, quote['symbol'], deepcopy(quote))
                recovered = self.last_error is not None
                self.last_error = None
            if recovered:
                LOG.info('position_quote_recovered symbols=%d elapsed_ms=%.1f',len(symbols),(monotonic()-started)*1000)
        except Exception as error:
            kind = (phase,type(error).__name__)
            with self.lock:
                changed = self.last_error != kind
                self.last_error = kind
            if changed:
                LOG.warning('position_quote_unavailable phase=%s error_type=%s symbols=%s elapsed_ms=%.1f budget_ms=%.1f',
                    phase,type(error).__name__,','.join(symbols),(monotonic()-started)*1000,max(0,deadline-started)*1000)

    def close(self, timeout):
        with self.lock:
            self.closing = True
            self.pending.clear()
            future = self.future
        if future is not None:
            future.cancel()
        return self.reader is None or self.reader.close(timeout)

    @property
    def live_threads(self):
        return 0 if self.reader is None else self.reader.live_threads


def project_latest_position_values(strategy, quote_owner=None):
    """页面仅投影内存并合并刷新；缺owner的独立读取保留原WT值。"""
    if quote_owner is not None:
        quote_owner.project(strategy)
