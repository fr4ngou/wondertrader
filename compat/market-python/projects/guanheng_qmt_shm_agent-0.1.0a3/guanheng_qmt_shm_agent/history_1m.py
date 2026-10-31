# -*- coding: utf-8 -*-
"""Fixed single-symbol history adapter; Python 3.6 standard library.

No result wrapper, transport, SDK import, persistence or native cancellation code.
ContextInfo and its Frame/scalar methods belong to the trusted SDK boundary.
"""
import json
import math
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from .errors import GatewayError

OP='market.history_1m'
SCHEMA='qmt.history-1m.v1'
POLICY='qmt.history-read.v1'
FIELDS=('time','open','high','low','close','volume','amount')
SHANGHAI=timezone(timedelta(hours=8))
MESSAGES={
    'invalid_request':'历史读取参数不合格', 'owner_required':'历史读取需要原策略线程',
    'execution_timeout':'历史读取已超出同一执行截止，原生调用状态按原ID核查',
    'source_shape_invalid':'历史来源结构不合格', 'source_value_invalid':'历史来源数值或时间不合格',
    'history_window_limit':'历史窗口达到条数上限，请显式缩小窗口',
    'result_too_large':'历史结果超过受管字节容量，请显式缩小窗口',
    'qmt_call_failed':'原生历史读取失败'}

class HistoryError(GatewayError):
    def __init__(self,code):
        self.code=code
        GatewayError.__init__(self,code,MESSAGES[code])

def fail(code):raise HistoryError(code)

def _stamp(value):
    if type(value) is not str or len(value)!=14 or not re.match(r'^[0-9]{12}00$',value):fail('invalid_request')
    # 协议固定十四位整分钟；直接构造保留原生datetime类型及日历校验，
    # 避免strptime在受限终端隐式从全局导入磁盘标准库。
    try:return datetime(int(value[:4]),int(value[4:6]),int(value[6:8]),
        int(value[8:10]),int(value[10:12]),int(value[12:14]),tzinfo=SHANGHAI)
    except ValueError:fail('invalid_request')

def arguments(value,as_of_date,max_calendar_days=5,max_rows=2000):
    """公开JSON边界只接受四个精确内建值，永不调用Frame/item等SDK钩子。"""
    if type(value) is not dict or len(value)!=4 or set(value)!=set(('symbol','start_time','end_time','max_rows')):fail('invalid_request')
    if type(as_of_date) is not date:fail('invalid_request')
    symbol=value['symbol']
    if type(symbol) is not str or len(symbol)!=9 or not re.match(r'^[0-9]{6}\.(SH|SZ)$',symbol):fail('invalid_request')
    count=value['max_rows']
    if type(count) is not int or not 1<=count<=max_rows:fail('invalid_request')
    start,end=_stamp(value['start_time']),_stamp(value['end_time'])
    if start>end or start.date()<datetime(2021,11,1).date() or end.year>2099 or end.date()>=as_of_date or (end.date()-start.date()).days>=max_calendar_days:fail('invalid_request')
    return symbol,value['start_time'],value['end_time'],count,start,end

