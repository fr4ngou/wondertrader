"""有限异步缓存观测的排程；通信事实仍保存原bound收据。"""
from __future__ import annotations

import math

from .source_history_transport import SourcePending,require


class FollowUpExhausted(ValueError):
    """明确后续观测额度已耗尽；不会授第二个下载。"""


def configuration(value):
    require(type(value)is dict and set(value)=={'enabled','max_attempts','interval_seconds','total_seconds',
        'rpc_timeout_seconds','journal_records','journal_bytes'}and value['enabled']is True)
    for name,low,high in [('max_attempts',1,16),('journal_records',1,1000000),('journal_bytes',1,1099511627776)]:
        require(type(value[name])is int and low<=value[name]<=high)
    for name,low,high in [('interval_seconds',.1,3600),('total_seconds',1,86400),('rpc_timeout_seconds',.1,30)]:
        require(type(value[name])in(int,float)and math.isfinite(value[name])and low<=value[name]<=high)
    require(value['interval_seconds']<=value['total_seconds'])
    return value


def capacity(settings,windows,pages,limits):
    records=windows*(1+(2+settings['max_attempts'])*pages)
    size=records*(limits['max_request_bytes']+limits['max_result_bytes']+16384)
    if settings['journal_records']<records or settings['journal_bytes']<size:
        raise FollowUpExhausted('follow-up Host Journal capacity declaration is insufficient')


def reading(uptime,wall):
    require(type(uptime)in(int,float)and math.isfinite(uptime)and uptime>=0
        and type(wall)in(int,float)and math.isfinite(wall)and wall>=0)
    return int(uptime*1000),int((wall-uptime)*1000)


def initial(settings,uptime,wall):
    now,anchor=reading(uptime,wall)
    return dict(start_ms=now,deadline_ms=now+int(settings['total_seconds']*1000),last_ms=now,
        next_ms=now+int(settings['interval_seconds']*1000),anchor_ms=anchor,runs=0,reads=[],stopped_reason=None)


def admit(state,settings,uptime,wall):
    """调用者在任何来源交换前持久化本次消费；重启继续同一截止。"""
    now,anchor=reading(uptime,wall)
    require(type(state)is dict and set(state)=={'start_ms','deadline_ms','last_ms','next_ms','anchor_ms','runs','reads','stopped_reason'})
    require(all(type(state[k])is int for k in('start_ms','deadline_ms','last_ms','next_ms','anchor_ms','runs'))
        and state['deadline_ms']==state['start_ms']+int(settings['total_seconds']*1000)
        and 0<=state['runs']<=settings['max_attempts']and type(state['reads'])is list
        and len(state['reads'])<=state['runs']and state['start_ms']<=state['last_ms']
        and state['next_ms']==state['last_ms']+int(settings['interval_seconds']*1000))
    if state['stopped_reason']is not None:
        require(type(state['stopped_reason'])is str and 1<=len(state['stopped_reason'])<=256)
        raise FollowUpExhausted(state['stopped_reason'])
    if now<state['last_ms']or abs(anchor-state['anchor_ms'])>5000:
        raise FollowUpExhausted('follow-up clock continuity is unavailable')
    if now>=state['deadline_ms']:raise FollowUpExhausted('follow-up original total deadline exhausted')
    if state['runs']>=settings['max_attempts']:raise FollowUpExhausted('follow-up attempt budget exhausted')
    if now<state['next_ms']:raise SourcePending('follow-up minimum interval has not elapsed')
    state.update(last_ms=now,next_ms=now+int(settings['interval_seconds']*1000),runs=state['runs']+1)
