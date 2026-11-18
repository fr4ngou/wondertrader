"""沪深回购发行人原公告的保守解析与按计划累计金额差分。"""

from bisect import bisect_left
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
import re
import unicodedata

from .market_supplement_sources import SourceUnavailable

DIRECTORY = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
REFERER = 'https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'
ATTACHMENTS = 'https://static.cninfo.com.cn/'
EXECUTION_TITLE = re.compile(r'首次回购|回购.{0,20}(?:进展|实施结果|完成|期限届满)')
NON_MARKET_TITLE = re.compile(
    r'限制性股票|股票期权|专项贷款|债权人|前十[大名]|回购(?:A股|公司|的)?(?:股份)?注销'
    r'|(?:出售|减持)(?:已)?回购股份|(?:已)?回购股份(?:集中竞价)?(?:出售|减持)|合作方回购[^。]{0,60}权益')
NOTICE_NUMBER = r'\d{4}-?\d{2,4}'
# 发行人页眉可省略简称，编号年份可带括号。紧邻其他数字说明编号边界未核。
WRAPPED_NOTICE_NUMBER = r'(?:\(\d{4}\)|〔\d{4}〕)\d{2,4}'
NOTICE_HEADER = re.compile(
    rf'(?:证券|股票)代码:(\d{{6}})(?:(?:证券|股票)简称:[^:]{{1,32}}?)?'
    rf'公告(?:编号|编码):?(?:临)?({NOTICE_NUMBER}|{WRAPPED_NOTICE_NUMBER})(?![\d-])号?')
HEADER_SECURITY = re.compile(r'(?:证券|股票|[ABH]股)代码:(\d{5,6})(?!\d)')
PLAN_REFERENCE = re.compile(rf'《([^《》]{{0,140}}?回购[^《》]{{0,90}})》\((?:公告编号:?)?(?:临)?({NOTICE_NUMBER})\)')
PLAN_TITLE = re.compile(r'回购.{0,30}(?:方案|预案)(?:的公告)?(?:暨回购(?:股份)?报告书)?$')
REPORT_TITLE = re.compile(r'(?:关于)?(回购(?:股份)?报告书)(?:的?公告)?$')
NUMBERED_REFERENCES = re.compile(
    rf'((?:《[^《》]{{1,140}}》){{2,8}})\(公告编号:((?:临?{NOTICE_NUMBER}[、,]){{1,7}}临?{NOTICE_NUMBER})\)')
PROPOSAL_DATE = re.compile(r'(20\d{2})[年/](\d{1,2})[月/](\d{1,2})日?')
PHASED_PLAN = re.compile(r'((?:20\d{2}年)?第[一二三四五六七八九十\d]+[期次])(?:股份回购|回购(?:公司)?股份)方案')
DISCLOSURE_DATE = re.compile(r'详见公司(?:于)?(20\d{2}年\d{1,2}月\d{1,2}日)在')
SOURCE_CLAUSE = re.compile(r'详见公司(?:分别)?于([^。;；]{1,420})$')
BOARD_APPROVAL = re.compile(
    r'(20\d{2})年(\d{1,2})月(\d{1,2})日[^。;；]{0,100}?召开[^。;；]{0,60}?董事会'
    r'[^。;；]{0,60}?审议(?:并)?通过(?:了)?《(关于[^《》]{0,50}?回购[^《》]{0,40}?方案)的议案》')
EXECUTION_SECTION = re.compile(r'一、(?:股份回购|回购股份|回购)(?:的)?(?:实施情况|进展情况|进展)')
MONEY = r'(?:为|:)?(?:人民币)?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(\.[0-9]{1,6})?([万亿])?元'
ACTUAL_AMOUNT = re.compile(r'(?:支付(?:的)?(?:资金总额|总金额)|(?:累计)?成交总?金额|使用资金总额)' + MONEY)
DATED_EXECUTION_AMOUNT = re.compile(
    r'(?<!拟)(?<!计划)(?<!预计)(?:回购总金额|资金发生总额|成交金额合计|已回购金额|支付的金额)' + MONEY)