def split_window(start_time,end_time):
    """纯整分钟闭区间拆分；不重试、不取日历、不调用SDK。"""
    start,end=_stamp(start_time),_stamp(end_time)
    if start>=end:fail('history_window_limit')
    minutes=int((end-start).total_seconds()//60)
    mid=start+timedelta(minutes=minutes//2)
    return ((start_time,mid.strftime('%Y%m%d%H%M%S')),((mid+timedelta(minutes=1)).strftime('%Y%m%d%H%M%S'),end_time))

def _number(value):
    # .item只对SDK返回的NumPy标量开放；公开请求不走此路径。
    if type(value) not in (int,float):
        if not type(value).__module__.startswith('numpy'):fail('source_value_invalid')
        item=getattr(value,'item',None)
        if not callable(item):fail('source_value_invalid')
        value=item()
    if type(value) is int:
        if value.bit_length()>54 or not -(2**53)<=value<=2**53:fail('source_value_invalid')
    elif type(value) is float:
        if not math.isfinite(value):fail('source_value_invalid')
    else:fail('source_value_invalid')
    return value


def validated_row(row,start_ms,end_ms,previous,check=None):
    """共用七字段纯值校验；可信标量转换始终由调用方原线程执行。"""
    if type(row) not in (tuple,list) or len(row)!=7:fail('source_shape_invalid')
    selected=[]
    for value in row:
        if check is not None:check()
        selected.append(_number(value))
        if check is not None:check()
    stamp,opening,high,low,close,volume,amount=selected
    if not float(stamp).is_integer() or stamp%60000 or not start_ms<=stamp<=end_ms:fail('source_value_invalid')
    if previous is not None and stamp<=previous:fail('source_value_invalid')
    if min(opening,high,low,close)<=0 or volume<0 or amount<0 or high<max(opening,low,close) or low>min(opening,high,close):fail('source_value_invalid')
    return tuple(selected)

class History1mAdapter(object):
    """构造线程独占；日期provider和额度来自部署owner，不能由请求覆盖。

    SDK调用不可抢占。deadline覆盖准入、native、遍历与编码；晚回只形成失败终态。
    """
    def __init__(self,context,limits,max_result_bytes,clock=time.monotonic,as_of_date_provider=None):
        from .read_capabilities import shanghai_date, _history_limits
        limits=_history_limits(limits,max_result_bytes)
        self.context,self.max_data_bytes,self.max_result_bytes=context,limits['max_data_bytes'],max_result_bytes
        self.max_calendar_days,self.max_rows=limits['max_calendar_days'],limits['max_rows']
        self.as_of_date_provider=shanghai_date if as_of_date_provider is None else as_of_date_provider
        if not callable(clock) or not callable(self.as_of_date_provider):raise ValueError('trusted clock required')
        self.clock,self.owner=clock,threading.get_ident()

    def _check(self,deadline):
        if threading.get_ident()!=self.owner:fail('owner_required')
        if type(deadline) not in (int,float) or not math.isfinite(deadline):fail('invalid_request')
        if self.clock()>=deadline:fail('execution_timeout')

    def _encode(self,value,limit,deadline):
        """只接收已限定的DTO，逐片UTF8计字节；无整体无限字符串中间副本。"""
        encoder=json.JSONEncoder(ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        pieces=[];size=0
        for piece in encoder.iterencode(value):
            self._check(deadline)
            data=piece.encode('utf-8');size+=len(data)
            if size>limit:fail('result_too_large')
            pieces.append(data)
        self._check(deadline)
        return b''.join(pieces)

    def _read(self,args,deadline):
        symbol,start_text,end_text,count,start,end=args
        self._check(deadline)
        try:
            values=self.context.get_market_data_ex(fields=list(FIELDS),stock_code=[symbol],period='1m',
                start_time=start_text,end_time=end_text,count=count,dividend_type='none',fill_data=False,subscribe=False)
        except Exception:fail('qmt_call_failed')
        self._check(deadline)
        if type(values) is not dict or len(values)!=1 or symbol not in values:fail('source_shape_invalid')
        frame=values[symbol]
        try:
            shape=frame.shape
            if type(shape) not in (tuple,list) or len(shape)!=2 or any(type(n) is not int or n<0 for n in shape):fail('source_shape_invalid')
            rows,cols=shape
            if rows>=count:fail('history_window_limit')
            if cols not in ((0,7) if rows==0 else (7,)):fail('source_shape_invalid')
            columns=frame.columns
            if len(columns)!=cols:fail('source_shape_invalid')
            iterator=iter(columns);names=[]
            for index in range(cols+1):
                self._check(deadline)
                try:name=next(iterator)
                except StopIteration:break
                if index==cols or type(name) is not str or len(name)>16 or name not in FIELDS or name in names:fail('source_shape_invalid')
                names.append(name)
            if len(names)!=cols or (cols and set(names)!=set(FIELDS)):fail('source_shape_invalid')
            positions=[names.index(field) for field in FIELDS] if cols else []
            iterator=iter(frame.itertuples(index=False,name=None))
            output=[];previous=None
            for index in range(rows+1):
                self._check(deadline)
                try:row=next(iterator)
                except StopIteration:
                    if index!=rows:fail('source_shape_invalid')
                    break
                self._check(deadline)
                if index==rows or type(row) not in (tuple,list) or len(row)!=cols:fail('source_shape_invalid')
                selected=validated_row(tuple(row[position] for position in positions),
                    start.timestamp()*1000,end.timestamp()*1000,previous,lambda:self._check(deadline))
                previous=selected[0];output.append(dict(zip(FIELDS,selected)))
            self._check(deadline)
        except HistoryError:raise
        except Exception:fail('source_shape_invalid')
        return {'schema_version':SCHEMA,'symbol':symbol,'period':'1m','start_time':start_text,'end_time':end_text,
            'max_rows':count,'rows':output,'coverage':'unknown','source_options':{'dividend_type':'none','fill_data':False,'subscribe':False}}

    def execute(self,value,deadline):
        """返回独立普通DTO；仅供同owner的原结果finalizer立即封装。"""
        self._check(deadline);args=arguments(value,self.as_of_date_provider(),self.max_calendar_days,self.max_rows)
        data=self._read(args,deadline);self._encode(data,self.max_data_bytes,deadline)
        return data

