"""WT数据侧复用唯一公开输入库取得定日事实；不构建或发布观察指标。"""
from datetime import datetime, timezone
import hashlib

from ..guanheng_market_client.daily_facts import FIELDS, STATS, validate_day_facts
from .market_generation import encode


def normalize_day_facts(capture, manifest, start, end):
    """同一原件解析函数输出字段/单位/资格；返回纯事实，不调用指标公式。"""
    from guanheng_app.observation.ashare_source import normalize_inputs
    inputs = normalize_inputs(capture, manifest, start, end)
    convert = lambda symbol: {'sh': 'SSE', 'sz': 'SZSE', 'bj': 'BSE'}[symbol[:2]] + '.' + symbol[3:]
    rows = []
    for original in inputs['rows']:
        value = dict(zip(inputs['fields'], original))
        value['symbol'] = convert(value.pop('code'))
        value['close_reference'] = value.pop('close')
        rows.append([value[key] for key in FIELDS])
    received = max(item['retrieved_at'] for item in capture.input_records if 'retrieved_at' in item)
    result = dict(
        schema='guanheng.daily-source-facts.v1',  # 固定定日事实合同，与指标结果分别保存。
        date=inputs['date'],  # 原件共同的交易日期YYYY-MM-DD。
        members=sorted(convert(symbol) for symbol in inputs['members']),  # 同日完整股票池，保留缺项证券。
        fields=FIELDS,  # 日期/身份/参考价/前收/成交股数/换手%/状态/资格的固定顺序。
        rows=rows,  # 原字符串值，价格参考只用于与WT原价核对。
        units=dict(close_reference='CNY', preclose='CNY', volume='share', turn='percent_of_float'),  # 原公开输入明确单位。
        stats={key: inputs['stats'][key] for key in STATS},  # 原解析阶段来源资格和缺股本事实，未计算行情指标。
        provenance=dict(
            packet_sha256=hashlib.sha256(encode(manifest)).hexdigest(),  # 原输入包的完整规范JSON身份。
            universe_sha256=inputs['universe_sha256'],  # 原定日股票池对象身份。
            source_received_at=received),  # 原输入的最晚实际接收UTC时刻，不替代数据日期。
        qualification=dict(
            membership_method='same_day_public',  # 同日公开身份原件准入，沿原池定义。
            membership_as_of=inputs['date'],  # 本股票池声明的观察日期。
            turnover_method='same_day_public',  # 同日公开原成交股数/流通股本，保留原单位。
            point_in_time=False,  # 本次捕获不授历史当时可知性。
            first_available_at=None))  # 未取得供应商首次可见时间，保持未知。
    return validate_day_facts(result)


def capture_day_facts(reader, fetch, source, day, *, now=None, retry_seconds=60, max_attempts=8,
                      admitted_records=(),retry_window_seconds=None,baostock_daily_timeout_seconds=None):
    """数据owner提供只存原件/回执的reader和有界fetch；网络/SDK沿原适配器。

    reader及fetch归调用线程，调用者持写锁并负责close。已有同日部件/原件复用，
    未完成输入保持可恢复；返回(packet,facts)，不修改观察current或指标结果。
    """
    from guanheng_app.observation.ashare_public import Archive
    archive = Archive(reader, fetch, source, now=now or datetime.now(timezone.utc),
                      retry_seconds=retry_seconds, max_attempts=max_attempts,
                      admitted_records=admitted_records, normalizer=normalize_day_facts, published_inputs=False,
                      retry_window_seconds=retry_window_seconds,
                      baostock_daily_timeout_seconds=baostock_daily_timeout_seconds)
    return archive.get(day)