RESULT_SUMMARY_AMOUNT = re.compile(r'实际回购金额' + MONEY)
FEE_BASIS = re.compile(r'\((不?含)(?:相关)?(?:交易费用|手续费|费用)')
AMOUNT_BASES = ('excludes_fees', 'unspecified', 'includes_fees')
DATED_REPURCHASE = re.compile(
    r'(?:截至?|本次首次回购至|实际回购期间为20\d{2}年\d{1,2}月\d{1,2}日至)'
    r'(20\d{2})[年/](\d{1,2})[月/](\d{1,2})日?[,，:]([^。]{1,360})')
COMBINED_PLANS = re.compile(r'本次(?:和|及|与)前次[^。]{0,80}?回购')
ZERO_EXECUTION = re.compile(
    r'(?:尚未|暂未)(?:开始)?(?:实施(?:本次)?(?:股份)?回购|股份回购|回购(?:公司)?股份)|未发生股份回购行为')
BEFORE_EXECUTION = re.compile(r'尚未进入回购实施期,未发生股份回购行为')
HEADER_BOILERPLATE = re.compile(
    r'本公司及董事会全体成员保证信息披露的内容真实、准确、完整,没有虚假记载、误导性陈述或重大遗漏。')


def announcement_directory(first, last, post, *, stock='', include_proposals=False):
    """核完整公告索引和附件身份，返回沪深市场回购执行候选。"""
    seen, candidates, parents = set(), [], []
    expected = None
    for page in range(1, 31):
        form = dict(pageNum=str(page), pageSize='30', column='sse', tabName='fulltext', stock=stock,
                    searchkey='回购', seDate=f'{first}~{last}', isHLtitle='false')
        receipt = post(DIRECTORY, form, REFERER)
        parents.append((receipt['sha256'],receipt['received_at']))
        try:
            raw = json.loads(receipt['body'])
        except (UnicodeError, ValueError) as error:
            raise SourceUnavailable('buyback_directory_schema') from error
        if type(raw) is not dict:
            raise SourceUnavailable('buyback_directory_schema')
        items, count = raw.get('announcements'), raw.get('totalAnnouncement')
        if items is None and count == 0:
            items = []
        if (type(count) is not int or not 0 <= count <= 900 or type(items) is not list
                or len(items) != min(30,count-(page-1)*30) or type(raw.get('hasMore')) is not bool
                or raw['hasMore'] != (page*30<count) or (expected is not None and expected != count)):
            raise SourceUnavailable('buyback_directory_pagination')
        expected = count
        for item in items:
            if type(item) is not dict or type(item.get('announcementId')) is not str:
                raise SourceUnavailable('buyback_directory_identity')
            identity = item['announcementId']
            if identity in seen:
                raise SourceUnavailable('buyback_directory_duplicate')
            seen.add(identity)
            code, title = item.get('secCode'), item.get('announcementTitle')
            if type(code) is not str or type(title) is not str:
                raise SourceUnavailable('buyback_directory_identity')
            proposal = include_proposals and _proposal_kind(title)
            if (not re.fullmatch(r'(?:00|30|60|68)\d{4}',code)
                    or (not proposal and (not EXECUTION_TITLE.search(title) or NON_MARKET_TITLE.search(title)))):
                continue
            path = item.get('adjunctUrl')
            match = re.fullmatch(r'finalpage/(\d{4}-\d{2}-\d{2})/([0-9]{5,24})\.[pP][dD][fF]',path) if type(path) is str else None
            org = item.get('orgId')
            if (match is None or match[2] != identity or not first <= match[1] <= last
                    or type(org) is not str or re.fullmatch(r'[A-Za-z0-9]{1,32}',org) is None):
                raise SourceUnavailable('buyback_attachment_identity')
            candidates.append(dict(
                symbol=('SSE.' if code.startswith('6') else 'SZSE.')+code,  # 沪深证券。
                notice_date=match[1],  # 巨潮披露日期。
                url=ATTACHMENTS+path,  # 固定巨潮附件地址。
                stock=code+','+org,  # 巨潮证券与机构组合身份，用于查前序。
                title=title,  # 原索引标题，用于核对缺公告编号的方案引用。
            ))
        if not raw['hasMore']:
            return candidates, parents
    raise SourceUnavailable('buyback_directory_pagination')


