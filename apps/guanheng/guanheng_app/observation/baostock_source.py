"""有界股票PB协议客户端；合同来自固定baostock0.9.4，不修改供应商全局状态。

只承担本来源登录、股表、交易日历、全市场日线及注销。消息头/压缩类型
沿锁定SDK常量，完整wire先归档，字符串JSON直接解析，避免SDK.split丢失空白。
"""
from datetime import datetime,timezone
import importlib.metadata
import re
import socket
import zlib
from .provider_tables import StringTable,parse_json
from .source_fetch import SourceFailure

TRAILER=b'<![CDATA[]]>\n'


class BaostockClient:
    def __init__(self,fetch,timeout=20,*,connector=None):
        fetch.budget.remaining()
        if type(timeout) not in (int,float) or not 0<timeout<=60:raise SourceFailure('pb_invalid_timeout')
        if importlib.metadata.version('baostock')!='0.9.4':raise SourceFailure('pb_sdk_version')
        from baostock.common import contants
        self.constants=contants;self.fetch=fetch;self.budget=fetch.budget;self.timeout=timeout
        self.connector=connector or socket.create_connection;self.socket=None;self.logged_in=False

    def _seconds(self):return min(self.timeout,self.budget.remaining())

    def __enter__(self):
        try:
            self.socket=self.connector((self.constants.BAOSTOCK_SERVER_IP,self.constants.BAOSTOCK_SERVER_PORT),timeout=self._seconds())
            self._message('00','login',['anonymous','123456','0']);self.logged_in=True
            return self
        except (OSError,TimeoutError):
            self.close();self.budget.remaining();raise SourceFailure('pb_transport_unavailable') from None
        except BaseException:
            self.close();raise

    def __exit__(self,kind,error,traceback):
        try:
            if kind is None and self.logged_in:
                self._message('02','logout',['anonymous',datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')])
        finally:self.close()

    def close(self):
        stream=self.socket
        if stream is not None:
            stream.close();self.socket=None

    def _message(self,request_type,method,arguments):
        remaining=self.budget.request_deadline(self.timeout)
        self.budget.request('sdk');split=self.constants.MESSAGE_SPLIT
        body=split.join([method,*arguments]);head=split.join([self.constants.BAOSTOCK_CLIENT_VERSION,request_type,str(len(body)).zfill(10)])
        message=(head+body).encode('utf8');wire=message+split.encode()+str(zlib.crc32(message)).encode()+b'\n'
        if len(wire)>65536:raise SourceFailure('pb_request_bytes')
        try:
            self.socket.settimeout(remaining());self.socket.sendall(wire)
            received=bytearray()
            while not received.endswith(TRAILER):
                self.socket.settimeout(remaining())
                chunk=self.socket.recv(min(65536,self.budget.response_bytes-len(received)+1))
                if not chunk:raise SourceFailure('pb_incomplete_response')
                self.budget.consume(len(chunk))
                if len(received)+len(chunk)>self.budget.response_bytes:raise SourceFailure('response_budget_exceeded')
                received.extend(chunk)
        except (OSError,TimeoutError):
            remaining();raise SourceFailure('pb_transport_unavailable') from None
        remaining()
        raw=bytes(received);identity=self.fetch.objects.put(raw)
        self.fetch.records.append(dict(sha256=identity,source_host='baostock',kind='provider_wire',status=200,
            retrieved_at=datetime.now(timezone.utc).isoformat(),protocol_request=request_type))
        try:
            header=raw[:21].decode('ascii');version,response_type,length=header.split(split)
            if re.fullmatch(r'\d{2}\.\d\.\d{2}',version) is None or response_type!=str(int(request_type)+1).zfill(2) or len(length)!=10 or not length.isdigit():
                raise ValueError('header')
            self.fetch.records[-1].update(provider_version=version,client_version=self.constants.BAOSTOCK_CLIENT_VERSION)
            count=int(length);payload=raw[21:-len(TRAILER)]
            if count>len(payload):raise ValueError('length')
            if response_type in self.constants.COMPRESSED_MESSAGE_TYPE_TUPLE:
                decoder=zlib.decompressobj();decoded=bytearray()
                # max_length在分配前限制解压输出，额外一字节检测越界。
                for offset in range(0,count,65536):
                    pending=payload[offset:min(count,offset+65536)]
                    while pending:
                        remaining();chunk=decoder.decompress(pending,min(65536,self.budget.response_bytes-len(decoded)+1))
                        if len(decoded)+len(chunk)>self.budget.response_bytes:raise SourceFailure('response_decode_budget_exceeded')
                        self.budget.expand(len(chunk));decoded.extend(chunk);pending=decoder.unconsumed_tail
                if not decoder.eof or decoder.unused_data:raise ValueError('compressed body')
                payload=bytes(decoded)
            else:
                if len(payload)>self.budget.response_bytes:raise SourceFailure('response_decode_budget_exceeded')
                self.budget.expand(len(payload))
            parts=payload.decode('utf8').rstrip('\n').split(split)
        except (ValueError,UnicodeError,zlib.error):raise SourceFailure('pb_protocol_schema') from None
        remaining()
        if len(parts)<4 or parts[0]!='0' or parts[2]!=method or parts[3]!='anonymous':
            raise SourceFailure('pb_provider_response')
        return parts

    def table(self,kind,start=None,end=None):
        settings={'stock_basic':('45','query_stock_basic',('code','type','ipoDate','outDate')),
            'calendar':('33','query_trade_dates',('calendar_date','is_trading_day')),
            'stock_daily_batch':(self.constants.MESSAGE_TYPE_GETKDaily_D_AStock_REQUEST,'query_daily_history_k_AStock',('date','code','pbMRQ','tradestatus'))}
        request_type,method,required=settings[kind];table=None;page=1;per_page=str(self.constants.BAOSTOCK_PER_PAGE_COUNT)
        while True:
            args=['anonymous',start] if kind=='stock_daily_batch' else ['anonymous',str(page),per_page,*(['',''] if kind=='stock_basic' else [start,end])]
            parts=self._message(request_type,method,args)
            try:
                data_at,fields_at=(4,5) if kind=='stock_daily_batch' else (6,9)
                # 供应商CSV列头带协议排版换行；仅规范列名，JSON行内字符串原样保留。
                fields=[field.strip() for field in parts[fields_at].split(',')];raw=parse_json(parts[data_at])
                if type(raw) is not dict or set(raw)!={'record'} or type(raw['record']) is not list:raise ValueError('table')
                if table is None:table=StringTable(fields,required,limit=self.budget.response_bytes,check=self.budget.remaining)
                elif fields!=table.fields:raise ValueError('fields changed')
                for row in raw['record']:table.append(row)
                if kind!='stock_daily_batch' and (parts[4]!=str(page) or parts[5]!=per_page):raise ValueError('page identity')
                if kind=='calendar' and parts[7:9]!=[start,end]:raise ValueError('calendar range')
                if kind=='stock_basic' and parts[7:9]!=['','']:raise ValueError('stock range')
                if kind=='stock_daily_batch' or len(raw['record'])<int(per_page):break
                if len(raw['record'])!=int(per_page):raise ValueError('page size')
                page+=1
            except (ValueError,IndexError,TypeError,RecursionError):raise SourceFailure('pb_protocol_table') from None
        identity=self.fetch.objects.put(table.body())
        self.fetch.records.append(dict(sha256=identity,source_host='baostock',kind=kind if kind!='calendar' else 'provider_protocol',
            status=200,retrieved_at=datetime.now(timezone.utc).isoformat()))
        return table.fields,table.rows
