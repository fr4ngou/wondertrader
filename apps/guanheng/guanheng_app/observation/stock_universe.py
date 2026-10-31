"""同源证券表的沪深上市日期准入；在线采集和归档补算共用。"""

from datetime import date
import re

from .contracts import ObservationError


def shsz_listings(fields, rows, *, check=lambda: None):
    """未知上市日拒绝生成市场分母；空退市日按供应商在市合同处理。"""
    check()
    required = {'code', 'type', 'ipoDate', 'outDate'}
    if len(set(fields)) != len(fields) or not required <= set(fields):
        raise ObservationError('stock_universe_schema', '证券表缺少股票身份或上市日期字段', 503)
    listings = {}
    for values in rows:
        check()
        if len(values) != len(fields) or any(type(value) is not str for value in values):
            raise ObservationError('stock_universe_schema', '证券表字段格式无效', 503)
        row = dict(zip(fields, values))
        if row['type'] != '1' or not row['code'].startswith(('sh.', 'sz.')):
            continue
        code, first, last = row['code'], row['ipoDate'], row['outDate']
        if re.fullmatch(r'(sh|sz)\.\d{6}', code) is None or code in listings:
            raise ObservationError('stock_universe_identity', '证券表股票身份无效或重复', 503)
        if not first:
            raise ObservationError('stock_listing_date_unknown', '股票上市日期缺失，暂不能确认历史股票池', 503)
        try:
            if date.fromisoformat(first).isoformat() != first:
                raise ValueError()
            if last and (date.fromisoformat(last).isoformat() != last or last <= first):
                raise ValueError()
        except ValueError:
            raise ObservationError('stock_listing_dates_invalid', '股票上市或退市日期无效', 503) from None
        listings[code] = (first, last)
        if len(listings) > 20000:
            raise ObservationError('stock_universe_capacity', '股票池超过已核容量', 503)
    return listings


def listed_codes(listings, day, *, check=lambda: None):
    """上市日计入，退市日退出；原调用者截止覆盖逐证券筛选。"""
    if date.fromisoformat(day).isoformat() != day:
        raise ObservationError('stock_day_invalid', '股票池日期无效', 422)
    result = set()
    for code, (first, last) in listings.items():
        check()
        if first <= day and (not last or last > day):
            result.add(code)
    return result