def execution_directory(first,last,post,*,stock=''):
    return announcement_directory(first,last,post,stock=stock)


def _pdf_text(raw):
    """从有界发行人 PDF 原件提取标准化文本。"""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not raw.startswith(b'%PDF-') or len(raw) > 2 * 1024 * 1024:
        raise SourceUnavailable('buyback_pdf_invalid')
    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        if not 1 <= len(reader.pages) <= 30:
            raise SourceUnavailable('buyback_pdf_invalid')
        return re.sub(r'\s+', '', unicodedata.normalize('NFKC', ''.join(p.extract_text() for p in reader.pages)))
    except (PdfReadError, ValueError, OSError, RecursionError) as error:
        raise SourceUnavailable('buyback_pdf_invalid') from error


def _header(body, symbol):
    """核对首页的单一证券代码，返回正文起点和发行人公告编号。"""
    front = body[:220]
    header = NOTICE_HEADER.search(front)
    security = re.fullmatch(r'(?:SSE\.(?:60|68)|SZSE\.(?:00|30))\d{4}', symbol)
    if (header is None or security is None
            or set(HEADER_SECURITY.findall(front)) != {symbol.split('.')[1]}):
        raise SourceUnavailable('buyback_security_mismatch')
    notice_id = header[2]
    if notice_id[0] in '(〔':
        notice_id = f'{notice_id[1:5]}-{notice_id[6:]}'
    return header.end(), notice_id


def _notice_key(notice_id):
    """编号分隔符仅是展示格式，年份、序号和前导零共同确定身份。"""
    return notice_id.replace('-', '', 1)


def _distinct_notices(notice_ids):
    return {_notice_key(notice): notice for notice in sorted(notice_ids)}


def _proposal_kind(title):
    if '议案' in title:
        return None
    if PLAN_TITLE.search(title):
        return 'proposal'
    if REPORT_TITLE.search(title):
        return 'report'
    return None


def _proposal_title_key(title):
    title = re.sub(r'\s+', '', unicodedata.normalize('NFKC', title))
    report = REPORT_TITLE.search(title)
    if report and _proposal_kind(title) == 'report':
        return report[1]
    # 公告索引、正文引用和 PDF 标题可能各用证券简称或公司全称。
    return title[title.index('关于'):] if '关于' in title else title


def _numbered_references(text):
    references = PLAN_REFERENCE.findall(text)
    # 只有并列标题与编号逐一对应时，才把其中的方案和报告书关联到同一引用。
    for titles, numbers in NUMBERED_REFERENCES.findall(text):
        titles = re.findall(r'《([^《》]+)》', titles)
        numbers = re.findall(NOTICE_NUMBER, numbers)
        if len(titles) == len(numbers):
            references.extend(zip(titles, numbers))
    return references


def _plan_report_pairs(text):
    """只采用同一语句内唯一方案和唯一报告书的并列引用。"""
    pairs = set()
    for sentence in re.split(r'[。；;]', text):
        references = _numbered_references(sentence)
        plans = _distinct_notices(number for title, number in references if _proposal_kind(title) == 'proposal')
        reports = _distinct_notices(number for title, number in references if _proposal_kind(title) == 'report')
        if len(plans) == len(reports) == 1:
            plan_key, plan = next(iter(plans.items()))
            report_key, report = next(iter(reports.items()))
            if plan_key != report_key:
                pairs.add((plan, report))
    return pairs


