from decimal import Decimal
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pypdf
import pytest

from integrations.guanheng.market_buyback_disclosures import (
    disclosure_increments, disclosure_window, execution_directory, parse_execution, SourceUnavailable,
)


def test_buyback_parse_and_difference_requires_plan_identity(monkeypatch):
    header = '证券代码：688625 证券简称：呈和科技 公告编号：2026-043 '
    proposal = '《关于以集中竞价交易方式回购股份的方案》（公告编号：2026-036）'
    text = header+'关于以集中竞价交易方式回购股份的进展公告 本公司董事会 '+proposal+'支付的资金总额为人民币48,226,931.38元。'
    monkeypatch.setattr(pypdf,'PdfReader',lambda *args, **kw:SimpleNamespace(
        pages=[SimpleNamespace(extract_text=lambda:text)]))
    second = parse_execution(b'%PDF-fixture','SSE.688625','2026-08-04')
    assert second['plan_id']=='2026-036' and second['cumulative_cny']==Decimal('48226931.38')
    third = dict(second, notice_date='2026-09-02', notice_id='2026-049', cumulative_cny=Decimal('96890613.58'))
    rows = disclosure_increments([third,second])
    assert rows[0]['gap']=='buyback_plan_baseline_missing'
    assert rows[1]['increment_cny']==Decimal('48663682.20')
    conflict = dict(third,cumulative_cny=Decimal('200'))
    assert disclosure_increments([second,conflict])[1]['gap']=='buyback_plan_sequence_conflict'
    with pytest.raises(SourceUnavailable,match='buyback_notice_order_ambiguous'):
        disclosure_increments([second,dict(third,notice_date=second['notice_date'])])
    text += proposal.replace('2026-036','2026-037')
    with pytest.raises(SourceUnavailable,match='buyback_execution_ambiguous'):
        parse_execution(b'%PDF-fixture','SSE.688625','2026-08-04')


def test_same_day_first_and_progress_disclosures_do_not_double_count():
    plan = dict(symbol='SZSE.002230', plan_id='2026-039')
    first = dict(plan, notice_date='2026-09-01', notice_id='2026-045', first_execution=True,
                 cumulative_cny=Decimal('30021592'))
    progress = dict(first, notice_id='2026-046', first_execution=False)
    later = dict(progress, notice_date='2026-11-05', notice_id='2026-060',
                 cumulative_cny=Decimal('40021592'))

    rows = disclosure_increments([progress, later, first])
    assert [row['increment_cny'] for row in rows] == [Decimal('30021592'), Decimal('10000000')]
    with pytest.raises(SourceUnavailable, match='buyback_notice_order_ambiguous'):
        disclosure_increments([first, dict(progress, cumulative_cny=Decimal('30021593'))])


def test_cninfo_directory_uses_actual_page_length_and_unique_ids():
    day = '2026-11-13'

    def post(_url,form,_referer):
        assert form['pageSize']=='30'
        page = int(form['pageNum'])
        items = [dict(announcementId=str(i),secCode='688625',orgId='example',
                      announcementTitle='关于股份回购进展的公告',adjunctUrl=f'finalpage/{day}/{i}.PDF')
                 for i in range(12000,12030) if page==1]
        if page==2:
            items.append(dict(announcementId='12030',secCode='688625',announcementTitle='关于回购专项贷款的公告'))
        return dict(body=json.dumps(dict(announcements=items,totalAnnouncement=31,totalpages=1,hasMore=page==1)),
                    sha256=str(page),received_at=day)

    candidates, parents = execution_directory(day,day,post)
    assert len(candidates)==30 and len(parents)==2
    assert candidates[0]['symbol']=='SSE.688625'


