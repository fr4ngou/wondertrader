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


def extract_table(page, year, page_number):
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
    values = {}
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
    books = []
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
        comparisons=[]
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
    payload=dict(extraction_version='szse-yearbook-coordinate-grid-v1',books=books)
    write(output,dict(schema='guanheng.official-yearbook-turnover.v1',payload=payload,payload_sha256=_identity(payload)))
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
    window=json.loads(Path(window_path).read_bytes());rows=window['history']['observations']
    days=sorted({r['trade_date']for r in rows});symbols=sorted({r['symbol']for r in rows if r['symbol'].endswith('.SH')})
    before={str(p.relative_to(seed)):hashlib.sha256(p.read_bytes()).hexdigest()for p in seed.rglob('*')if p.is_file()}
    facts=load_facts((seed,),days,symbols,legacy_manifest=legacy_manifest,yearbook=yearbook,research_margin=research_margin)
    official=publications_from_facts(facts.values(),days)
    research=publications_from_facts(facts.values(),days,research=True)
    official_map={(f.source,str(f.statistic_date)):f for f in official.source_facts}
    initial_failures=json.loads((seed/'FAILURES.json').read_bytes())
    coverage=[]
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
    research_overlap=[]
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
    summaries={source:dict(expected=len(days),seed_readable=sum(r['seed_readable']for r in coverage if r['source']==source),
        readable=sum(r['readable']for r in coverage if r['source']==source),research_only=sum(r['research_readable']for r in coverage if r['source']==source),
        missing=[r['statistic_date']for r in coverage if r['source']==source and not r['readable']],
        tail=max((r['statistic_date']for r in coverage if r['source']==source and r['readable']),default=None))for source in SOURCES}
    report=dict(schema='guanheng.auxiliary-history-audit.v1',observed_at=datetime.now(timezone.utc).isoformat(),
        window_sha256=hashlib.sha256(Path(window_path).read_bytes()).hexdigest(),window_rows=len(rows),days=len(days),date_range=[days[0],days[-1]],symbols=symbols,
        sources=summaries,official_complete_days=sum(all((s,d)in official_map for s in SOURCES)for d in days),
        research_overlap=research_overlap,
        official_derived=official_derived,research_derived=research_derived,
        source_qualification_counts=dict(Counter(f.qualification for f in facts.values())),
        actual_historical_merge_changed_rows=sum(a!=b for a,b in zip(original,merged)),
        historical_merge_basis='actually received; no historical first visibility assumption',
        seed_files=len(before),seed_unchanged=before=={str(p.relative_to(seed)):hashlib.sha256(p.read_bytes()).hexdigest()for p in seed.rglob('*')if p.is_file()},
        production_adopted=False,source_policy='official-only default; research candidates never silently enter official bundle')
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