def _proposal_references(text):
    """识别正文中明确引用的方案标题，日期仅用于缩窄发行人原索引。"""
    result = []
    cited_dates = ()
    last_end = 0
    for match in re.finditer(r'《([^《》]{1,140})》',text):
        title = match[1]
        lead = text[max(last_end,match.start()-500):match.start()]
        last_end = match.end()
        if _proposal_kind(title) is None:
            continue
        # 引用的报纸刊名也带书名号。用同句的披露日期贯穿刊名和公告标题。
        disclosure = SOURCE_CLAUSE.search(text[max(0,match.start()-480):match.start()])
        if disclosure:
            lead = disclosure[1]
        try:
            dates = [date(int(y),int(m),int(d)).isoformat() for y,m,d in PROPOSAL_DATE.findall(lead)]
        except ValueError as error:
            raise SourceUnavailable('buyback_proposal_date_invalid') from error
        if dates:
            cited_dates = tuple(sorted(set(dates)))
        elif '同日' in lead:
            preceding = text[max(0,match.start()-450):match.start()]
            matches = PROPOSAL_DATE.findall(preceding)
            if matches:
                try:
                    cited_dates = (date(*map(int,matches[-1])).isoformat(),)
                except ValueError as error:
                    raise SourceUnavailable('buyback_proposal_date_invalid') from error
        result.append((title,cited_dates))
    if not result:
        phases = {match[0] for match in PHASED_PLAN.finditer(text[:700])}
        disclosures = {match[1] for match in DISCLOSURE_DATE.finditer(text[:1200])}
        if len(phases) == len(disclosures) == 1:
            match = PROPOSAL_DATE.fullmatch(disclosures.pop())
            try:
                result.append((phases.pop(), (date(*map(int,match.groups())).isoformat(),)))
            except ValueError as error:
                raise SourceUnavailable('buyback_proposal_date_invalid') from error
    if not any(_proposal_kind(title) == 'proposal' for title, _ in result):
        preface = EXECUTION_SECTION.split(text[:1200], maxsplit=1)[0]
        approvals = {match.groups() for match in BOARD_APPROVAL.finditer(preface)}
        if len(approvals) == 1:
            year, month, day, title = approvals.pop()
            try:
                approved_on = date(int(year), int(month), int(day)).isoformat()
            except ValueError as error:
                raise SourceUnavailable('buyback_proposal_date_invalid') from error
            # 议案日期仅用于查原方案，仍由同证券的索引及 PDF 标题核对公告号。
            result.append((title + '的公告', (approved_on,)))
    return list(dict.fromkeys(result))


