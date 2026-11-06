"""MSF离线来源夹具；保留真实Retained客户端和公开源解析器，不连接QMT/网络。"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import time
from uuid import uuid4
from xml.sax.saxutils import escape
import zipfile

ROOT=Path(__file__).resolve().parents[3]
for relative in ('apps/guanheng','connectors/qmt_shm/host','connectors/qmt_shm/agent'):
    path=str(ROOT/relative)
    if path not in sys.path:sys.path.insert(0,path)

from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from guanheng_app.observation.storage import ContentStore
from guanheng_qmt_shm import bound
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.protocol import canonical,decode
from guanheng_qmt_shm_agent.read_capabilities import build_read_profile
from integrations.guanheng.source_history_transport import BoundHistorySource,SourcePending
from integrations.guanheng.market_generation import encode

DAYS=['2026-11-04','2026-11-05']


def xlsx_table(rows,*,mode='inline',extra_members=()):
    """标准库生成合法最小OOXML；输入数值写numeric，其余用inline或shared字符串。"""
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    strings=[];xml_rows=[]
    for index,row in enumerate(rows,1):
        cells=[]
        for column,value in enumerate(row):
            reference=f'{chr(65+column)}{index}'
            if type(value) in (int,float):
                cell=f'<c r="{reference}"><v>{value}</v></c>'
            elif mode=='shared':
                strings.append(str(value));cell=f'<c r="{reference}" t="s"><v>{len(strings)-1}</v></c>'
            else:cell=f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            cells.append(cell)
        xml_rows.append(f'<row r="{index}">'+''.join(cells)+'</row>')
    parts={
        '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml':f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="基金规模" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml':f'<worksheet xmlns="{ns}"><sheetData>'+''.join(xml_rows)+'</sheetData></worksheet>',
    }
    if strings:
        parts['xl/sharedStrings.xml']=f'<sst xmlns="{ns}">'+''.join('<si><t>'+escape(s)+'</t></si>' for s in strings)+'</sst>'
        parts['[Content_Types].xml']=parts['[Content_Types].xml'].replace('</Types>','<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>')
        parts['xl/_rels/workbook.xml.rels']=parts['xl/_rels/workbook.xml.rels'].replace('</Relationships>','<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as package:
        for name,body in parts.items():package.writestr(name,body)
        for name,body in extra_members:package.writestr(name,body)
    return output.getvalue()


def szse_xlsx(day,*,mode='inline',rows=None,header=None,extra_members=()):
    return xlsx_table([header or ['日期','基金代码','基金简称','基金规模(份)']]+(
        rows if rows is not None else [[day,'159352','合成ETF甲',32469101746],[day,'159780','合成ETF乙','4,037,248,583']]),
        mode=mode,extra_members=extra_members)


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    body=encode(value);path.write_bytes(body)
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(body).hexdigest()}


def plan(*targets,required=True):
    return dict(schema='guanheng.market-supplement-plan.v1',policy='qmt_preferred',
                targets=[dict(metric=metric,symbol=symbol,**{'from':DAYS[0]}) for metric,symbol in targets],
                external_fallback=['SSE','SZSE','Eastmoney'],required=required)


def query(snapshot='1'*64,metric='etf_total_shares',symbols=None,**updates):
    value=dict(snapshot_id=snapshot,metric=metric,symbols=symbols or ['SSE.510300'],
               **{'from':DAYS[0],'to':DAYS[-1]},offset=0,limit=2000)
    value.update(updates);return value


class FrozenFetch:
    """固定公开HTTP形状和人工金额；HTTP预算与原件消费仍用生产预算类。"""
    def __init__(self,*,bad_day=None,deadline=None):
        self.budget=CollectionBudget(deadline or time.monotonic()+30,max_requests=100,
                                     max_bytes=4*1024*1024,response_bytes=1024*1024)
        self.bad_day=bad_day;self.calls=[];self.closed=False
    def get(self,url,params=None,referer=None):
        self.budget.request();self.calls.append((url,deepcopy(params)))
        if params.get('CATALOGID')=='scsj_fund_jjgm':
            assert url=='http://www.szse.cn/api/report/ShowReport' and params['SHOWTYPE']=='xlsx'
            day=params['txtStart'];actual='2026-11-03' if day==self.bad_day else day
            body=szse_xlsx(actual);self.budget.consume(len(body));return body
        elif params.get('sqlId')=='COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L':
            day=params['STAT_DATE'];actual='2026-11-03' if day==self.bad_day else day
            value=dict(actionErrors=[],fieldErrors={},pageHelp=dict(total=1,pageCount=1,pageNo=1),
                       result=[dict(STAT_DATE=actual,SEC_CODE='510300',TOT_VOL='175000.125')])
        elif params.get('sqlId')=='COMMON_SSE_SJ_GPSJ_CJGK_MRGK_C':
            day=params['SEARCH_DATE']
            value=dict(result=[dict(TRADE_DATE=day.replace('-',''),PRODUCT_CODE='17',TRADE_AMT='9812.82')])
        elif params.get('CATALOGID')=='1803':
            value=[dict(metadata=dict(tabkey='tab1',subname=params['txtQueryDate']),
                        data=[dict(zbmc='股票成交金额（亿元）',brsz='11,395.92')])]
        elif params.get('reportName')=='RPTA_WEB_MARGIN_DAILYTRADE':
            day=params['filter'].split("'")[1]
            value=dict(success=True,result=dict(count=1,pages=1,data=[
                dict(STATISTICS_DATE=day+' 00:00:00',FIN_BALANCE='123.456789',RZYE='999999999')]))
        else:raise AssertionError('unexpected public source request')
        body=encode(value);self.budget.consume(len(body));return body
    def close(self):self.closed=True


class QmtTransport:
    """签名metadata/原slot/票据/lookup/consumed均走原客户端；SDK仅为确定返回的替身。"""
    def __init__(self,*,lose_first=False,binding_pending=False,max_rows=2000,amounts=None):
        self.original=BoundHistorySource(dict(base_url='http://127.0.0.1:1',key_id='msf-fixture',
            secret_env='MSF_SYNTHETIC_SECRET',timeout=1),environ={'MSF_SYNTHETIC_SECRET':'synthetic-msf-only-'*4})
        descriptors={'market.market_data':dict(policy_id='qmt.daily-read.v1',policy_version='1.0',
            execution_timeout_ms=1000,limits=dict(schema_version='qmt.daily-history.v1',
            max_calendar_days=3660,max_rows=max_rows,max_data_bytes=32768))}
        control=dict(schema_version='1.0',max_pending_calls=4,max_call_bytes=8192,max_reply_bytes=131072,
                     max_retained_bytes=1048576,max_cycle_messages=8,max_cycle_bytes=196608,poll_seconds=.005,max_call_seconds=10.)
        profile=build_read_profile(sorted(descriptors),1000,control,descriptors,max_result_bytes=65536,
                                   read_retention=dict(schema='qmt.read-retention.v1',max_lifetime_ms=300000))
        raw=canonical(profile)
        binding=host_binding(route=dict(route_id='msf',executor_id='synthetic-sdk',route_epoch=1),
            generation=uuid4().hex,host_instance_id=uuid4().hex,journal_generation=None,
            capability_sha256=bound.digest(raw),observation_identity=None)
        self.metadata=dict(schema_version=bound.SCHEMA,binding=binding,binding_sha256=bound.digest(canonical(binding)),
            read_profile_body_b64=bound.b64(raw),read_profile_body_sha256=bound.digest(raw),order_ready=False,
            limits=dict(max_request_bytes=8192,max_result_bytes=65536,max_http_request_bytes=65536,max_http_response_bytes=131072))
        self.lose_first=lose_first;self.binding_pending=binding_pending
        self.amounts=amounts or {'000001.SH':100.25,'399106.SZ':200.75}
        self.calls=[];self.responses={};self.sdk_calls=[];self.closed=False
    @contextmanager
    def rpc_budget(self,seconds):yield
    def plan(self,*args):return self.original.plan(*args)
    def exchange(self,method,path,body,deadline):
        self.calls.append((method,path))
        if path.endswith('read-binding'):
            return (503,{}) if self.binding_pending else (200,self.metadata)
        if path.endswith('read-retention-status'):return 200,dict(retained=0,capacity=32)
        if path.endswith('/consumed'):
            rid=path.split('/')[-2]
            return 200,dict(schema='qmt.read-consumed-result.v1',request_id=rid,consumed=True)
        if path.endswith('/lookup'):
            return 200,self.responses[path.split('/')[-2]]
        if path=='/internal/v1/bound-operations/market.market_data':
            envelope=decode(body);raw=bound.unb64(envelope['request_body_b64'],8192);request=decode(raw)
            self.sdk_calls.append(deepcopy(request));symbol=request['arguments']['symbol']
            amount=self.amounts[symbol]
            dates=[d.replace('-','') for d in DAYS if request['arguments']['start_date']<=d.replace('-','')<=request['arguments']['end_date']]
            dates=dates[-request['arguments']['max_rows']:]
            data={symbol:{day:dict(open=1.,high=1.,low=1.,close=1.,volume=1.,amount=amount) for day in dates}}
            reply=dict(request_id=request['request_id'],operation_id=request['operation_id'],ok=True,error_code=None,data=data)
            reply['result_sha256']=bound.digest(canonical(reply));reply_raw=canonical(reply)
            response=dict(schema_version=bound.SCHEMA,request_id=request['request_id'],operation_id=request['operation_id'],
                request_sha256=bound.digest(raw),request_body_sha256=bound.digest(raw),binding_status='recorded',
                admitted_binding=self.metadata['binding'],dispatch_binding=self.metadata['binding'],result_binding=self.metadata['binding'],
                state='terminal',result_body_b64=bound.b64(reply_raw),result_body_sha256=bound.digest(reply_raw))
            self.responses[request['request_id']]=response
            if self.lose_first:
                self.lose_first=False;raise SourcePending('synthetic reply lost after SDK call')
            return 200,response
        raise AssertionError('unexpected retained source request '+path)
    def close(self):self.closed=True;self.original.close()


def capture_metadata():
    """完整且自洽的原capture anchor；快照装配继续使用生产来源身份校验。"""
    from guanheng_qmt_shm.read_retention_client import RetainedReadClient
    transport=QmtTransport()
    try:
        metadata=RetainedReadClient(transport).metadata(deadline=time.monotonic()+5)
    finally:
        transport.close()
    metadata['limits']=bound.limits(max_frame=65536,max_result_bytes=65536,native_body_limit=8192)
    return metadata