def test_buyback_dated_cumulative_payment_and_explicit_zero(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    header = '关于回购股份的进展公告证券代码:600382证券简称:样本公司公告编号:临2026-058'
    proposal = '《关于以集中竞价交易方式回购股份的方案》(公告编号:2026-036)。'
    zero = header+'关于回购股份的进展公告'+proposal+'截至2026年7月31日,公司尚未实施股份回购。'
    progress = (header.replace('058', '060')+'关于回购股份的进展公告'+proposal
                +'2026年8月,公司回购股份,支付总金额为53,259,846.28元。'
                +'截至2026年8月31日,公司累计回购股份,已支付的总金额为65,216,277.12元。')
    texts = {b'zero':zero, b'progress':progress,
             b'conflict':progress+'截至2026年8月31日,公司累计回购股份,支付总金额为12元。'}
    monkeypatch.setattr(buybacks, '_pdf_text', texts.__getitem__)

    before = parse_execution(b'zero', 'SSE.600382', '2026-08-03')
    after = parse_execution(b'progress', 'SSE.600382', '2026-09-02')
    assert before['cumulative_cny'] == 0
    assert after['cumulative_cny'] == Decimal('65216277.12')
    first = dict(after, notice_date='2026-08-11', notice_id='2026-059', first_execution=True,
                 cumulative_cny=Decimal('12000000'))
    assert [row['increment_cny'] for row in disclosure_increments([before, first, after])] == [
        Decimal(0), Decimal('12000000'), Decimal('53216277.12')]
    with pytest.raises(SourceUnavailable, match='buyback_execution_ambiguous'):
        parse_execution(b'conflict', 'SSE.600382', '2026-09-02')


def test_completed_buyback_prefers_full_period_amount_excluding_fees(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    text = ('证券代码:603979证券简称:样本公告编号:2026-091关于股份回购实施结果的公告'
            '实际回购金额39,988.01万元。'
            '《关于回购公司股份的方案》(公告编号:2026-086)。'
            '2026年10月27日,首次回购股份,支付的资金总额为3,925.023万元。'
            '实际回购期间为2026年10月27日至2026年11月12日,公司累计回购股份,'
            '累计成交金额39,988.01万元(不含交易费用),使用资金总额39,999.85万元(含交易费用)。')
    monkeypatch.setattr(buybacks, '_pdf_text', lambda raw: text)
    row = parse_execution(b'issuer', 'SSE.603979', '2026-11-13')
    assert row['cumulative_cny'] == Decimal('399880100')
    assert not row['first_execution']


def test_including_fees_only_reports_missing_net_execution_amount(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    text = ('证券代码:301656证券简称:样本公告编号:2026-055关于首次回购公司股份的公告'
            '《关于回购公司股份方案的公告》(公告编号:2026-048)。'
            '2026年11月10日,公司首次回购公司股份389,800股,'
            '已使用资金总额为人民币5,308,047.97元(含交易费用)。')
    monkeypatch.setattr(buybacks, '_pdf_text', lambda raw: text)
    with pytest.raises(SourceUnavailable, match='buyback_execution_net_amount_missing'):
        parse_execution(b'issuer', 'SZSE.301656', '2026-11-11')


def test_issuer_citation_dates_survive_newspaper_titles(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    proposal = '关于2026年第二次以集中竞价交易方式回购公司股份方案的公告'
    report = '回购股份报告书'
    text = ('证券代码:002633证券简称:样本公告编号:2026-064关于回购实施结果的公告'
            '详见公司于2026年9月23日、2026年10月15日刊登在《证券时报》《证券日报》和'
            '巨潮资讯网的《'+proposal+'》《'+report+'》。'
            '截至2026年11月11日,公司累计回购股份,成交总金额39,938,225元。')
    monkeypatch.setattr(buybacks, '_pdf_text', lambda raw: text)

    def resolve(references):
        assert references == [(proposal, ('2026-09-23', '2026-10-15')),
                              (report, ('2026-09-23', '2026-10-15'))]
        return {'2026-050'}

    row = parse_execution(b'issuer', 'SZSE.002633', '2026-11-12', resolve_plan=resolve)
    assert row['plan_id'] == '2026-050' and row['cumulative_cny'] == Decimal('39938225')


def test_buyback_qualifies_no_purchases_before_execution_period(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    text = ('证券代码:000935证券简称:样本公告编号:2026-44关于回购股份的进展公告'
            '《关于回购公司股份的方案》(公告编号:2026-39)。'
            '公司的回购期限为2026年9月1日至11月6日,2026年8月公司尚未进入回购实施期,未发生股份回购行为。')
    monkeypatch.setattr(buybacks, '_pdf_text', lambda raw: text)
    row = parse_execution(b'issuer', 'SZSE.000935', '2026-09-01')
    assert disclosure_increments([row])[0]['increment_cny'] == 0


def test_current_buyback_total_excludes_prior_plans_quoted_in_progress(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    text = ('证券代码:000935证券简称:样本公告编号:2026-57关于股份回购的进展公告'
            '《关于回购公司股份的方案》(公告编号:2026-39)。'
            '本次首次回购至2026年10月31日,公司累计回购股份,成交总金额27,207,224.76元。'
            '前次回购成交总金额88,252,176.26元。两次回购成交总金额115,459,401.02元。')
    monkeypatch.setattr(buybacks, '_pdf_text', lambda raw: text)
    row = parse_execution(b'issuer', 'SZSE.000935', '2026-11-03')
    assert row['cumulative_cny'] == Decimal('27207224.76')


def test_missing_plan_number_requires_matched_proposal_pdf(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    day, proposal_day = '2026-11-13','2026-11-02'
    title = '关于回购公司股份方案的公告'
    stock, symbol = '300657,org','SZSE.300657'
    prefix = '证券代码:300657证券简称:弘信电子公告编号:'
    texts = {
        b'exec':prefix+'2026-124关于首次回购公司股份的公告于2026年11月2日召开董事会。'+'事项说明'*65+'同日披露的《'+title+'》。支付的资金总额为人民币127,766,838.16元。',
        b'proposal':prefix+'2026-120厦门弘信电子科技集团股份有限公司'+title,
    }
    monkeypatch.setattr(buybacks,'_pdf_text',texts.__getitem__)
    current = dict(symbol=symbol,notice_date=day,url='exec',stock=stock)
    proposal = dict(symbol=symbol,notice_date=proposal_day,url='proposal',stock=stock,title='弘信电子'+title)
    monkeypatch.setattr(buybacks,'execution_directory',lambda *args:([current],[('current-index',day)]))

    def directory(first,last,post,**kwargs):
        assert first==last==proposal_day and kwargs==dict(stock=stock,include_proposals=True)
        return [proposal],[('proposal-index',day)]

    monkeypatch.setattr(buybacks,'announcement_directory',directory)
    get = lambda url,params,referer:dict(body=url.encode(),sha256=url,received_at=day)
    result,proofs = disclosure_window([day],['2026-11-12',day],get,None)
    assert result[day] == dict(amount=Decimal('127766838.16'),gap=None)
    assert {sha for sha,_ in proofs} == {'exec','proposal','current-index','proposal-index'}
    proposal['title'] = '关于另一回购方案的公告'
    monkeypatch.setattr(buybacks,'announcement_directory',lambda *args, **kwargs: ([proposal], []))
    result,_ = disclosure_window([day],['2026-11-12',day],get,None)
    assert result[day]['gap']=='buyback_plan_reference_missing'


def test_phased_plan_requires_issuer_pdf_and_can_match_next_publication_day(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    symbol = 'SZSE.300408'
    day = '2026-11-06'
    prefix = '证券代码:300408证券简称:样本公告编号:'
    text = {
        b'execution': prefix+'2026-74关于首次回购公司股份的公告'
        '2026年第四期回购股份方案已实施首次回购,成交总金额为399,884,600.12元。'
        '具体内容详见公司于2026年11月5日在指定网站刊登的公告。',
        b'plan': prefix+'2026-72关于2026年第四期回购公司股份方案的公告暨回购股份报告书'
        '本公司保证披露内容真实。',
    }
    monkeypatch.setattr(buybacks,'_pdf_text',text.__getitem__)
    current = dict(symbol=symbol,notice_date=day,url='execution',stock='300408,org')
    plan = dict(symbol=symbol,notice_date=day,url='plan',stock='300408,org',
                title='关于2026年第四期回购公司股份方案的公告暨回购股份报告书')
    monkeypatch.setattr(buybacks,'execution_directory',lambda *args: ([current], []))
    queries = []
    def directory(first,last,post,**kwargs):
        queries.append(first)
        return [plan] if first == day else [], []
    monkeypatch.setattr(buybacks,'announcement_directory',directory)
    get = lambda url,*args: dict(body=url.encode(),sha256=url,received_at=day)
    result,_ = disclosure_window([day],['2026-11-05',day],get,None)
    assert queries == ['2026-11-05',day]
    assert result[day] == dict(amount=Decimal('399884600.12'),gap=None)
    text[b'plan'] = text[b'plan'].replace('第四期','第三期')
    result,_ = disclosure_window([day],['2026-11-05',day],get,None)
    assert result[day]['gap'] == 'buyback_plan_reference_missing'


def test_buyback_parallel_references_and_standalone_report(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    day = '2026-11-13'
    header = '证券代码:002931证券简称:样本公告编号:2026-093'
    amount = '截至2026年11月6日,公司累计回购股份,支付总金额为32万元。'
    title = '关于公司股份回购的进展公告'
    references = ('《董事会决议公告》《关于回购公司股份方案的公告》《回购报告书》'
                  '(公告编号:2026-070、2026-071、2026-072)。')
    texts = {b'parallel':header+title+references+amount,
             b'report':header+title+'公司于2026年7月28日披露《回购股份报告书》(公告编号:2026-072)。'+amount,
             b'broken':header+title+references.replace('、2026-072', '')+amount}
    monkeypatch.setattr(buybacks, '_pdf_text', texts.__getitem__)
    later = parse_execution(b'parallel', 'SZSE.002931', day)
    assert later['plan_id'] == '2026-071' and later['plan_reports'] == ('2026-072',)
    earlier = parse_execution(b'report', 'SZSE.002931', '2026-11-10')
    assert earlier['plan_id'] == '2026-072' and earlier['plan_reports'] == ()
    earlier = dict(earlier, notice_id='2026-087', cumulative_cny=Decimal('210000'), first_execution=True)
    assert [row['increment_cny'] for row in disclosure_increments([later, earlier])] == [
        Decimal('210000'), Decimal('110000')]
    conflicting = dict(later, notice_date='2026-11-12', notice_id='2026-091', plan_id='2026-070')
    assert all(row['gap'] == 'buyback_plan_sequence_conflict'
               for row in disclosure_increments([later, earlier, conflicting]))
    with pytest.raises(SourceUnavailable, match='buyback_plan_reference_missing'):
        parse_execution(b'broken', 'SZSE.002931', day)


def test_buyback_window_uses_issuer_baseline_and_blocks_unknown_day(monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks

    news = {'today':('688625','2026-11-07'), 'bad':('688624','2026-11-10'), 'prior':('688625','2026-10-30')}

    def candidate(name):
        code,day = news[name]
        return dict(symbol='SSE.'+code,notice_date=day,url=name,stock=code+',org')

    def directory(first,last,post,*,stock=''):
        if stock:
            assert stock=='688625,org' and last=='2026-11-06'
            return [candidate('prior')],[('prior-page',last)]
        assert first=='2026-11-07' and last=='2026-11-11'
        return [candidate('today'),candidate('bad')],[('current-page',last)]

    def parse(raw,symbol,day,**kwargs):
        if raw=='bad':
            raise SourceUnavailable('buyback_execution_ambiguous')
        start = raw=='prior'
        return dict(symbol=symbol,notice_date=day,first_execution=start,notice_id=raw,plan_id='same',
                    cumulative_cny=Decimal('90') if start else Decimal('100'))

    monkeypatch.setattr(buybacks,'execution_directory',directory)
    monkeypatch.setattr(buybacks,'parse_execution',parse)
    calendar=['2026-11-06','2026-11-09','2026-11-10','2026-11-11']
    values,parents = disclosure_window(calendar[1:],calendar,
        lambda url,params,referer:dict(body=url,sha256=url,received_at='2026-11-14'),None)
    assert values=={calendar[1]:dict(amount=10,gap=None),calendar[2]:dict(amount=0,gap='buyback_execution_ambiguous'),
                    calendar[3]:dict(amount=0,gap=None)}
    assert {sha for sha,_ in parents}=={'prior','prior-page','current-page','today','bad'}


def test_wt_buyback_fact_preserves_index_and_pdfs(tmp_path,monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks
    from integrations.guanheng.market_supplement_capture import collect_supplement
    from integrations.guanheng.market_supplement_store import MarketSupplementStore
    from msf_fixture import ContentStore,FrozenFetch,QmtTransport,plan,query

    day = '2026-11-13'
    targets = plan(('buyback_execution_disclosed','CN.SH_SZ'),required=False)
    targets['targets'][0]['from'] = day
    targets['external_fallback'] = ['CNINFO']
    objects = ContentStore(tmp_path/'raw')
    pdfs = [objects.put(b'%PDF-one'),objects.put(b'%PDF-two')]

    def disclosure(*args):
        return {day:dict(amount=Decimal('100'),gap=None)},[(sha,day+'T15:00:00+00:00') for sha in pdfs]

    monkeypatch.setattr(buybacks,'disclosure_window',disclosure)
    descriptor = collect_supplement(targets,day,['2026-11-12',day],tmp_path/'work',objects=objects,
        fetch=FrozenFetch(),qmt_transport=QmtTransport(),calendar_coverage=('2026-11-12',day),deadline=time.monotonic()+20)
    store = MarketSupplementStore(descriptor)
    try:
        args = query(metric='buyback_execution_disclosed',symbols=['CN.SH_SZ'],**{'from':day,'to':day})
        assert store.query(args)['rows'][0]['value']=='100'
        path = objects.root/'objects'/'sha256'/pdfs[0][:2]/pdfs[0]
        assert Path(path).is_file()
        path.unlink()
        with pytest.raises(ValueError,match='object unavailable'):
            store.query(args)
    finally:
        store.close()


@pytest.mark.parametrize('required',[False,True])
def test_buyback_backfill_progresses_past_latest_ambiguous_date(tmp_path,monkeypatch,required):
    from integrations.guanheng import market_buyback_disclosures as buybacks
    from integrations.guanheng.market_supplement_capture import SupplementPending, collect_supplement
    from msf_fixture import ContentStore,FrozenFetch,QmtTransport,plan

    day, older = '2026-11-13','2026-11-12'
    calendar = ['2026-11-11',older,day]
    objects = ContentStore(tmp_path/'raw')
    parent = objects.put(b'captured issuer index')
    targets = plan(('buyback_execution_disclosed','CN.SH_SZ'),required=required)
    targets.update(max_requests=2,external_fallback=['CNINFO'])  # 一个QMT元数据加一个回购来源请求。
    targets['targets'][0]['from'] = older
    visited = []
    budget = None

    def disclosure(days,*args):
        budget.request()
        d, = days
        visited.append(d)
        gap = 'buyback_plan_reference_missing' if d == day else None
        return {d:dict(amount=Decimal('10'),gap=gap)},[(parent,d+'T15:00:00+00:00')]

    monkeypatch.setattr(buybacks,'disclosure_window',disclosure)

    def collect(name,previous=None):
        nonlocal budget
        fetch = FrozenFetch()
        budget = fetch.budget
        return collect_supplement(targets,day,calendar,tmp_path/name,objects=objects,
            fetch=fetch,qmt_transport=QmtTransport(),calendar_coverage=(calendar[0],day),
            deadline=time.monotonic()+20,previous=previous)

    if required:
        with pytest.raises(SupplementPending):
            collect('attempt-1')
        with pytest.raises(SupplementPending):
            collect('attempt-1')
        state = json.loads((tmp_path/'attempt-1'/'STATE.json').read_bytes())
        assert [row['date'] for row in state['rows'].values()]==[older]
    else:
        previous = collect('attempt-1')
        result = json.loads(Path(collect('attempt-2',previous)['path']).read_bytes())
        assert [(row['date'],row['value']) for row in result['rows']]==[(older,'10')]
        assert [(gap['date'],gap['reason']) for gap in result['gaps']]==[(day,'buyback_plan_reference_missing')]
    assert visited == [day,older]


@pytest.mark.parametrize('reason', ['capture_budget_exceeded', 'collection_timeout'])
def test_buyback_backfill_advances_when_latest_day_exhausts_budget(tmp_path, monkeypatch, reason):
    from guanheng_app.observation.source_fetch import SourceFailure
    from integrations.guanheng import market_buyback_disclosures as buybacks
    from integrations.guanheng.market_supplement_capture import collect_supplement
    from msf_fixture import ContentStore, FrozenFetch, QmtTransport, plan

    latest, older = '2026-11-13', '2026-11-12'
    calendar = ['2026-11-11', older, latest]
    objects = ContentStore(tmp_path/'raw')
    parent = objects.put(b'issuer evidence')
    targets = plan(('buyback_execution_disclosed', 'CN.SH_SZ'), required=False)
    targets['external_fallback'] = ['CNINFO']
    targets['targets'][0]['from'] = older
    attempted = []
    budget = None

    def disclosure(days, *args):
        day, = days
        attempted.append(day)
        budget.request()
        if day == latest:
            raise SourceFailure(reason)
        return {day:dict(amount=Decimal('10'), gap=None)}, [(parent, day+'T15:00:00+00:00')]

    monkeypatch.setattr(buybacks, 'disclosure_window', disclosure)

    def collect(name, previous=None):
        nonlocal budget
        fetch = FrozenFetch()
        budget = fetch.budget
        return collect_supplement(targets, latest, calendar, tmp_path/name, objects=objects,
            fetch=fetch, qmt_transport=QmtTransport(), calendar_coverage=(calendar[0], latest),
            deadline=time.monotonic()+20, previous=previous)

    previous = collect('first')
    catalog = json.loads(Path(collect('second', previous)['path']).read_bytes())
    assert attempted == [latest, older, latest]
    assert [row['date'] for row in catalog['rows']] == [older]
    assert catalog['gaps'][0]['reason'] == reason


def test_current_buyback_is_collected_before_etf_history(tmp_path, monkeypatch):
    from integrations.guanheng import market_buyback_disclosures as buybacks
    from integrations.guanheng.market_supplement_capture import collect_supplement
    from msf_fixture import ContentStore, FrozenFetch, QmtTransport, plan

    previous, latest = '2026-11-12', '2026-11-13'
    calendar = ['2026-11-11', previous, latest]
    objects = ContentStore(tmp_path / 'raw')
    parent = objects.put(b'issuer evidence')
    targets = plan(('buyback_execution_disclosed', 'CN.SH_SZ'),
                   ('etf_total_shares', 'SSE.510300'), required=False)
    targets.update(max_requests=3, external_fallback=['CNINFO', 'SSE'])
    for target in targets['targets']:
        target['from'] = previous
    fetch = FrozenFetch()

    def disclosure(days, *args):
        day, = days
        fetch.budget.request()
        return {day: dict(amount=Decimal('10'), gap=None)}, [(parent, day+'T15:00:00+00:00')]

    monkeypatch.setattr(buybacks, 'disclosure_window', disclosure)
    result = collect_supplement(targets, latest, calendar, tmp_path / 'work', objects=objects,
        fetch=fetch, qmt_transport=QmtTransport(), calendar_coverage=(calendar[0], latest),
        deadline=time.monotonic()+20)
    catalog = json.loads(Path(result['path']).read_bytes())
    assert [(row['date'], row['metric']) for row in catalog['rows']] == [
        (latest, 'buyback_execution_disclosed'), (latest, 'etf_total_shares')]
    assert {row['date'] for row in catalog['gaps']} == {previous}