def _execution_amounts(text, notice_date, *, first_execution=False):
    """优先使用按明确截止日披露的执行金额，保留同一截止日的冲突。"""
    text = HEADER_BOILERPLATE.sub('', text)
    # 同一截止日可同时报告本方案和多方案合计，合计不进入单方案差分。
    text = DATED_REPURCHASE.sub(
        lambda match: '' if COMBINED_PLANS.search(match[4]) else match[0], text)

    def amounts(section, pattern=ACTUAL_AMOUNT):
        values = set()
        for match in pattern.finditer(section):
            fees = FEE_BASIS.match(section, match.end())
            basis = ('excludes_fees' if fees[1] == '不含' else 'includes_fees') if fees else 'unspecified'
            integral, fraction, multiplier = match.groups()
            value = Decimal(integral.replace(',', '')+(fraction or '')) * {None: 1, '万': 10_000, '亿': 100_000_000}[multiplier]
            if value*100 == (value*100).to_integral_value():
                values.add((value, basis))
        return values

    def preferred(values):
        if not values:
            return set(), 'unspecified'
        basis = min((basis for _, basis in values), key=AMOUNT_BASES.index)
        return {value for value, kind in values if kind == basis}, basis

    dated = {}
    for match in DATED_REPURCHASE.finditer(text):
        section = match[4]
        if '回购' not in section:
            continue
        values = amounts(section)
        # 两种金额表述同时用于执行期间和计划说明，只在定日执行段核算。
        committed = re.search(r'回购(?:公司)?股份(?:数量)?(?:为)?[0-9,]+(?:\.[0-9]+)?万?股', section)
        if committed:
            values.update(amounts(section[committed.end():], DATED_EXECUTION_AMOUNT))
        if ZERO_EXECUTION.search(section):
            values.add((Decimal(0), 'unspecified'))
        if values:
            try:
                cutoff = date(*map(int, match.groups()[:3]))
            except ValueError as error:
                raise SourceUnavailable('buyback_execution_value_invalid') from error
            if cutoff.isoformat() > notice_date:
                raise SourceUnavailable('buyback_execution_value_invalid')
            dated.setdefault(cutoff, set()).update(values)
    if dated:
        latest, basis = preferred(dated[max(dated)])
        if not first_execution or latest != {Decimal(0)}:
            return latest, basis
        # 首次执行暨月报可同时披露上月底零回购和本月首笔成交。
    # 公告结果表可能四舍五入，正文无实付额时才采用表内实际金额。
    paid = amounts(text) or amounts(text, RESULT_SUMMARY_AMOUNT)
    if not paid and BEFORE_EXECUTION.search(text):
        return {Decimal(0)}, 'unspecified'
    return preferred(paid)


def parse_execution(raw, symbol, notice_date, *, resolve_plan=None):
    """从唯一明确的原计划引用和实付金额提取带原件身份的执行记录。"""
    try:
        if date.fromisoformat(notice_date).isoformat() != notice_date:
            raise ValueError('noncanonical notice date')
    except (TypeError, ValueError) as error:
        raise SourceUnavailable('buyback_execution_value_invalid') from error
    body = _pdf_text(raw)
    heading_end, notice_id = _header(body, symbol)
    text = body[heading_end:]
    front = text.split('公告', 1)[0]
    if not EXECUTION_TITLE.search(front):
        raise SourceUnavailable('buyback_execution_title_unqualified')
    references = _numbered_references(text)
    plans = _distinct_notices(number for title, number in references if _proposal_kind(title) == 'proposal')
    if not plans:
        plans = _distinct_notices(number for title, number in references if _proposal_kind(title) == 'report')
    first_execution = '首次回购' in front
    amounts, basis = _execution_amounts(text, notice_date, first_execution=first_execution)
    if len(amounts) != 1 or len(plans) > 1:
        raise SourceUnavailable('buyback_execution_ambiguous')
    if not plans and resolve_plan is not None:
        plans = _distinct_notices(resolve_plan(_proposal_references(text)))
    if len(plans) != 1:
        raise SourceUnavailable('buyback_plan_reference_missing' if not plans else 'buyback_execution_ambiguous')
    amount = amounts.pop()
    if (len(amount.as_tuple().digits) > 24 or _notice_key(notice_id) in plans
            or amount == 0 and first_execution):
        raise SourceUnavailable('buyback_execution_value_invalid')
    plan_key, plan_id = next(iter(plans.items()))
    return dict(
        symbol=symbol,  # WT 沪深证券标识。
        plan_id=plan_id,  # 原方案公告编号，仅引用报告书时为报告书编号。
        plan_reports=tuple(sorted(report for plan, report in _plan_report_pairs(text)
                                  if _notice_key(plan) == plan_key and _notice_key(report) != _notice_key(notice_id))),  # 原件中与本方案并列的报告书编号。
        notice_id=notice_id,  # 当前执行进展公告编号。
        notice_date=notice_date,  # 公告索引的原披露日期。
        first_execution=first_execution,  # 标题明确为首次执行，不从最早样本猜测。
        cumulative_cny=amount,  # 本次披露的累计实际支付金额，元。
        amount_basis=basis,  # 当前金额含费、不含费或公告未说明。
        source_sha256=sha256(raw).hexdigest(),  # 发行人原 PDF 摘要。
    )


