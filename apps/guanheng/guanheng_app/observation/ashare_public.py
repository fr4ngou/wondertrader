"""公开日终来源、定日原件归档与原refresh之间的适配。"""
from datetime import date, datetime, time, timedelta, timezone

from .ashare_source import _clock, _decode, _need, _pages, bse_numbers, normalize, validate_daily, FIELDS
from .contracts import ObservationError
from .baostock_source import BaostockClient
from .bse_universe import LIST_API, LIST_PAGE, MAPPING, _Mapping, _day
from .executive_source import COMPANY_COLUMNS, COMPANY_REPORT
from .ashare_pool import current_pool
from .provider_reports import report_pages
from .source_fetch import BoundedContentStore,CollectionBudget,Fetcher,SourceFailure
from .storage import digest, encode
from .calendars import closed_day_cutoff
from .provider_tables import load_table

ZONE=timezone(timedelta(hours=8))
QUOTE_API='https://www.bse.cn/nqhqController/nqhq_en.do'
QUOTE_PAGE='https://www.bse.cn/nq/quotation.html'


class ObjectCapture:
    """同一对象库中的原件引用；文件包和网络捕获共用normalize。"""
    def __init__(self,fetch):
        self.fetch=fetch
        self.input_records=[]

    def read(self,descriptor,kind,*,timed=True):
        expected={'path','sha256','received_at'} if timed else {'path','sha256'}
        _need(type(descriptor) is dict and set(descriptor)==expected)
        self.fetch.budget.remaining()
        body=self.fetch.objects.get(descriptor['sha256'])
        _need(len(body)<=self.fetch.budget.response_bytes,'ashare_source_capacity')
        record=dict(kind=kind,sha256=descriptor['sha256'],media_type='application/json')
        if timed:
            _clock(descriptor['received_at'])
            record['retrieved_at']=descriptor['received_at']
        self.input_records.append(record)
        if not any(row.get('kind')==kind and row.get('sha256')==record['sha256'] for row in self.fetch.records):
            self.fetch.records.append(record)
        value=_decode(body)
        self.fetch.budget.remaining()
        return value


