"""北京时间09:00计划身份；两日扫描与单窗口准入使用同一日历规则。"""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from .contracts import ObservationError

ZONE=ZoneInfo('Asia/Shanghai')


def local_now(now):
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ObservationError('invalid_schedule_clock','观察调度需要带时区的时钟',422)
    return now.astimezone(ZONE)


def due_windows(now,schedule,completed=()):
    local=local_now(now);floor=schedule.get('start_date');windows=[]
    for offset in (1,0):
        day=(local-timedelta(days=offset)).date()
        if floor and day.isoformat()<floor:continue
        when=datetime(day.year,day.month,day.day,9,tzinfo=ZONE)
        key=when.isoformat()
        if when<=local and key not in completed:windows.append((key,when))
    return windows


def window_as_of(key,now):
    try:
        when=datetime.fromisoformat(key);local=local_now(now)
        if (when.tzinfo is None or when.isoformat()!=key or when.utcoffset()!=timedelta(hours=8)
                or (when.hour,when.minute,when.second,when.microsecond)!=(9,0,0,0)
                or when>local or when.date()<(local-timedelta(days=1)).date()):
            raise ValueError('window outside bounded schedule')
        return (when-timedelta(days=1)).date().isoformat()
    except (ValueError,TypeError,OverflowError):
        raise ObservationError('invalid_schedule_window','观察计划窗口无效或尚未到期',422) from None
