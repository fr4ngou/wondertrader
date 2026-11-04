"""北京时间计划窗口；市场截止沿原交易日历，披露来源保留自然日期。"""
from datetime import datetime,timedelta
import re
from zoneinfo import ZoneInfo
from .contracts import ObservationError

ZONE=ZoneInfo('Asia/Shanghai')


def valid_schedule_times(times):
    """保留09:00，允许至多三个16:30以后的显式盘后窗口。"""
    return (type(times) is list and 1<=len(times)<=4 and times[0]=='09:00'
        and all(type(value) is str and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value)
            and (value=='09:00' or value>='16:30') for value in times)
        and times==sorted(set(times)))


def local_now(now):
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ObservationError('invalid_schedule_clock','观察调度需要带时区的时钟',422)
    return now.astimezone(ZONE)


def due_windows(now,schedule,completed=()):
    local=local_now(now);floor=schedule.get('start_date');windows=[]
    for offset in (1,0):
        day=(local-timedelta(days=offset)).date()
        if floor and day.isoformat()<floor:continue
        for value in schedule['times']:
            hour,minute=map(int,value.split(':'))
            when=datetime(day.year,day.month,day.day,hour,minute,tzinfo=ZONE)
            key=when.isoformat()
            if when<=local and key not in completed:windows.append((key,when))
    return windows


def window_as_of(key,now,schedule=None,models=None):
    """旧配置沿原日期口径；source-aware-v1取窗口时点已结束的沪深交易日。"""
    try:
        when=datetime.fromisoformat(key);local=local_now(now)
        times=schedule['times'] if schedule is not None else ['09:00']
        if (when.tzinfo is None or when.isoformat()!=key or when.utcoffset()!=timedelta(hours=8)
                or not valid_schedule_times(times) or when.strftime('%H:%M') not in times
                or (when.second,when.microsecond)!=(0,0)
                or when>local or when.date()<(local-timedelta(days=1)).date()):
            raise ValueError('window outside bounded schedule')
        if schedule is not None and schedule.get('date_policy')=='source-aware-v1' and models is not None:
            return closed_market_day(when,'cn',models)
        return (when-timedelta(days=1)).date().isoformat()
    except (ValueError,TypeError,OverflowError):
        raise ObservationError('invalid_schedule_window','观察计划窗口无效或尚未到期',422) from None


def closed_market_day(when,market,models,*,check=lambda:None):
    """收盘前回看上一日，再沿已准入官方日历排除周末与假期。"""
    from .calendars import last_open_day
    from .source_fetch import SourceFailure
    local=local_now(when);close=(15,0) if market=='cn' else (16,0)
    day=local.date() if (local.hour,local.minute)>=close else (local-timedelta(days=1)).date()
    calendar=models.get('calendars',{}).get(market,{})
    if calendar.get('kind')!='official-exchange-calendar/v1':
        raise SourceFailure('official_calendar_required')
    return last_open_day(calendar,day.isoformat(),check=check)


def source_as_of(source,as_of,config,when,*,check=lambda:None):
    """来源策略显式配置；披露截止不改变月季年报告期或股份变动日。"""
    if config.get('schedule',{}).get('date_policy')!='source-aware-v1':return as_of
    policy=source['date_policy']
    if policy=='calendar-day':return local_now(when).date().isoformat()
    if policy=='cn-prior-day':
        # 与WT数据owner的全天目标一致；显式历史as_of仍限定查询上限，不推进未来日。
        from .calendars import last_open_day
        upper=min(as_of,(local_now(when)-timedelta(days=1)).date().isoformat())
        return last_open_day(config['models']['calendars']['cn'],upper,check=check)
    return closed_market_day(when,'cn' if policy=='cn-closed-day' else 'hk',config['models'],check=check)