class Archive:
    """原runs记录尝试和成功原件锚；采集lease由原refresh或服务调用者持有。"""
    def __init__(self,reader,fetch,source,*,retry_seconds=60,max_attempts=8,now=None,admitted_records=(),
                 normalizer=None,published_inputs=True,retry_window_seconds=None,baostock_daily_timeout_seconds=None):
        self.normalizer=normalize if normalizer is None else normalizer  # 原默认指标准入或显式数据事实回调；在本采集线程执行。
        _need(callable(self.normalizer) and type(published_inputs) is bool)
        self.published_inputs=published_inputs  # 原观察角色可复用已发布PB原件；数据角色只读自己的原件/回执域。
        self.reader,self.fetch,self.source=reader,fetch,source
        self.now=now or datetime.now(timezone.utc)
        self.retry_seconds,self.max_attempts=retry_seconds,max_attempts
        self.retry_window_seconds=retry_window_seconds  # 常驻数据owner的有限重试窗口；None保持既有单批次数规则。
        self.policy=digest(encode(source))
        self.admitted_records=admitted_records  # 同批先前成功Baostock来源的原件记录；保持原SHA及真实抓取时间。
        self.baostock_daily_timeout_seconds=baostock_daily_timeout_seconds  # WT 日线单请求预算，None 沿 fetch 超时。

    def stock_input(self,kind,day):
        """同一Baostock事实只采一次；优先本批成功原件，再读已发布PB原件。

        证券表须不早于目标日实际取得，并按上市/退市区间取day的成员；
        日线须每行属于day。原件先核SHA和字符串
        合同。没有合格原件时调用者继续原网络入口，不把旧日数据改日期。
        """
        records=list(self.admitted_records)
        if self.published_inputs:
            _version,manifest=self.reader.snapshot()
            item=manifest['datasets'].get('pb_shsz_daily',{})
            # freshness允许为空；首次采集尚无前代来源回执，仍可消费本批原件。
            for receipt in (item.get('definition',{}).get('freshness') or {}).get('source_results',[]):
                if receipt.get('status')=='success' and receipt.get('source_manifest'):
                    captured=_decode(self.fetch.objects.get(receipt['source_manifest']))
                    _need(type(captured) is list,'ashare_source_schema')
                    records.extend(captured)
        required=('code','type','ipoDate','outDate') if kind=='stock_basic' else tuple(FIELDS)
        for record in records:
            self.fetch.budget.remaining()
            if (record.get('kind')!=kind or record.get('source_host')!='baostock'
                    or not isinstance(record.get('retrieved_at'),str)):continue
            received=_clock(record['retrieved_at'])
            if kind=='stock_basic' and received.astimezone(ZONE).date().isoformat()<day:continue
            table=load_table(self.fetch.objects.get(record['sha256']),required,check=self.fetch.budget.remaining)
            value=dict(fields=table.fields,rows=table.rows)
            if kind=='stock_daily_batch':
                position=table.fields.index('date')
                if not table.rows or any(row[position]!=day for row in table.rows):continue
                validate_daily(value,day,self.fetch.budget.remaining)
            if not any(row.get('kind')==kind and row.get('sha256')==record['sha256'] for row in self.fetch.records):
                self.fetch.records.append(dict(record))
            return value
        return None

    def receipts(self,operation,day,**filters):
        return self.reader.repository.source_receipts(operation,self.source['id'],day,
            deadline=self.fetch.budget.deadline,cancelled=self.fetch.budget.cancelled,
            policy=self.policy,**filters)

    def record(self,operation,day,status,**values):
        stamp=datetime.now(timezone.utc).isoformat()
        row=dict(operation=operation,source_id=self.source['id'],date=day,status=status,
            policy_sha256=self.policy,started_at=stamp,completed_at=stamp,
            execution_mode='source_capture',**values)
        self.reader.repository.record_run(row,deadline=self.fetch.budget.deadline,
            cancelled=self.fetch.budget.cancelled)
        return row

    def attempt(self,operation,day):
        attempt_date=self.now.astimezone(ZONE).date().isoformat()
        attempts=self.receipts(operation,day,status='attempted',attempt_date=attempt_date)
        if self.retry_window_seconds is not None:
            _need(type(self.retry_window_seconds)in(int,float)and 1<=self.retry_window_seconds<=86400,
                  'ashare_capture_retry_window')
            # 原回执全部保留；窗口外失败不永久耗尽整日采集资格，仍受同一批次D和请求/字节预算约束。
            attempts=[row for row in attempts if 0<=(self.now-_clock(row['started_at'])).total_seconds()<self.retry_window_seconds]
        _need(len(attempts)<self.max_attempts,'ashare_capture_retries_exhausted')
        if attempts:
            elapsed=(self.now-_clock(attempts[0]['started_at'])).total_seconds()
            _need(elapsed>=self.retry_seconds,'ashare_capture_retry_pending')
        self.record(operation,day,'attempted',attempt_date=attempt_date)

    def restore_records(self,receipt):
        records=_decode(self.fetch.objects.get(receipt['source_manifest']))
        _need(type(records) is list and len(records)<=256)
        known={(r.get('kind'),r.get('sha256')) for r in self.fetch.records}
        for row in records:
            _need(type(row) is dict and 'kind' in row and 'sha256' in row)
            key=(row['kind'],row['sha256'])
            if key not in known:self.fetch.records.append(row);known.add(key)

    def describe(self,body,received=None):
        identity=self.fetch.objects.put(body)
        result=dict(path=identity+'.json',sha256=identity)
        if received:
            result['received_at']=received
        return result

    def closed_day(self,as_of):
        end=date.fromisoformat(as_of)
        local=self.now.astimezone(ZONE)
        cutoff=closed_day_cutoff(self.now)
        _need(end<=local.date(),'ashare_source_date')
        rows=self.receipts('ashare_calendar',as_of,status='success')
        success=rows[0] if rows else None
        if success:
            table=_decode(self.fetch.objects.get(success['calendar_sha256']))
            self.restore_records(success)
        else:
            self.attempt('ashare_calendar',as_of)
            start=(end-timedelta(days=45)).isoformat()
            with BaostockClient(self.fetch,self.fetch.timeout) as client:
                fields,values=client.table('calendar',start,as_of)
            table=dict(fields=fields,rows=values)
        fields,values=table['fields'],table['rows']
        _need(len(set(fields))==len(fields) and {'calendar_date','is_trading_day'}<=set(fields))
        expected=[(end-timedelta(days=n)).isoformat() for n in reversed(range(46))]
        days=[];opened=[]
        for values_row in values:
            self.fetch.budget.remaining()
            _need(type(values_row) is list and len(values_row)==len(fields))
            row=dict(zip(fields,values_row));day=row['calendar_date']
            _need(type(day) is str and date.fromisoformat(day).isoformat()==day
                and row['is_trading_day'] in ('0','1'))
            days.append(day)
            closed=day<=cutoff
            if row['is_trading_day']=='1' and closed:opened.append(day)
        _need(days==expected and bool(opened),'ashare_calendar_incomplete')
        if not success:
            identity=self.fetch.objects.put(encode(table))
            records=self.fetch.objects.put(encode(self.fetch.records))
            self.record('ashare_calendar',as_of,'success',calendar_sha256=identity,source_manifest=records)
        return opened[-1]

    def pages(self,day,kind):
        descriptors=[];count=None;pages=1
        for number in range(100):
            if number>=pages:break
            if kind=='quote':
                body=self.fetch.post_readonly(QUOTE_API,dict(page=str(number),type_en='["B"]',
                    sortfield='hqcjsl',sorttype='desc',xxfcbj_en='[2]',zqdm=''),
                    referer=QUOTE_PAGE,session_handoff=True)
            else:
                body=self.fetch.post_readonly(LIST_API,dict(page=str(number),typejb='T',
                    **{'xxfcbj[]':'2'},xxzqdm='',sortfield='xxzqdm',sorttype='asc'),
                    referer=LIST_PAGE,session_handoff=True)
            value=_decode(body)
            _need(type(value) is list and len(value)==1 and type(value[0]) is dict)
            value=value[0]
            if count is None:
                count=value['totalElements'];pages=value['totalPages']
                _need(type(count) is int and 1<=count<=2000 and type(pages) is int
                    and pages==(count+19)//20)
            _need(value['number']==number and value['totalElements']==count
                and value['totalPages']==pages and type(value['content']) is list)
            for row in value['content']:
                _need(str(row['hqjsrq' if kind=='quote' else 'xxjsrq'])==day.replace('-',''),
                    'ashare_current_feed_has_different_date')
            descriptors.append(self.describe(body,self.fetch.records[-1]['retrieved_at']))
        return descriptors

    def part(self,day,name,build):
        records=self.receipts('ashare_part',day,status='success',part=name)
        if records:
            self.restore_records(records[0])
            return _decode(self.fetch.objects.get(records[0]['part_sha256']))
        value=build()
        identity=self.fetch.objects.put(encode(value))
        self.fetch.records.append(dict(kind='ashare_'+name,sha256=identity,media_type='application/json'))
        source_manifest=self.fetch.objects.put(encode(self.fetch.records))
        self.record('ashare_part',day,'success',part=name,part_sha256=identity,source_manifest=source_manifest)
        return value

    def bse_part(self,day):
        quotes=self.pages(day,'quote')
        static=self.pages(day,'security')
        capture=ObjectCapture(self.fetch)
        quoted=_pages(capture,quotes,'bse_quote_original','hqzqdm',day)
        basics=_pages(capture,static,'bse_security_original','xxzqdm',day)
        for code,quote in quoted.items():
            self.fetch.budget.remaining()
            bse_numbers(quote,basics.get(code,{}))
        return dict(date=day,bse_quotes=quotes,bse_static=static)

    def security_part(self,day):
        fetch=self.fetch
        basic=self.stock_input('stock_basic',day)
        if basic is None:
            with BaostockClient(fetch,fetch.timeout) as client:
                fields,values=client.table('stock_basic')
            basic=dict(fields=fields,rows=values)
        basic_sha=next(row['sha256'] for row in reversed(fetch.records) if row['kind']=='stock_basic')
        mapping=_Mapping(fetch.budget.remaining)
        mapping.feed(fetch.get(MAPPING,referer=LIST_PAGE,session_handoff=True).decode('utf-8'))
        aliases={old:new for old,new,_first in mapping.rows}
        _need(len(aliases)==len(mapping.rows) and bool(aliases),'bse_mapping_duplicate')
        year=date.fromisoformat(day).year
        periods=tuple(f'{n}-12-31' for n in (year-2,year-1))
        company_rows=[]
        for period in periods:
            company_rows.extend(report_pages(fetch,self.source['url'],report=COMPANY_REPORT,
                columns=COMPANY_COLUMNS,filters=f'(REPORT_DATE=\'{period}\')(SECURITY_TYPE_CODE in ("058001001","058001008"))',
                sort='SECUCODE',max_pages=self.source['max_pages'],error_prefix='ashare_identity_report'))
        company_sha=fetch.objects.put(encode(company_rows))
        current_pool(basic,dict(fields=['code','date'],rows=[]),{},{},company_rows,periods,aliases,
            day,check=fetch.budget.remaining)
        fetch.records.append(dict(kind='stock_identity_reports',sha256=company_sha,media_type='application/json'))
        return dict(date=day,basic_sha256=basic_sha,identity_sha256=company_sha,
            periods=list(periods),aliases=aliases)

    def daily_part(self,day):
        fetch=self.fetch
        table=self.stock_input('stock_daily_batch',day)
        if table is None:
            with BaostockClient(fetch,fetch.timeout) as client:
                fields,values=client.table('stock_daily_batch',day,request_timeout=self.baostock_daily_timeout_seconds)
            table=dict(fields=fields,rows=values)
        fields,values=table['fields'],table['rows']
        _need(bool(values),'pb_day_not_published')
        validate_daily(table,day,fetch.budget.remaining)
        _need('date' in fields and all(row[fields.index('date')]==day for row in values),'pb_date_mismatch')
        receipt=next(row for row in reversed(fetch.records) if row['kind']=='stock_daily_batch')
        return self.describe(encode(dict(fields=fields,rows=values)),receipt['retrieved_at'])

    def create(self,day):
        self.attempt('ashare_capture',day)
        fetch=self.fetch
        try:
            # 日期会随下一交易日轮换的北交所原件先存；历史日线迟到时复用同日部件。
            bse=self.part(day,'bse_close',lambda:self.bse_part(day))
            securities=self.part(day,'security_identity',lambda:self.security_part(day))
            daily=self.part(day,'shsz_daily',lambda:self.daily_part(day))
            capture=ObjectCapture(fetch)
            basics=_pages(capture,bse['bse_static'],'bse_security_original','xxzqdm',day)
            quoted=_pages(capture,bse['bse_quotes'],'bse_quote_original','hqzqdm',day)
            universe=current_pool(_decode(fetch.objects.get(securities['basic_sha256'])),
                _decode(fetch.objects.get(daily['sha256'])),basics,quoted,
                _decode(fetch.objects.get(securities['identity_sha256'])),securities['periods'],
                securities['aliases'],day,check=fetch.budget.remaining)
            universe.update(source_basic_sha256=securities['basic_sha256'],
                source_identity_sha256=securities['identity_sha256'])
            manifest=dict(schema='guanheng.ashare-public-inputs.v1',date=day,
                closed_at=datetime.combine(date.fromisoformat(day),time(15,30),ZONE).isoformat(),
                universe=self.describe(encode(universe)),shsz_daily=daily,
                bse_quotes=bse['bse_quotes'],bse_static=bse['bse_static'])
            rows=self.normalizer(ObjectCapture(fetch),manifest,day,day)
            identity=fetch.objects.put(encode(manifest))
            fetch.records.append(dict(kind='ashare_public_inputs',sha256=identity,media_type='application/json'))
            source_manifest=fetch.objects.put(encode(fetch.records))
            self.record('ashare_capture',day,'success',packet_sha256=identity,source_manifest=source_manifest,
                market_count=universe['market_count'])
            return manifest,rows
        except BaseException as error:
            # 已持久的尝试/部件在停止与超时后继续可查；记录失败不覆盖原未知提交首因。
            if isinstance(error,ObservationError) and error.code=='write_outcome_unknown':raise
            try:
                fetch.budget.remaining()
                self.record('ashare_capture',day,'failed',error_code=getattr(error,'code','ashare_public_capture_failed'),
                    source_manifest=fetch.objects.put(encode(fetch.records)))
            except (SourceFailure,ObservationError,OSError):
                pass
            raise

    def get(self,day):
        records=self.receipts('ashare_capture',day,status='success')
        success=records[0] if records else None
        if success:
            self.restore_records(success)
            manifest=_decode(self.fetch.objects.get(success['packet_sha256']))
            return manifest,self.normalizer(ObjectCapture(self.fetch),manifest,day,day)
        return self.create(day)


def history(reader,fetch,source,start,end,*,retry_seconds=60,max_attempts=8,now=None,admitted_records=()):
    """读取闭合交易日及窗口内归档；升级口径用原有父原件完整重算。"""
    archive=Archive(reader,fetch,source,retry_seconds=retry_seconds,max_attempts=max_attempts,now=now,
        admitted_records=admitted_records)
    day=archive.closed_day(end)
    packet,rows=archive.get(day)
    by_day={day:rows}
    for receipt in reader.repository.source_archives('ashare_capture',source['id'],start,day,
            deadline=fetch.budget.deadline,cancelled=fetch.budget.cancelled,policy=archive.policy):
        captured=receipt['date']
        if captured in by_day:continue
        archive.restore_records(receipt)
        packet=_decode(fetch.objects.get(receipt['packet_sha256']))
        by_day[captured]=normalize(ObjectCapture(fetch),packet,captured,captured)
    _version,manifest=reader.snapshot()
    required=set();parents=set()
    for metric in source['datasets']:
        item=manifest['datasets'].get(metric)
        if item is None:continue
        # 当前方法增量沿既有历史；方法升级必须重新取得每个原观察日期的原件。
        if item['definition']['definition_version']==metric+'/1':
            required.update(row['date'] for row in reader.rows(item['partition']))
            parents.update(item['parents'])
    missing=required-set(by_day)
    seen=set()
    for identity in sorted(parents):
        if not missing:break
        fetch.budget.remaining()
        body=fetch.objects.get(identity)
        if not body.lstrip().startswith(b'['):continue
        records=_decode(body)
        if type(records) is not list:continue
        for record in records:
            if type(record) is not dict or record.get('kind')!='ashare_public_inputs':continue
            raw=record.get('sha256')
            if raw in seen:continue
            seen.add(raw);packet=_decode(fetch.objects.get(raw))
            captured=packet['date']
            if captured not in missing:continue
            by_day[captured]=normalize(ObjectCapture(fetch),packet,captured,captured)
            fetch.records.append(record)
            missing.remove(captured)
    _need(not missing,'ashare_archive_missing')
    return {key:[row for captured in sorted(by_day) for row in by_day[captured][key]]
        for key in rows}


def capture_due(reader,config,now,*,deadline,cancelled=None,fetcher_factory=Fetcher):
    """原服务收盘后预归档；同一采集lease内仅保存原件与收据，保持数据current。"""
    from .schedule_policy import local_now
    from .query import ObservationReader
    local=local_now(now)
    selected=[source for source in config['sources'] if source['kind']=='ashare_public']
    if not selected or (local.hour,local.minute)<(15,30):
        return dict(status='not_due',sources=[])
    limits=config['budget']
    budget=CollectionBudget(deadline,limits['max_requests'],limits['max_bytes'],limits['response_bytes'],
        cancelled=cancelled)
    bounded=ObservationReader(reader.repository,BoundedContentStore(reader.objects,budget))
    results=[]
    with reader.repository.collection_lease() as acquired:
        if not acquired:return dict(status='another_owner_running',sources=[])
        for source in selected:
            budget.remaining()
            fetch=fetcher_factory(bounded.objects,config['allowed_hosts'],
                timeout=min(config['timeout_seconds'],source.get('timeout_seconds',config['timeout_seconds'])),
                budget=budget)
            result=dict(source_id=source['id'])
            try:
                archive=Archive(bounded,fetch,source,retry_seconds=config['retry_seconds'],
                    max_attempts=config['max_window_attempts'],now=now)
                day=archive.closed_day(local.date().isoformat())
                if archive.receipts('ashare_capture',day,status='success'):
                    result.update(status='already_archived',date=day)
                else:
                    archive.get(day)
                    result.update(status='captured',date=day)
            except (SourceFailure,ObservationError) as error:
                result.update(status='failed',error_code=error.code)
            finally:
                fetch.close()
            results.append(result)
    return dict(status='checked',sources=results,requests=budget.requests,
        captured_bytes=budget.captured_bytes)
