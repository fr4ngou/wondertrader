"""独立QA作业：核官方缓存、提取年鉴并输出逐来源/日覆盖；不操作运行实例。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN
import hashlib
import gzip
import json
from pathlib import Path
import re
import sys
from typing import TypedDict, NotRequired


class CoverageEntry(TypedDict):
    source: str  # 五类业务来源名，单位由该来源定义。
    statistic_date: str  # 应有统计日，ISO日期，与取得时间分开。
    expected: bool  # 本次完整市场日历要求此来源存在。
    readable: bool  # 官方来源原件与规范值均通过当前解析校验。
    seed_readable: bool  # 原只读种子存在对应回执；总量报告另核原件。
    qualification: str | None  # 实际选中来源资格，缺失保留None。
    values: dict[str, str] | str | None  # 规范十进制值，份额亿份，其余亿元；缺失不填零。
    received_at: str | None  # 当前owner实际取得上界，带时区。
    origin_received_at: str | None  # 旧工程原采集时刻，带时区，不作为当前导入时刻。
    historical_first_available: str  # 恒unknown，历史首次发布时间未证实。
    evidence_sha256: str | None  # 日期、值、单位、实际知晓及原件共同身份。
    raw_sha256: str | None  # 原文或完整年鉴表格来源身份。
    references: tuple[str, ...]  # 可回读的原件、封套及页码定位。
    research_readable: bool  # 另有第三方研究候选，仍未进入官方默认事实流。
    unresolved_reason: str | None  # 未解决的实际原因，已解决为None。
    seed_failure: dict | None  # 原种子失败类型/原因，不把原请求失败改为零值。
    derived_symbols: NotRequired[list[str]]  # 份额字段具有相邻原件的证券；只对shares来源出现。
    publication_usable: bool  # 可形成完整原AuxiliaryPublication；市场合计要求双边。
    derived_usable: bool  # 原公式已具备数值派生前缀，区别于历史行因果资格。
    derived_available_at: str | None  # 所有依赖实际取得上界的最晚时刻，带时区。
    derived_time_basis: str  # 时钟依据声明，禁止由统计日伪造历史知晓时间。


class SourceCoverage(TypedDict):
    expected: int  # 本日历应有的统计日数量。
    seed_readable: int  # 种子中已核通过的原来源日数量。
    readable: int  # 官方补齐后可读来源日数量。
    research_only: int  # 仅有独立第三方研究候选的日数量。
    missing: list[str]  # 官方事实仍未解决的精确日期，零值不会充作缺失。
    tail: str | None  # 最新可读官方统计日，无事实则None。


class DerivedPoint(TypedDict):
    statistic_date: str  # 唯一原公式所用的最新来源统计日。
    value: float  # 0..100分位刻度，来自原策略模块，适配器不改公式。
    available_at: str  # 全部前缀依赖实际可知上界的最晚时刻，带时区。
    source_dates: list[str]  # 完整依赖来源日期，成交热度最多64点。


class DerivedReport(TypedDict):
    publications_by_kind: dict[str,int]  # 各类完整原AuxiliaryPublication数量。
    derived_by_kind: dict[str,list[DerivedPoint]]  # 逐统计日数值派生结果，历史生效资格另核。


class YearbookCell(TypedDict):
    value: str  # 交易所分板块股票成交额，亿元，原表精度0.01亿元。
    page: int  # PDF物理页码，从1开始，区别于书内印刷页码。
    month: int  # 此单元格所属统计月份，1..12，保持原空白月份位置。
    day: int  # 此单元格所属月份内日期，1..31。
    bbox: list[float]  # PDF坐标[x0,top,x1,bottom]，单位pt(1/72英寸)，原点为页面左上角。


class YearbookOverlap(TypedDict):
    day: str  # 两份官方来源均存在的同一统计日。
    yearbook: str  # 主板与创业板分表相加后的亿元数，保留十进制。
    official: str  # 已核接口原规范值，亿元，不被年鉴覆盖。
    difference: str  # 年鉴合计减接口值，亿元；两分表舍入可能造成0.01亿元尾差。


class YearbookBook(TypedDict):
    year: int  # 年鉴统计年份，区别于公开发行和本次取得年份。
    file: str  # 同目录原PDF文件名，拒绝跨目录路径。
    pdf_sha256: str  # 完整官方原PDF正文SHA256。
    url: str  # 原官方静态出版物URL，保持出版来源。
    received_at: str  # 本系统实际取得PDF的时刻，带UTC offset。
    unit: str  # 固定yi_CNY，即亿元人民币，按该表明确单位解释。
    boards: list[str]  # 固定main和chinext，表示主板及创业板股票口径。
    pages: dict[str,int]  # 各板块原PDF物理页码，从1开始。
    daily_cells: dict[str,dict[str,YearbookCell]]  # 统计日→板块→有坐标定位的单元格；空格不左移。
    overlap: list[YearbookOverlap]  # 年鉴与已核接口的真实重叠日差值。
    precision: str  # 每个分表0.01亿元展示精度，合计不冒充更高精度。
    redistribution_permission: str  # 原出版物再分发许可状态，原件仅在受控QA保留。


class YearbookPayload(TypedDict):
    extraction_version: str  # 坐标提取算法版本，参与单元格来源身份。
    books: list[YearbookBook]  # 完整原件、日期、单位及逐格提取的已核年鉴集合。


class YearbookDocument(TypedDict):
    schema: str  # 固定官方年鉴成交额协议版本。
    payload: YearbookPayload  # 原件与提取值的完整来源清单。
    payload_sha256: str  # payload规范JSON摘要，保护提取后修改。


class ResearchOverlap(TypedDict):
    statistic_date: str  # 官方与研究候选共同存在的统计日。
    research: str  # 第三方融资余额候选，规范为亿元，保留原精度。
    official: str  # 当前选中的官方融资余额，亿元。
    difference: str  # 研究候选减官方值，亿元，保留差值方向。
    within_display_resolution: bool  # 绝对差小于0.01亿元，仅作展示精度一致性检查。
    observed_truncation_match: bool  # 候选正数截断至0.01亿元后与官方值相同的观察，不推定源算法。


class AuditReport(TypedDict):
    schema: str  # 固定独立历史审计协议版本。
    observed_at: str  # 实际审计完成时刻，UTC offset明确。
    window_sha256: str  # 唯一一次读取窗口原文的SHA，与计算输入完全相同。
    window_rows: int  # 输入市场行数量，包含各证券逐日行。
    days: int  # 去重后的来源交易日数量。
    date_range: list[str]  # 输入首尾日期，不作为首尾间完整日历的推定。
    symbols: list[str]  # 实际请求的沪市ETF集合，证券缺口按Coverage记录。
    sources: dict[str,SourceCoverage]  # 五来源逐日汇总与实际缺口。
    official_complete_days: int  # 五来源均具备官方事实的日数量，不代替单字段覆盖。
    research_overlap: list[ResearchOverlap]  # 官方/研究候选的同日差值及展示精度关系。
    official_derived: DerivedReport  # 默认官方事实流派生，完全排除研究候选。
    research_derived: DerivedReport  # 显式研究流派生，保持research_only资格。
    source_qualification_counts: dict[str,int]  # 各来源资格的事实数量。
    actual_historical_merge_changed_rows: int  # 真实窗口严格知晓时钟下被合并改变的行数量。
    historical_merge_basis: str  # 实际取得依据声明，禁止回填历史首次知晓时间。
    seed_files: int  # 审计前种子普通文件数量。
    seed_unchanged: bool  # 种子前后完整文件集合/内容摘要一致。
    production_adopted: bool  # 本模块恒False，现场采用归Root。
    source_policy: str  # 默认官方流及显式研究流的来源边界。

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
if (REPO/'integrations/guanheng').is_dir():
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO/'integrations/guanheng'))
from auxiliary_history_sources import (SOURCES, _identity, load_facts, publications_from_facts,
                                       read_official_capture, read_research_margin, import_legacy_archive)


def write(path, value):
    """QA单写者输出，原子替换自身文件；调用前已拒绝写入种子根。"""
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def extract_table(page, year, page_number) -> dict[str,YearbookCell]:
    """按PDF坐标读取空白单元格，防止文本串行抽取把月份左移。"""
    words = page.extract_words()
    text = re.sub(r'\s+', '', page.extract_text())
    if f'每日成交金额表（{year}年）' not in text or '亿元人民币' not in text:
        raise ValueError('yearbook_table_heading_or_unit')
    labels = ('一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月')
    headers = [next(w for w in words if w['text']==name) for name in labels]
    centers = [(w['x0']+w['x1'])/2 for w in headers]
    boundaries = [(a+b)/2 for a,b in zip(centers,centers[1:])]
    date_header = next(w for w in words if w['text']=='日期')
    date_right = ((date_header['x0']+date_header['x1'])/2+centers[0])/2
    top = max(w['top'] for w in headers)
    days = [w for w in words if (w['x0']+w['x1'])/2<date_right and w['top']>top+15 and re.fullmatch(r'[1-9]|[12][0-9]|3[01]',w['text'])]
    if len(days)!=31 or {int(w['text'])for w in days}!=set(range(1,32)):
        raise ValueError('yearbook_date_grid')
    values: dict[str,YearbookCell] = {}
    for row in days:
        number = int(row['text'])
        for index in range(12):
            left = boundaries[index-1] if index else date_right
            right = boundaries[index] if index<11 else page.width
            cell = sorted((w for w in words if abs(w['top']-row['top'])<2.1
                           and left<(w['x0']+w['x1'])/2<right),key=lambda w:w['x0'])
            if not cell:
                continue
            value = ''.join(w['text']for w in cell)
            if not re.fullmatch(r'\d+\.\d{2}',value):
                raise ValueError('yearbook_numeric_cell')
            day = date(year,index+1,number).isoformat()
            values[day] = dict(value=value,page=page_number,month=index+1,day=number,
                               bbox=[round(left,3),round(row['top']-2.1,3),round(right,3),round(row['bottom']+2.1,3)])
    return values


def build_yearbooks(publications, seed, output):
    """从官方原PDF构建可复核表格；使用独立工具解释器，不增加运行服务依赖。"""
    import pdfplumber
    publications = Path(publications)
    output = Path(output).resolve()
    if Path(seed).resolve() in output.parents or output==Path(seed).resolve() or output==publications.resolve()/'RECEIPTS.json' or output.suffix!='.json':
        raise ValueError('yearbook_output_scope')
    receipts = json.loads((publications/'RECEIPTS.json').read_bytes())
    books: list[YearbookBook] = []
    for year, pages in ((2023,{'main':132,'chinext':225}),(2024,{'main':132,'chinext':226})):
        receipt = next(r for r in receipts if r['statistical_year']==year and r['status']=='captured')
        pdf = publications/(str(year)+'.pdf')
        if hashlib.sha256(pdf.read_bytes()).hexdigest()!=receipt['sha256']:
            raise ValueError('yearbook_download_identity')
        with pdfplumber.open(pdf) as document:
            tables={board:extract_table(document.pages[n-1],year,n)for board,n in pages.items()}
        if set(tables['main'])!=set(tables['chinext']):
            raise ValueError('yearbook_board_calendar_conflict')
        cells={day:{board:table[day]for board,table in tables.items()}for day in sorted(tables['main'])}
        comparisons: list[YearbookOverlap]=[]
        for day, values in cells.items():
            capture=Path(seed)/'szse-turnover'/(day+'.json')
            if capture.is_file():
                original=json.loads(capture.read_bytes())
                with gzip.open(capture.with_suffix('.json.gz'),'rb') as stream:
                    original_raw=stream.read(4*1024*1024+1)
                if (hashlib.sha256(original_raw).hexdigest()!=original['body_sha256'] or original['statistic_date']!=day
                        or original['source']!='szse-turnover'):
                    raise ValueError('yearbook_overlap_capture_identity')
                total=sum(Decimal(v['value'])for v in values.values())
                difference=total-Decimal(original['values'])
                comparisons.append(dict(day=day,yearbook=str(total),official=original['values'],difference=str(difference)))
        if year==2024 and (len(comparisons)<20 or any(abs(Decimal(c['difference']))>Decimal('.01')for c in comparisons)):
            raise ValueError('yearbook_overlap_not_qualified')
        books.append(dict(year=year,file=pdf.name,pdf_sha256=receipt['sha256'],url=receipt['url'],received_at=receipt['received_at'],
                          unit='yi_CNY',boards=['main','chinext'],pages=pages,daily_cells=cells,overlap=comparisons,
                          precision='each_board_rounded_to_0.01_yi_CNY',redistribution_permission='unverified; retained privately'))
    payload: YearbookPayload=dict(extraction_version='szse-yearbook-coordinate-grid-v1',books=books)
    document: YearbookDocument=dict(schema='guanheng.official-yearbook-turnover.v1',payload=payload,payload_sha256=_identity(payload))
    write(output,document)
    return dict(books=len(books),days=sum(len(b['daily_cells'])for b in books),overlap=sum(len(b['overlap'])for b in books))


def audit(seed, window_path, output, *, legacy_manifest=None, yearbook=None, research_margin=None):
    """真实原件→来源事实→原AuxiliaryPublication→原派生/合并；历史未知时点保持。"""
    from dataclasses import asdict
    from guanheng_strategy_v1.auxiliary import _percentiles, merge_auxiliary
    from guanheng_strategy_core.models import DailyObservation
    output, seed = Path(output).resolve(), Path(seed).resolve()
    if output==seed or seed in output.parents:
        raise ValueError('seed_output_overlap')
    output.mkdir(parents=True,exist_ok=True)
    window_raw=Path(window_path).read_bytes()
    window=json.loads(window_raw);rows=window['history']['observations']
    days=sorted({r['trade_date']for r in rows});symbols=sorted({r['symbol']for r in rows if r['symbol'].endswith('.SH')})
    before={str(p.relative_to(seed)):hashlib.sha256(p.read_bytes()).hexdigest()for p in seed.rglob('*')if p.is_file()}
    facts=load_facts((seed,),days,symbols,legacy_manifest=legacy_manifest,yearbook=yearbook,research_margin=research_margin)
    official=publications_from_facts(facts.values(),days)
    research=publications_from_facts(facts.values(),days,research=True)
    official_map={(f.source,str(f.statistic_date)):f for f in official.source_facts}
    initial_failures=json.loads((seed/'FAILURES.json').read_bytes())
    coverage: list[CoverageEntry]=[]
    for day in days:
        for source in SOURCES:
            key=(source,day);fact=official_map.get(key);candidate=facts.get(key)
            error=initial_failures.get(day,{}).get(source)
            coverage.append(dict(source=source,statistic_date=day,expected=True,readable=fact is not None,
                seed_readable=(seed/source/(day+'.json')).is_file(),qualification=fact.qualification if fact else None,
                values=fact.values if fact else None,received_at=fact.received_at.isoformat()if fact else None,
                origin_received_at=fact.origin_received_at.isoformat()if fact and fact.origin_received_at else None,
                historical_first_available='unknown',evidence_sha256=fact.evidence_sha256 if fact else None,
                raw_sha256=fact.raw_sha256 if fact else None,references=fact.references if fact else (),
                research_readable=candidate is not None and candidate.qualification=='research_only',
                unresolved_reason=None if fact else ('source_not_published_in_seed_response' if error and error.get('reason')=='auxiliary_source_not_published' else 'source_request_or_parse_unresolved' if day==days[-1] else 'official_transport_unavailable; research_candidate_separate' if candidate else 'official_transport_unavailable'),seed_failure=error))
    research_overlap: list[ResearchOverlap]=[]
    if research_margin:
        for fact in read_research_margin(*research_margin):
            original=official_map.get((fact.source,str(fact.statistic_date)))
            if original:
                difference=Decimal(fact.values)-Decimal(original.values)
                research_overlap.append(dict(statistic_date=str(fact.statistic_date),research=fact.values,
                    official=original.values,difference=str(difference),within_display_resolution=abs(difference)<Decimal('.01'),
                    observed_truncation_match=Decimal(fact.values).quantize(Decimal('.01'),rounding=ROUND_DOWN)==Decimal(original.values)))
    def derived(bundle):
        facts_by_kind={kind:[p for p in bundle.publications if p.kind==kind]for kind in ('shares','turnover','margin')}
        result={kind:_percentiles(facts_by_kind[kind],5 if kind=='turnover' else 1)for kind in ('turnover','margin')}
        return dict(publications_by_kind={k:len(v)for k,v in facts_by_kind.items()},
                    derived_by_kind={k:[dict(statistic_date=str(x.statistic_date),value=x.value,available_at=x.available_at.isoformat(),source_dates=[str(d)for d in x.source_dates])for x in v]for k,v in result.items()})
    def observation(row):
        value=dict(row);value['trade_date']=date.fromisoformat(value['trade_date'])
        for name in ('market_available_at','auxiliary_available_at'):
            if value.get(name):value[name]=datetime.fromisoformat(value[name])
        for name in ('auxiliary_source_dates','evidence_refs'):
            if name in value:value[name]=tuple(date.fromisoformat(d)for d in value[name])if name.endswith('dates')else tuple(value[name])
        return DailyObservation(**value)
    original=tuple(observation(row)for row in rows)
    merged=merge_auxiliary(original,official.publications)
    official_derived,research_derived=derived(official),derived(research)
    derived_days={kind:{v['statistic_date']:v for v in values}for kind,values in official_derived['derived_by_kind'].items()}
    pairs={(p.kind,str(p.statistic_date)):p for p in official.publications if p.kind!='shares'}
    for entry in coverage:
        day=entry['statistic_date'];kind=entry['source'].split('-')[1]
        if kind=='shares':
            index=days.index(day);previous=official_map.get(('sse-shares',days[index-1]))if index else None
            current=official_map.get(('sse-shares',day))
            entry['derived_symbols']=sorted(set(previous.values)&set(current.values))if previous and current else []
            entry['publication_usable']=current is not None
            entry['derived_usable']=bool(entry['derived_symbols'])
            entry['derived_available_at']=max(previous.received_at,current.received_at).isoformat()if entry['derived_usable']else None
        else:
            entry['publication_usable']=(kind,day)in pairs
            entry['derived_usable']=day in derived_days[kind]
            entry['derived_available_at']=derived_days[kind][day]['available_at']if entry['derived_usable']else None
        entry['derived_time_basis']='actual_receipt_or_current_import_upper_bound; no historical backfill'
    summaries: dict[str,SourceCoverage]={source:dict(expected=len(days),seed_readable=sum(r['seed_readable']for r in coverage if r['source']==source),
        readable=sum(r['readable']for r in coverage if r['source']==source),research_only=sum(r['research_readable']for r in coverage if r['source']==source),
        missing=[r['statistic_date']for r in coverage if r['source']==source and not r['readable']],
        tail=max((r['statistic_date']for r in coverage if r['source']==source and r['readable']),default=None))for source in SOURCES}
    report: AuditReport=dict(schema='guanheng.auxiliary-history-audit.v1',observed_at=datetime.now(timezone.utc).isoformat(),
        window_sha256=hashlib.sha256(window_raw).hexdigest(),window_rows=len(rows),days=len(days),date_range=[days[0],days[-1]],symbols=symbols,
        sources=summaries,official_complete_days=sum(all((s,d)in official_map for s in SOURCES)for d in days),
        research_overlap=research_overlap,
        official_derived=official_derived,research_derived=research_derived,
        source_qualification_counts=dict(Counter(f.qualification for f in facts.values())),
        actual_historical_merge_changed_rows=sum(a!=b for a,b in zip(original,merged)),
        historical_merge_basis='actually received; no historical first visibility assumption',
        seed_files=len(before),seed_unchanged=before=={str(p.relative_to(seed)):hashlib.sha256(p.read_bytes()).hexdigest()for p in seed.rglob('*')if p.is_file()},
        production_adopted=False,source_policy='official-only default; research candidates never silently enter official bundle')
    # 保留计算时的唯一原文，运行窗口随后更新仍可按报告SHA重现本次输入。
    (output/'MARKET-WINDOW.json').write_bytes(window_raw)
    write(output/'COVERAGE.json',coverage);write(output/'REPORT.json',report)
    write(output/'SEED-INVENTORY.json',before)
    write(output/'FACTS.json',[dict(asdict(f),statistic_date=str(f.statistic_date),received_at=f.received_at.isoformat(),origin_received_at=f.origin_received_at.isoformat()if f.origin_received_at else None)for f in facts.values()])
    write(output/'OFFICIAL-PUBLICATIONS.json',[dict(asdict(p),statistic_date=str(p.statistic_date),available_at=p.available_at.isoformat(),received_at=p.received_at.isoformat())for p in official.publications])
    concise={source:{k:v for k,v in summary.items()if k!='missing'}|{'missing_count':len(summary['missing'])}for source,summary in summaries.items()}
    return dict(days=len(days),sources=concise,official_publications=len(official.publications),research_publications=len(research.publications),
                actual_historical_merge_changed_rows=report['actual_historical_merge_changed_rows'],seed_unchanged=report['seed_unchanged'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependency-root',type=Path,required=True)
    parser.add_argument('--seed',type=Path,required=True)
    parser.add_argument('--window',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--yearbook',type=Path)
    parser.add_argument('--legacy-manifest',type=Path)
    parser.add_argument('--import-legacy',type=Path)
    parser.add_argument('--research-margin',nargs=2,type=Path)
    parser.add_argument('--build-yearbooks',type=Path)
    args=parser.parse_args();sys.path.insert(0,str(args.dependency_root))
    if args.import_legacy:
        if not args.window:parser.error('window required')
        window=json.loads(args.window.read_bytes());days={row['trade_date']for row in window['history']['observations']}
        result=import_legacy_archive(args.import_legacy,args.seed,days,args.output)
    elif args.build_yearbooks:
        result=build_yearbooks(args.build_yearbooks,args.seed,args.output)
    else:
        if not args.window:parser.error('window required')
        result=audit(args.seed,args.window,args.output,legacy_manifest=args.legacy_manifest,yearbook=args.yearbook,research_margin=tuple(args.research_margin)if args.research_margin else None)
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
