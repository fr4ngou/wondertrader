"""同一官方日历验证与交易日规则；标准库模块供原观衡和WT采集共同调用。"""
from datetime import date, timedelta
import hashlib
import json


class CalendarFailure(ValueError):
    """固定日历准入失败码，调用者沿自身边界转换异常类型。"""


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def digest(body):
    return hashlib.sha256(body).hexdigest()


def _configuration(config,check):
    check()
    start = date.fromisoformat(config['coverage_start'])
    end = date.fromisoformat(config['coverage_end'])
    through = date.fromisoformat(config['verified_through'])
    if not start <= through <= end:
        raise CalendarFailure('official_calendar_coverage_invalid')
    closures = set(config['closed_dates'])
    if len(closures) != len(config['closed_dates']):
        raise CalendarFailure('official_calendar_duplicate_closure')
    for day in closures:
        check()
        date.fromisoformat(day)
    return start,end,through,closures


def _days(start,end,check):
    day=start
    while day<=end:
        check();yield day
        if day==end:return
        day+=timedelta(days=1)


def _is_open(day,closures):
    return day.weekday()<5 and day.isoformat() not in closures


def _verify(config,start,through,closures,check):
    """保持原开放日JSON摘要，逐日送入哈希，不物化历史列表。"""
    identity=hashlib.sha256();identity.update(b'[');first=True
    for day in _days(start,through,check):
        if _is_open(day,closures):
            if not first:identity.update(b',')
            identity.update(encode(day.isoformat()));first=False
    identity.update(b']')
    if identity.hexdigest()!=config['verified_open_dates_sha256']:
        raise CalendarFailure('official_calendar_verification_mismatch')


def last_open_day(config,end,*,check=lambda:None):
    """核同原开放日摘要后按原规则回看；原check约束迭代，内存与覆盖年数无关。"""
    start,last,through,closures=_configuration(config,check)
    day=date.fromisoformat(end)
    if not start<=day<=last:raise CalendarFailure('official_calendar_outside_coverage')
    _verify(config,start,through,closures,check)
    while day>=start:
        check()
        if _is_open(day,closures):return day.isoformat()
        if day==start:break
        day-=timedelta(days=1)
    raise CalendarFailure('official_calendar_outside_coverage')


def official_calendar(config,*,check=lambda:None):
    start,end,through,closures=_configuration(config,check)
    _verify(config,start,through,closures,check)
    rows=[dict(date=day.isoformat(),is_open=int(_is_open(day,closures))) for day in _days(start,end,check)]
    metadata = dict(id=config['id'], version=digest(encode(config)),
                    coverage_start=start.isoformat(), coverage_end=end.isoformat(),
                    verified_through=through.isoformat(), method=config['method'],
                    official_history_verified=True, evidence=config['evidence'])
    return rows, metadata


