"""原采集owner的有界时间投影；不保存报价或取得分钟完整性资格。"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import math
import re
import threading


SHANGHAI = timezone(timedelta(hours=8))
MARKETS = {'SH': 'SSE', 'SZ': 'SZSE', 'BJ': 'BSE'}


@dataclass(frozen=True)
class QuoteObservation:
    source_time_ms: int  # 最近成功交付原生批次中该证券的源epoch毫秒；保持原值，不与接收时刻互换。
    received_at: float  # 同批消费回调观察的本机epoch秒；不表示交易所时间或原生归档完成。
    delivered_ticks: int  # 本实例成功整包交付后该证券累计出现次数；不等于成交笔数或分钟条数。


class CollectionCoverage:
    """接收线程只更新时间/次数；管理线程复制投影，容量固定为本次配对集合。"""
    def __init__(self, symbols, *, native_types=None):
        if (type(symbols) is not list or not 1 <= len(symbols) <= 10000
                or len(set(symbols)) != len(symbols)
                or any(type(s) is not str or re.fullmatch(r'[0-9]{6}\.(SH|SZ|BJ)', s) is None for s in symbols)):
            raise ValueError('collection coverage symbols invalid')
        self.symbols = tuple(sorted(symbols))  # 本实例原QST配对集合；资料更新仅产生差异，不暗中改变订阅。
        self._allowed = frozenset(symbols)  # 报价准入与有界投影共享同一清单。
        self._types = dict(native_types or {})  # 原基础资料声明的stock/etf/index；未知保留unknown。
        if (not set(self._types) <= self._allowed
                or any(value not in ('stock', 'etf', 'index', 'unknown') for value in self._types.values())):
            raise ValueError('collection native classification invalid')
        self._rows = {}  # 仅成功交付证券的纯时间/计数；从未收到证券在投影中显式为空。
        self._reference = None  # 最近验证的完整或partial动态名册；来源失败时沿原成功事实保留。
        self._reference_state = 'waiting_reference_publication'  # 唯一资料owner尚未发布固定引用，区别于Source能力状态。
        self._guard = threading.Lock()  # 仅保护本对象；持锁期间不调用原生、来源或磁盘。

    def accept(self, ticks, observed):
        """成功整包交付后调用；先整包校验再改变投影，失败不留下部分时间状态。"""
        if type(observed) not in (int, float) or not math.isfinite(observed) or observed <= 0:
            raise ValueError('collection coverage receipt clock invalid')
        selected = []
        for symbol, row in ticks.items():
            stamp = row['time']
            if (symbol not in self._allowed or type(stamp) not in (int, float) or not math.isfinite(stamp)
                    or not 0 < stamp < 253402300800000 or stamp != int(stamp)):
                raise ValueError('collection coverage source identity invalid')
            selected.append((symbol, int(stamp)))  # 原QST允许整值float毫秒；纯投影编码为同值整数，不改变报价。
        with self._guard:
            for symbol, stamp in selected:
                previous = self._rows.get(symbol)
                self._rows[symbol] = QuoteObservation(stamp, observed,
                    1 if previous is None else previous.delivered_ticks + 1)

    def adopt_reference(self, value, state='captured'):
        """仅接收原capture_reference已验证v2资料；未知分母沿原逐组状态保持。"""
        from .security_reference import _reference_catalog
        if state != 'captured':
            raise ValueError('collection reference adoption state invalid')
        value = _reference_catalog(value)
        if value['schema'] != 'guanheng.security-reference.v2':
            raise ValueError('collection coverage requires dynamic reference')
        # 再编码脱离调用方的可变容器，验证与传递沿既有资料合同。
        import json
        detached = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
        with self._guard:
            self._reference, self._reference_state = detached, state

    def reference_waiting(self, state):
        """来源能力或暂时失败改变观察状态，最近成功名册继续保留。"""
        if state not in ('waiting_reference_publication', 'pending', 'unavailable'):
            raise ValueError('collection reference state invalid')
        with self._guard:
            self._reference_state = state

    def snapshot(self, observed):
        """返回分证券源/接收时刻及逐类集合差异；当日报价不冒充完整分钟。"""
        if type(observed) not in (int, float) or not math.isfinite(observed) or observed <= 0:
            raise ValueError('collection coverage observation clock invalid')
        today = datetime.fromtimestamp(observed, SHANGHAI).date()
        with self._guard:
            rows, reference, reference_state = dict(self._rows), self._reference, self._reference_state
        identities = {} if reference is None else reference['securities']
        # 市场采用显式表；类型沿资料声明，不按证券代码前缀推断。
        qmt_identity = {MARKETS[s.split('.')[1]] + '.' + s.split('.')[0]: s for s in self.symbols}
        all_ids = sorted(set(qmt_identity) | set(identities))
        projected, known_missing = [], []
        for identity in all_ids:
            exchange, code = identity.split('.')
            qmt = qmt_identity.get(identity)
            quote = None if qmt is None else rows.get(qmt)
            detail = identities.get(identity)
            security_type = detail['security_type'] if detail is not None else self._types.get(qmt, 'unknown')
            source_day = None if quote is None else datetime.fromtimestamp(quote.source_time_ms / 1000, SHANGHAI).date()
            quote_state = ('unsubscribed' if qmt is None else 'not_received' if quote is None
                           else 'future_source' if source_day > today else 'old_source_day' if source_day < today else 'observed_today')
            if qmt is None:
                known_missing.append(identity)
            projected.append(dict(
                symbol=identity,  # WT规范证券身份，市场来自原后缀映射。
                market=exchange,  # SSE/SZSE/BSE，保留未接入市场的真实已知名册项。
                security_type=security_type,  # 原Source分类优先；无Source时仅沿基础资料声明。
                subscribed=qmt is not None,  # 本次不可变配对集合是否包含该证券。
                quote_state=quote_state,  # 仅描述最后成功交付报价的日期关系，不授分钟完整性。
                source_time_ms=None if quote is None else quote.source_time_ms,  # 原源epoch毫秒，未知为None。
                received_at=None if quote is None else quote.received_at,  # 回调观察epoch秒，未知为None。
                delivered_ticks=0 if quote is None else quote.delivered_ticks))  # 本实例成功交付次数，尚无交付为0。
        groups = []
        declarations = [] if reference is None else reference['provenance']['groups']
        for market in ('SH', 'SZ', 'BJ'):
            for kind in ('stock', 'etf', 'index', 'unknown'):
                exchange = MARKETS[market]
                selected = [r for r in projected if r['market'] == exchange and r['security_type'] == kind]
                declared = next((g for g in declarations if g['market'] == market and g['security_type'] == kind), None)
                groups.append(dict(
                    market=market, security_type=kind,  # 原市场×类型分组，unknown显式保留。
                    reference_state='unknown' if declared is None else declared['state'],  # 未取得分组保持unknown。
                    expected_count=None if declared is None else declared['expected_count'],  # 完整Source分母，未知为None。
                    known_count=sum(r['symbol'] in identities for r in selected),  # 本份动态名册已取得数量。
                    subscribed_count=sum(r['subscribed'] for r in selected),  # 实际配对集合中的本组数量。
                    missing_subscription_count=sum(not r['subscribed'] for r in selected),  # 已知名册且尚未订阅。
                    outside_reference_count=sum(r['subscribed'] and r['symbol'] not in identities for r in selected),  # 原订阅中未在本份名册出现的保留成员。
                    observed_today_count=sum(r['quote_state'] == 'observed_today' for r in selected),  # 今日源时间的成功交付数。
                    not_received_count=sum(r['quote_state'] == 'not_received' for r in selected),  # 已订阅但本实例从未成功交付。
                    old_source_day_count=sum(r['quote_state'] == 'old_source_day' for r in selected)))  # 本实例接收了旧交易日源值。
        return dict(
            schema='qmt.collection-coverage.v1',  # 本覆盖投影模式，独立于既有64KiB采集状态。
            observed_at=observed,  # 管理线程制作投影的本机epoch秒。
            trading_date=today.isoformat(),  # 观察时刻的北京时间日期；节假日资格仍归官方日历。
            reference_state=reference_state,  # 最近资料观察结果，失败时保留旧成功名册。
            reference_catalog_id=None if reference is None else reference['provenance']['catalog_id'],  # 原Source名册身份。
            reference_captured_at=None if reference is None else reference['provenance']['captured_at'],  # 原名册UTC捕获时刻。
            reference_source_as_of=None if reference is None else reference['provenance']['source_as_of'],  # 独立资料时点，未知为None。
            subscribed_count=len(self.symbols),  # 原QST配对集合数量，区别于今日收到报价的证券数。
            groups=groups,  # 有界逐市场/类型对照，未知分母不推算。
            symbols=projected,  # 各证券最后成功交付的纯时间及计数，不含报价正文。
            missing_subscriptions=known_missing,  # 已知名册中原配对集合尚未包含的规范身份。
            minute_coverage='not_evaluated')  # 分钟需实际Reader核对，本报价投影不授完整性。
