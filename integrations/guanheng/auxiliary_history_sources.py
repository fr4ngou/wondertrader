"""辅助历史缺口的只读来源适配。

复用AWP官方JSON解析与策略唯一派生；补充交易所年鉴的有出处统计。
第三方研究材料保持独立，默认事实流只含交易所来源。种子目录从不写入。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import math
import os
from io import BytesIO
from pathlib import Path
from typing import Iterable, TypedDict
from uuid import uuid4
from urllib.parse import urlsplit, parse_qs
from xml.etree import ElementTree
from zipfile import ZipFile

SOURCES = ('sse-shares', 'sse-turnover', 'szse-turnover', 'sse-margin', 'szse-margin')
MAX_RAW_BYTES = 32 * 1024 * 1024


class _LegacyRecord(TypedDict):
    source: str  # 所补五类业务来源之一，原件仍属于交易所来源。
    statistic_date: str  # 原统计日，ISO日期，区别于取得日。
    raw: str  # 独立导入目录内的原件相对路径，内容须与原SHA一致。
    evidence: str  # 独立目录内原v3封套相对路径，保持原字段和摘要。
    original_raw: str  # 旧工程原件路径，仅用于追溯，消费从独立副本读取。
    original_evidence: str  # 旧工程原封套路径，原工程保持只读。
    values: str  # 正数十进制规范值，成交额/融资余额均为亿元。
    received_at: str  # 当前owner首次导入时刻，带UTC offset，缓存复用保持原值。
    origin_received_at: str  # 旧工程原始采集时刻，带UTC offset，不授当前owner历史知晓资格。


class _LegacyPayload(TypedDict):
    records: list[_LegacyRecord]  # 此冻结作业成功导入的原件及规范值。
    origin: str  # 已解析绝对路径的旧原件根，续接须匹配。
    seed: str  # 已解析绝对路径的只读种子根，续接须匹配。
    requested_days: list[str]  # 本次有限作业完整日期集合；扩大范围须新作业。
    historical_first_available: str  # 恒为unknown，历史首次可获知时间未经证明。


class _LegacyDocument(TypedDict):
    schema: str  # 固定导入协议guanheng.legacy-official-import.v1。
    payload: _LegacyPayload  # 范围与来源均绑定的不可变导入事实。
    payload_sha256: str  # payload规范JSON摘要，不以可变游标代替原件。


@dataclass(frozen=True, slots=True)
class SourceFact:
    """统计事实及出处；历史首次可知时刻始终保留未知。"""
    source: str  # 五类业务来源名；替代出版物仍标识所补业务来源。
    statistic_date: date  # 原统计日，区别于实际取得日及策略生效日。
    values: dict[str, str] | str  # 十进制规范值：份额亿份，其余亿元；缺失不填零。
    received_at: datetime  # 实际取得原文时刻，带时区；复用缓存保留原时刻。
    raw_sha256: str  # 原文SHA256；组合年鉴绑定完整PDF及表格提取身份。
    evidence_sha256: str  # 日期、单位、数值、来源及实际取得时刻共同组成的身份。
    qualification: str  # official_json、official_archive、official_yearbook或research_only，保持来源资格。
    references: tuple[str, ...]  # 原件/回执与页码定位；只指向调用者受控证据目录。
    origin_received_at: datetime | None = None  # 旧系统原采集时刻；当前owner取得时刻另由received_at表示。


@dataclass(frozen=True, slots=True)
class PublicationBundle:
    """明确资格的只读消费结果；研究包与官方包分别命名。"""
    publications: tuple  # 原AuxiliaryPublication；不改原派生、生效日和信号规则。
    qualification: str  # official_observed或research_only；研究包由显式入口取得。
    missing: tuple[tuple[str, str], ...]  # 尚缺的来源/统计日，不能由空值或零替代。
    source_facts: tuple[SourceFact, ...]  # 生成本批次公共事实的完整来源身份。


def _json(path: Path):
    if path.stat().st_size > MAX_RAW_BYTES:
        raise ValueError('history_metadata_capacity')
    with path.open('rb') as stream:
        raw = stream.read(MAX_RAW_BYTES + 1)
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError('history_metadata_capacity')
    return json.loads(raw)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity(value) -> str:
    return _hash(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                            allow_nan=False).encode('utf-8'))


def _positive(value) -> str:
    number = Decimal(str(value).replace(',', ''))
    if not number.is_finite() or number <= 0:
        raise ValueError('history_source_positive_number')
    return str(number)


def _received(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError('history_source_timezone')
    return stamp


def _finite_float(value) -> float:
    """公共策略接口使用float；十进制转换后的溢出、下溢与非正数在此拒绝。"""
    number=float(value)
    if not math.isfinite(number) or number<=0:
        raise ValueError('history_publication_float_range')
    return number


def _fact(source, day, values, received, raw_sha, qualification, references, origin_received=None):
    if source not in SOURCES:
        raise ValueError('history_source_name')
    parsed_day = date.fromisoformat(day)
    stamp = _received(received)
    if stamp.astimezone(timezone(timedelta(hours=8))).date() < parsed_day or len(raw_sha) != 64 or any(c not in '0123456789abcdef' for c in raw_sha):
        raise ValueError('history_source_identity')
    values = {k: _positive(v) for k, v in values.items()} if isinstance(values, dict) else _positive(values)
    origin = _received(origin_received) if origin_received else None
    if origin and origin>stamp:
        raise ValueError('history_import_before_origin')
    identity = _identity(dict(source=source, statistic_date=day, values=values, unit='yi_shares' if source=='sse-shares' else 'yi_CNY',
                              received_at=stamp.isoformat(),origin_received_at=origin.isoformat()if origin else None,
                              raw_sha256=raw_sha, qualification=qualification))
    return SourceFact(source, parsed_day, values, stamp, raw_sha, identity, qualification, tuple(references),origin)


def _legacy_value(evidence, body):
    """只读旧工程交易所原件；核v3封套，不运行旧工程代码或使用其历史知晓假设。"""
    source_id = evidence['source_id']
    sources = {'szse-margin-balance':('szse-margin','1837_xxpl','txtDate'),
               'szse-stock-turnover':('szse-turnover','1803_sczm','txtQueryDate')}
    if source_id not in sources:
        raise ValueError('history_legacy_source')
    source,catalog,parameter = sources[source_id]
    address=urlsplit(evidence['request_url']);query=parse_qs(address.query)
    day=evidence['statistic_date'];date.fromisoformat(day)
    suffix='.json' if source=='szse-margin' else '.xlsx'
    expected_ref=f'minio://replay-datasets/resonance-regime/raw/{source_id}/{day}/{_hash(body)}{suffix}'
    if (address.scheme!='https' or address.netloc!='www.szse.cn'
            or address.path!=('/api/report/ShowReport/data' if source=='szse-margin' else '/api/report/ShowReport')
            or query.get('CATALOGID')!=[catalog] or query.get(parameter)!=[day]
            or query.get('SHOWTYPE')!=['JSON' if source=='szse-margin' else 'xlsx']
            or set(query)-{'CATALOGID',parameter,'SHOWTYPE','TABKEY'}
            or evidence.get('status_code')!=200 or evidence.get('parser_version')!='resonance-official-auxiliary-v3'
            or evidence.get('schema_version')!='1.0' or evidence.get('frozen') is not True
            or evidence.get('executable') is not False or evidence['object_ref']!=expected_ref
            or len(body)>MAX_RAW_BYTES or len(body)!=evidence['body_size'] or _hash(body)!=evidence['body_sha256']):
        raise ValueError('history_legacy_envelope')
    names=('schema_version','parser_version','source_id','statistic_date','request_url','source_page',
           'retrieved_at','status_code','content_type','body_sha256','body_size','object_ref')
    content={k:evidence[k]for k in names}
    content['statistic_date']=date.fromisoformat(day);content['retrieved_at']=_received(evidence['retrieved_at'])
    identity=_hash(json.dumps(content,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode('utf-8'))
    if identity!=evidence['evidence_sha256']:
        raise ValueError('history_legacy_evidence_sha256')
    if source=='szse-margin':
        from guanheng_analysis_window_producer.official_auxiliary import parse_source
        return source,parse_source(source,day,body,set())
    # 旧缓存官方导出为XLSX；这里只解析列名/单位，不根据列序或指数金额推断。
    namespace='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    with ZipFile(BytesIO(body))as archive:
        members=archive.infolist()
        if len(members)>200 or sum(p.file_size for p in members)>50*1024*1024:
            raise ValueError('history_legacy_xlsx_capacity')
        shared=[]
        if 'xl/sharedStrings.xml'in archive.namelist():
            shared=[''.join(t.itertext())for t in ElementTree.fromstring(archive.read('xl/sharedStrings.xml')).findall(namespace+'si')]
        rows=[]
        for row in ElementTree.fromstring(archive.read('xl/worksheets/sheet1.xml')).iter(namespace+'row'):
            cells={}
            for cell in row.findall(namespace+'c'):
                reference=cell.get('r','');letters=''.join(c for c in reference if c.isalpha());column=0
                for letter in letters:column=column*26+ord(letter)-ord('A')+1
                if not 1<=column<=64:raise ValueError('history_legacy_xlsx_column')
                value=cell.findtext(namespace+'v',default='')
                if cell.get('t')=='s':value=shared[int(value)]
                elif cell.get('t')=='inlineStr':value=''.join(t.text or ''for t in cell.iter(namespace+'t'))
                cells[column]=''.join(value.split())
            rows.append(cells)
    headers=[row for row in rows if '证券类别'in row.values() and any('成交金额'in v for v in row.values())]
    if len(headers)!=1:raise ValueError('history_legacy_xlsx_header')
    header=headers[0];kind=next(k for k,v in header.items()if v=='证券类别')
    amounts=[(k,v)for k,v in header.items()if v.startswith('成交金额')]
    if len(amounts)!=1:raise ValueError('history_legacy_xlsx_amount')
    column,label=amounts[0];stocks=[row for row in rows if row.get(kind)=='股票']
    if len(stocks)!=1:raise ValueError('history_legacy_xlsx_stock')
    amount=Decimal(_positive(stocks[0][column]))
    if '亿元'in label:return source,str(amount)
    if '元'in label:return source,str(amount/Decimal(100000000))
    raise ValueError('history_legacy_xlsx_unit')


def import_legacy_archive(root: Path, seed: Path, days: Iterable[str], output: Path) -> dict:
    """复制旧工程已归档且当前种子缺少的原件到独立QA；不写旧工程/种子。

    导入时刻固定在新清单，旧原采集时刻保留在原封套。历史首次未知；旧09:25
    等研究假设不进入本事实流。已有导入按原件SHA回读后复用。
    """
    from datetime import timezone
    root,seed,output=Path(root).resolve(),Path(seed).resolve(),Path(output).resolve()
    days=sorted(set(days))
    if not days or len(days)>4096 or any(date.fromisoformat(d).isoformat()!=d for d in days):
        raise ValueError('history_legacy_scope_capacity')
    if any(output==p or p in output.parents or output in p.parents for p in (root,seed)):
        raise ValueError('history_legacy_output_overlap')
    manifest=output/'ARCHIVE.json'
    if manifest.exists():
        payload=_json(manifest)['payload']
        if (payload.get('origin')!=str(root) or payload.get('seed')!=str(seed) or payload.get('requested_days')!=days):
            raise ValueError('history_legacy_job_scope_changed; use a new output root')
        result=read_legacy_manifest(manifest)
        return dict(reused=True,records=len(result),manifest=str(manifest))
    output.mkdir(parents=True,exist_ok=True);records=[]
    received=datetime.now(timezone.utc).isoformat()
    for source,source_id in (('szse-margin','szse-margin-balance'),('szse-turnover','szse-stock-turnover')):
        for day in sorted(set(days)):
            date.fromisoformat(day)
            if (seed/source/(day+'.json')).exists():continue
            candidates=[]
            for path in (root/'evidence'/source_id/day).glob('*.json'):
                evidence=_json(path)
                if evidence.get('parser_version')!='resonance-official-auxiliary-v3':continue
                sha=evidence.get('body_sha256','')
                if len(sha)!=64 or any(c not in '0123456789abcdef'for c in sha):
                    raise ValueError('history_legacy_body_sha256')
                suffix='.json'if source=='szse-margin'else'.xlsx'
                raw_path=root/'raw'/source_id/day/(evidence['body_sha256']+suffix)
                if not raw_path.is_file():continue
                if raw_path.stat().st_size>MAX_RAW_BYTES:raise ValueError('history_legacy_raw_capacity')
                with raw_path.open('rb')as stream:body=stream.read(MAX_RAW_BYTES+1)
                _,value=_legacy_value(evidence,body)
                candidates.append((evidence,body,value,path,raw_path))
            if not candidates:continue
            if len({v[2]for v in candidates})!=1:raise ValueError('history_legacy_revision_conflict')
            evidence,body,value,evidence_path,raw_path=min(candidates,key=lambda v:_received(v[0]['retrieved_at']))
            directory=output/source/day;directory.mkdir(parents=True,exist_ok=True)
            target=directory/raw_path.name;target.write_bytes(body)
            envelope=directory/evidence_path.name;envelope.write_bytes(evidence_path.read_bytes())
            record: _LegacyRecord=dict(source=source,statistic_date=day,raw=str(target.relative_to(output)),
                evidence=str(envelope.relative_to(output)),original_raw=str(raw_path),original_evidence=str(evidence_path),
                values=value,received_at=received,origin_received_at=evidence['retrieved_at'])
            records.append(record)
    payload: _LegacyPayload=dict(records=records,origin=str(root),seed=str(seed),requested_days=days,historical_first_available='unknown')
    document: _LegacyDocument=dict(schema='guanheng.legacy-official-import.v1',payload=payload,payload_sha256=_identity(payload))
    temporary=manifest.with_name('ARCHIVE.'+str(uuid4())+'.tmp')
    # 先完整写入和回读全部原件，再原子提交；进程中断不会留下截断的正式清单。
    with temporary.open('xb')as stream:
        stream.write(json.dumps(document,indent=2).encode('utf-8'));stream.flush();os.fsync(stream.fileno())
    read_legacy_manifest(temporary)
    os.replace(temporary,manifest)
    return dict(reused=False,records=len(records),manifest=str(manifest))


def read_legacy_manifest(manifest: Path) -> tuple[SourceFact,...]:
    """消费独立导入清单，逐份核原封套和正文；原工程无需运行或在线。"""
    manifest=Path(manifest);document=_json(manifest)
    if document.get('schema')!='guanheng.legacy-official-import.v1' or document.get('payload_sha256')!=_identity(document['payload']):
        raise ValueError('history_legacy_manifest')
    result=[]
    for record in document['payload']['records']:
        paths=[]
        for key in ('raw','evidence'):
            p=(manifest.parent/record[key]).resolve()
            if manifest.parent.resolve()not in p.parents:raise ValueError('history_legacy_path')
            paths.append(p)
        raw_path,envelope=paths
        if raw_path.stat().st_size>MAX_RAW_BYTES:raise ValueError('history_legacy_raw_capacity')
        with raw_path.open('rb')as stream:body=stream.read(MAX_RAW_BYTES+1)
        evidence=_json(envelope)
        source,value=_legacy_value(evidence,body)
        if source!=record['source'] or value!=record['values'] or evidence['statistic_date']!=record['statistic_date'] or evidence['retrieved_at']!=record['origin_received_at']:
            raise ValueError('history_legacy_import_values')
        result.append(_fact(source,record['statistic_date'],value,record['received_at'],evidence['body_sha256'],
            'official_archive',(str(raw_path),str(envelope),record['original_raw'],record['original_evidence']),record['origin_received_at']))
    if len({(f.source,f.statistic_date)for f in result})!=len(result):raise ValueError('history_legacy_duplicate')
    return tuple(result)


def read_official_capture(root: Path, source: str, day: str, symbols: Iterable[str]) -> SourceFact | None:
    """核对原件、请求、日期、单位及规范值；只读原缓存，缺文件返回None。"""
    from guanheng_analysis_window_producer.official_auxiliary import parse_source, source_request
    if source not in SOURCES or date.fromisoformat(day).isoformat()!=day:
        raise ValueError('history_source_or_date')
    receipt = Path(root) / source / (day + '.json')
    if not receipt.exists():
        return None
    record = _json(receipt)
    archive = receipt.with_suffix('.json.gz')
    # 限制解压后容量，避免gzip头声明或压缩大小代替实际读取边界。
    with gzip.open(archive, 'rb') as stream:
        body = stream.read(MAX_RAW_BYTES + 1)
    url, _ = source_request(source, day)
    if (len(body) > MAX_RAW_BYTES or record.get('schema') != 'guanheng.official-auxiliary-capture.v1'
            or record.get('source') != source or record.get('statistic_date') != day
            or record.get('url') != url or _hash(body) != record.get('body_sha256')
            or record.get('historical_first_available') != 'unknown'):
        raise ValueError('history_capture_identity')
    complete_symbols=set(record['values'])if source=='sse-shares'and type(record['values'])is dict else set()
    values = parse_source(source, day, body, complete_symbols)
    if values != record['values']:
        raise ValueError('history_capture_values')
    if source=='sse-shares':
        requested=set(symbols);values={k:v for k,v in values.items()if k in requested}
    return _fact(source, day, values, record['received_at'], record['body_sha256'],
                 'official_json', (str(receipt), str(archive)))


def read_yearbook_facts(bundle_path: Path) -> tuple[SourceFact, ...]:
    """读取经逐格提取并核过重叠期的交易所年鉴；原PDF与表格均保留身份。

    年鉴中的主板与创业板每日股票成交额相加；各表按0.01亿元四舍五入，
    合计与接口总额可相差0.01亿元。本入口不覆盖已有接口数值。
    """
    bundle_path = Path(bundle_path)
    document = _json(bundle_path)
    if document.get('schema') != 'guanheng.official-yearbook-turnover.v1':
        raise ValueError('history_yearbook_schema')
    payload = document['payload']
    if document.get('payload_sha256') != _identity(payload):
        raise ValueError('history_yearbook_payload')
    result = []
    for book in payload['books']:
        if Path(book['file']).name!=book['file'] or Path(book['file']).suffix!='.pdf' or not book['url'].startswith('https://docs.static.szse.cn/www/market/periodical/year/'):
            raise ValueError('history_yearbook_publisher_or_path')
        pdf = bundle_path.parent / book['file']
        if pdf.stat().st_size > MAX_RAW_BYTES or _hash(pdf.read_bytes()) != book['pdf_sha256']:
            raise ValueError('history_yearbook_raw_identity')
        if book.get('unit') != 'yi_CNY' or book.get('boards') != ['main', 'chinext']:
            raise ValueError('history_yearbook_scope_or_unit')
        received = book['received_at']
        for day, cells in book['daily_cells'].items():
            if date.fromisoformat(day).year != book['year'] or set(cells) != {'main', 'chinext'}:
                raise ValueError('history_yearbook_date_or_cells')
            total = sum(Decimal(_positive(cells[k]['value'])) for k in ('main', 'chinext'))
            for name, cell in cells.items():
                if cell['page'] != book['pages'][name] or cell['month'] != date.fromisoformat(day).month or cell['day'] != date.fromisoformat(day).day:
                    raise ValueError('history_yearbook_cell_locator')
            raw_sha = _identity(dict(pdf_sha256=book['pdf_sha256'], day=day, cells=cells,
                                     extraction=payload['extraction_version']))
            result.append(_fact('szse-turnover', day, str(total), received, raw_sha,
                                 'official_yearbook', (str(pdf), str(bundle_path),
                                  'pdf_pages:' + ','.join(str(book['pages'][k]) for k in ('main', 'chinext')))))
    if len({p.statistic_date for p in result}) != len(result):
        raise ValueError('history_yearbook_duplicate_date')
    return tuple(result)


def read_research_margin(archive: Path, receipt: Path) -> tuple[SourceFact, ...]:
    """东方财富公开展示的深市融资余额；保留研究资格，禁止混入默认官方包。"""
    record = _json(Path(receipt))
    address=urlsplit(record['url']);query=parse_qs(address.query)
    if (address.scheme!='https' or address.hostname!='datacenter-web.eastmoney.com'
            or address.path!='/api/data/v1/get' or query.get('reportName')!=['RPTA_WEB_RZRQ_LSSH']
            or record.get('qualification')!='research_only_rights_and_official_scope_not_accepted'):
        raise ValueError('history_research_provider_or_qualification')
    with gzip.open(archive, 'rb') as stream:
        raw = stream.read(MAX_RAW_BYTES + 1)
    if len(raw) > MAX_RAW_BYTES or _hash(raw) != record['body_sha256']:
        raise ValueError('history_research_raw_identity')
    value = json.loads(raw)
    rows = value.get('result', {}).get('data', [])
    if not value.get('success') or value['result'].get('count') != len(rows) or value['result'].get('pages') != 1:
        raise ValueError('history_research_incomplete_page')
    result = []
    for row in rows:
        if row.get('SCDM') != '001':
            raise ValueError('history_research_wrong_market')
        day = row['DIM_DATE'].split(' ')[0]
        # RZYE为融资余额人民币元；RZRQYE包含融券，保持字段隔离。
        number = Decimal(_positive(row['RZYE'])) / Decimal(100000000)
        result.append(_fact('szse-margin', day, str(number), record['received_at'], record['body_sha256'],
                             'research_only', (str(archive), str(receipt))))
    if len({p.statistic_date for p in result}) != len(result):
        raise ValueError('history_research_duplicate_date')
    return tuple(result)


def load_facts(seed_roots: Iterable[Path], days: Iterable[str], symbols: Iterable[str], *,
               legacy_manifest: Path | None = None, yearbook: Path | None = None,
               research_margin: tuple[Path, Path] | None = None):
    """按原来源读取完整日历；官方JSON优先，来源修订冲突交owner处理。

    补充年鉴须显式指定。第三方材料由research_margin独立参数加入，事实资格仍为研究。
    """
    days, symbols, roots = tuple(sorted(set(days))), tuple(symbols), tuple(Path(p) for p in seed_roots)
    if not days or len(days) > 4096 or not roots or len(roots) > 16:
        raise ValueError('history_input_capacity')
    selected = {}
    for day in days:
        for source in SOURCES:
            found = [p for root in roots if (p := read_official_capture(root, source, day, symbols)) is not None]
            if not found:
                continue
            if len({_identity(p.values) for p in found}) > 1:
                raise ValueError('history_official_revision_requires_owner')
            # 同值复用最早实际取得时刻；后来重采不抹去已经存在的本系统知晓证据。
            selected[source, day] = min(found, key=lambda p: p.received_at)
    archive = read_legacy_manifest(legacy_manifest) if legacy_manifest else ()
    supplementary = read_yearbook_facts(yearbook) if yearbook else ()
    research = read_research_margin(*research_margin) if research_margin else ()
    for fact in archive + supplementary + research:
        day = str(fact.statistic_date)
        if day in days:
            selected.setdefault((fact.source, day), fact)
    return selected


def publications_from_facts(facts: Iterable[SourceFact], days: Iterable[str], *, research: bool = False) -> PublicationBundle:
    """沿原AuxiliaryPublication对接唯一数学模块；可获知时刻取实际取得上界。

    research=False过滤所有第三方研究事实。历史首次未知保持在来源清单，
    不由统计日推算available_at；历史收盘不因补采而获得未来事实。
    """
    from guanheng_strategy_v1.auxiliary import AuxiliaryPublication
    days = tuple(sorted(set(days)))
    if not days or len(days) > 4096:
        raise ValueError('history_input_capacity')
    selected = {}
    for fact in facts:
        if not isinstance(fact, SourceFact) or fact.qualification not in ('official_json','official_archive','official_yearbook','research_only'):
            raise ValueError('history_fact_qualification')
        checked = _fact(fact.source,str(fact.statistic_date),fact.values,fact.received_at.isoformat(),
                        fact.raw_sha256,fact.qualification,fact.references,
                        fact.origin_received_at.isoformat()if fact.origin_received_at else None)
        if checked.evidence_sha256 != fact.evidence_sha256:
            raise ValueError('history_fact_identity')
        if fact.qualification == 'research_only' and not research:
            continue
        if str(fact.statistic_date) not in days:
            continue
        key = (fact.source, str(fact.statistic_date))
        if key in selected:
            raise ValueError('history_duplicate_fact')
        selected[key] = fact
    output = []
    for day in days:
        shares = selected.get(('sse-shares', day))
        if shares:
            for symbol, value in shares.values.items():
                output.append(AuxiliaryPublication('shares', shares.statistic_date, _finite_float(value),
                              shares.received_at, shares.received_at, shares.evidence_sha256, symbol))
        for kind in ('turnover', 'margin'):
            pair = [selected.get((exchange + '-' + kind, day)) for exchange in ('sse', 'szse')]
            if not all(pair):
                continue
            available = max(p.received_at for p in pair)
            try:number = sum(Decimal(p.values) for p in pair)
            except ArithmeticError:raise ValueError('history_publication_decimal_range')from None
            identity = _identity(dict(kind=kind, statistic_date=day,
                                      sources=[p.evidence_sha256 for p in pair], available_at=available.isoformat()))
            output.append(AuxiliaryPublication(kind, date.fromisoformat(day), _finite_float(number),
                                               available, available, identity))
    missing = tuple((source, day) for day in days for source in SOURCES if (source, day) not in selected)
    return PublicationBundle(tuple(output), 'research_only' if research else 'official_observed',
                             missing, tuple(selected.values()))