def disclosure_increments(rows):
    """按同计划差分；部分计划缺前序与回落明确保留原因。"""
    rows = list(rows)
    aliases = {}
    proposals = set()
    for row in rows:
        for report in row.get('plan_reports', ()):
            plan = _notice_key(row['plan_id'])
            proposals.add((row['symbol'], plan))
            aliases.setdefault((row['symbol'], _notice_key(report)), set()).add(plan)
    conflicts = {key for key, plans in aliases.items() if len(plans) > 1 or key in proposals}
    conflicts.update((symbol, plan) for (symbol, report) in conflicts.copy()
                     for plan in aliases[(symbol, report)])

    def plan_key(row):
        key = row['symbol'], _notice_key(row['plan_id'])
        return (row['symbol'], next(iter(aliases[key]))) if key in aliases and key not in conflicts else key

    result, previous, notices, invalid = [], {}, set(), set()
    for row in sorted(rows, key=lambda row: (row['notice_date'], *plan_key(row),
                                             not row['first_execution'], _notice_key(row['notice_id']))):
        key = plan_key(row)
        notice = row['symbol'], _notice_key(row['notice_id'])
        before = previous.get(key)
        if notice in notices:
            raise SourceUnavailable('buyback_notice_order_ambiguous')
        notices.add(notice)
        amount = row['cumulative_cny']
        # 首次公告和同日进展可披露同一累计值，第二份只提供来源证明。
        if before is not None and row['notice_date'] == before['notice_date']:
            if amount != before['cumulative_cny'] or row['first_execution']:
                raise SourceUnavailable('buyback_notice_order_ambiguous')
            continue
        reason = None
        if key in conflicts or key in invalid:
            reason = 'buyback_plan_sequence_conflict'
        elif before is None and not row['first_execution'] and amount != 0:
            reason = 'buyback_plan_baseline_missing'
        elif before is not None and ((row['first_execution'] and before['cumulative_cny'] != 0)
                                     or amount < before['cumulative_cny']):
            reason = 'buyback_plan_sequence_conflict'
            invalid.add(key)
        result.append(dict(row, increment_cny=None if reason else amount-(before['cumulative_cny'] if before else 0),
                           prior_amount_basis=before.get('amount_basis') if before else None,
                           prior_source_sha256=before.get('source_sha256') if before else None, gap=reason))
        previous[key] = row
    return result


def disclosure_window(days, calendar, get, post):
    """核查一组交易日的当期与前序披露，返回逐日金额、缺口和原件引用。"""
    position = bisect_left(calendar, days[0])
    if position == 0:
        raise SourceUnavailable('buyback_calendar_unavailable')
    first = (date.fromisoformat(calendar[position-1])+timedelta(days=1)).isoformat()
    candidates, parents = execution_directory(first,days[-1],post)
    values = {day:dict(amount=Decimal(0),gap=None) for day in days}  # 按交易日的金额和缺口。
    results, stock_by_symbol, uncertain = [], {}, {}
    seen = set()

    def resolve(candidate, references):
        directories = {}

        def matches(title, dates):
            plan_ids = set()
            phase = PHASED_PLAN.fullmatch(title)
            kind = 'proposal' if phase else _proposal_kind(title)
            key = _proposal_title_key(title)
            for day in sorted(set(dates)):
                if day > candidate['notice_date']:
                    continue
                if day not in directories:
                    proposals, receipts = announcement_directory(day,day,post,stock=candidate['stock'],include_proposals=True)
                    parents.extend(receipts)
                    directories[day] = proposals
                for proposal in directories[day]:
                    if proposal['symbol'] != candidate['symbol'] or _proposal_kind(proposal['title']) != kind:
                        continue
                    if not phase and _proposal_title_key(proposal['title']) != key:
                        continue
                    receipt = get(proposal['url'],{},None)
                    parents.append((receipt['sha256'],receipt['received_at']))
                    body = _pdf_text(receipt['body'])
                    heading_end, notice_id = _header(body, candidate['symbol'])
                    heading = body[heading_end:heading_end+240].split('保证',1)[0]
                    if phase and phase[1] not in {match[1] for match in PHASED_PLAN.finditer(body[:2200])}:
                        continue
                    if not phase and key not in heading:
                        raise SourceUnavailable('buyback_proposal_title_mismatch')
                    plan_ids.add(notice_id)
            return plan_ids

        for is_report in (False, True):
            plan_ids = set()
            for title, possible_dates in references:
                if (_proposal_kind(title) == 'report') != is_report:
                    continue
                exact = matches(title, possible_dates)
                # 深市发行人使用正文日期，平台附件有时编入下一日。
                following = ((date.fromisoformat(day)+timedelta(days=1)).isoformat() for day in possible_dates)
                plan_ids.update(exact or matches(title, following))
            if plan_ids:
                return plan_ids
        return set()

    def collect(candidate):
        url = candidate['url']
        if url in seen:
            return
        seen.add(url)
        receipt = get(url,{},None)
        parents.append((receipt['sha256'],receipt['received_at']))
        try:
            row = parse_execution(receipt['body'],candidate['symbol'],candidate['notice_date'],
                                  resolve_plan=lambda references:resolve(candidate,references))
        except SourceUnavailable as error:
            uncertain[candidate['symbol'],candidate['notice_date']] = error.code
            return
        results.append(row)
        stock_by_symbol[row['symbol']] = candidate['stock']

    for candidate in candidates:
        collect(candidate)
    # 缺当前区间之前的基线时，按同一原公告身份追查较早的相邻执行披露。
    previous_first = (date.fromisoformat(first)-timedelta(days=90)).isoformat()
    previous_last = (date.fromisoformat(first)-timedelta(days=1)).isoformat()
    previous_symbols = {row['symbol'] for row in disclosure_increments(results)
                        if row['gap']=='buyback_plan_baseline_missing'}
    for symbol in sorted(previous_symbols):
        earlier, receipts = execution_directory(previous_first,previous_last,post,stock=stock_by_symbol[symbol])
        parents.extend(receipts)
        for candidate in earlier:
            if candidate['symbol'] != symbol:
                raise SourceUnavailable('buyback_attachment_identity')
            collect(candidate)

    def selected_session(day):
        return calendar[bisect_left(calendar,day)] if day >= first else None

    for (symbol,notice), reason in sorted(uncertain.items()):
        session = selected_session(notice)
        if session in values:
            values[session]['gap'] = reason
    for row in disclosure_increments(results):
        session = selected_session(row['notice_date'])
        if session not in values:
            continue
        affected = any(symbol==row['symbol'] and notice<=row['notice_date'] for symbol,notice in uncertain)
        if row['gap'] or affected:
            values[session]['gap'] = values[session]['gap'] or row['gap'] or 'buyback_execution_ambiguous'
        else:
            values[session]['amount'] += row['increment_cny']
            if 'includes_fees' in (row.get('amount_basis'), row.get('prior_amount_basis')):
                notes = values[session].setdefault('fee_basis_notes', [])
                notes.append(dict(
                    symbol=row['symbol'],  # 含费披露对应的证券。
                    source_sha256=row['source_sha256'],  # 本期公告原件。
                    amount_basis=row['amount_basis'],  # 本期累计金额的费用口径。
                    prior_source_sha256=row['prior_source_sha256'],  # 前序公告原件，首笔为空。
                    prior_amount_basis=row['prior_amount_basis'],  # 前序累计金额的费用口径。
                    increment_cny=str(row['increment_cny']),  # 本次纳入日汇总的增量，元。
                ))
    return values, list(dict.fromkeys(parents))
