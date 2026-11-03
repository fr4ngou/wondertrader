"""机构原报告的数字生产；报告期、分母及公布日由各来源独立解释。"""
from calendar import monthrange
from datetime import date
from decimal import Decimal
from html import unescape
from html.parser import HTMLParser
import io
import re
from urllib.parse import urljoin, urlsplit

from .source_fetch import SourceFailure
from .provider_tables import parse_json

PBC_URL = 'https://www.pbc.gov.cn/jinrongshichangsi/147160/147173/index.html'
WEALTH_URL = 'https://www.chinawealth.com.cn/lc_lcsj/lcbg/'
CITIC_URL = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'


class ReportHTML(HTMLParser):
    """公开目录的标题链接和正文；不执行脚本或加载页面依赖。"""
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links = []  # (href, 标题)；只含本次页面字符串，地址后续按官方主机准入。
        self.text = []  # 页面可见文本片段；报告身份与数值由具体解析器核实。
        self.attachments = []  # 官方data-recurl附件地址；不作内容或权限资格推断。
        self._anchor = None  # 正在读取的链接及片段，生命周期限定在feed调用内。
        self._skip = 0  # script/style嵌套深度；其文字不参与报告数值解析。
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self._skip += 1
        if tag == 'a' and attrs.get('href'):
            self._anchor = [attrs['href'], []]
        if attrs.get('data-recurl'):
            self.attachments.append(attrs['data-recurl'])

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._skip = max(0, self._skip - 1)
        if tag == 'a' and self._anchor is not None:
            self.links.append((self._anchor[0], ''.join(self._anchor[1]).strip()))
            self._anchor = None

    def handle_data(self, value):
        if self._skip:
            return
        self.text.append(value)
        if self._anchor is not None:
            self._anchor[1].append(value)


def _html(body):
    try:
        return ReportHTML(body.decode('utf8'))
    except (ValueError, UnicodeError):
        raise SourceFailure('institution_html_schema') from None


def _official(base, link, host, prefix):
    url = urljoin(base, unescape(link))
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != host or not parsed.path.startswith(prefix) or parsed.fragment:
        raise SourceFailure('institution_attachment_identity')
    return url


def _period(year, month):
    try:
        return date(year, month, monthrange(year, month)[1]).isoformat()
    except (ValueError, OverflowError):
        raise SourceFailure('institution_report_period') from None


def _published(text, end):
    values = set(re.findall(r'(?<!\d)(20\d{2}-\d{2}-\d{2})(?:[ T\u00a0]|$)', text))
    if len(values) != 1:
        raise SourceFailure('institution_publication_date')
    value = values.pop()
    try:
        date.fromisoformat(value)
    except ValueError:
        raise SourceFailure('institution_publication_date') from None
    return value if value <= end else None


def pdf_pages(body, budget, *, max_pages, max_bytes):
    """固定字节/页数/文本上限的原PDF读取；每页检查原截止，不执行嵌入对象。"""
    budget.remaining()
    if not body.startswith(b'%PDF-') or len(body) > min(max_bytes, budget.response_bytes):
        raise SourceFailure('institution_pdf_format_or_budget')
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SourceFailure('institution_pdf_dependency_missing') from None
    try:
        with io.BytesIO(body) as stream:
            reader = PdfReader(stream, strict=True)
            try:
                count = reader.root_object['/Pages']['/Count']
                if reader.is_encrypted or not isinstance(count, int) or not 1 <= count <= max_pages:
                    raise SourceFailure('institution_pdf_format_or_budget')
                if sum(len(items) for items in reader.xref.values()) + len(reader.xref_objStm) > 100000:
                    raise SourceFailure('institution_pdf_object_budget')
                pages, size = [], 0
                for page in reader.pages:
                    budget.remaining()
                    text = page.extract_text() or ''
                    budget.remaining()
                    size += len(text.encode('utf8'))
                    if len(pages) >= max_pages or size > 4 * 1024 * 1024:
                        raise SourceFailure('institution_pdf_text_budget')
                    pages.append(text)
                if len(pages) != count:
                    raise SourceFailure('institution_pdf_format_or_budget')
                return pages
            finally:
                reader.close()
    except SourceFailure:
        raise
    except Exception:
        raise SourceFailure('institution_pdf_invalid') from None


def pbc_custody(fetch, config, start, end):
    """月末全市场余额，万亿元；只追加游标之后真实已公布报告，不改旧行。"""
    directory = _html(fetch.get(config['url']))
    reports = {}
    for href, title in directory.links:
        match = re.fullmatch(r'(20\d{2})年(\d{1,2})月(?:份)?金融市场运行情况', title)
        if match:
            period = _period(int(match[1]), int(match[2]))
            url = _official(config['url'], href, 'www.pbc.gov.cn', '/jinrongshichangsi/147160/147173/')
            if period in reports and reports[period] != url:
                raise SourceFailure('custody_duplicate_report')
            reports[period] = url
    if not reports:
        raise SourceFailure('custody_directory_schema')
    rows = []
    for period, url in sorted(reports.items()):
        if not start < period <= end:
            continue
        document = _html(fetch.get(url))
        text = re.sub(r'\s+', '', ''.join(document.text))
        published = _published(' '.join(document.text), end)
        if published is None:
            continue
        if published < period:
            raise SourceFailure('custody_publication_before_period')
        year, month = int(period[:4]), int(period[5:7])
        pattern = rf'{year}年{month}月末[，,]?债券市场托管余额(\d+(?:\.\d+)?)万亿元'
        values = re.findall(pattern, text)
        if len(values) != 1:
            raise SourceFailure('custody_report_schema_or_unit')
        value = Decimal(values[0])
        if not value.is_finite() or not 0 < value < 10000:
            raise SourceFailure('custody_report_value')
        rows.append(dict(
            date=period,  # 人民银行正文所属月末，ISO日期；实际报告期而非抓取日。
            custody=float(value),  # 全市场债券托管余额，万亿元；不含义推为某单一托管机构余额。
            available_at=published))  # 官网公布日期；精度为自然日，沿原字段保留。
        fetch.records[-1]['parsed_document'] = dict(period=period, published=published, unit='CNY_trillion', scope='whole_bond_market')
    return {'bond.custody': rows}


def wealth_pdf(body, period, published, budget):
    """原市场报告债券及存单百分数；金额与分母仅做舍入精度内的交叉核对。"""
    pages = pdf_pages(body, budget, max_pages=100, max_bytes=8*1024*1024)
    text = re.sub(r'\s+', '', ''.join(pages))
    year, month = int(period[:4]), int(period[5:7])
    quarter = month // 3
    period_labels = [f'{year}年{label}季度末' for label in [str(quarter), '一二三四'[quarter-1]]]
    if month == 6:
        period_labels += [f'{year}年6月末', f'{year}年上半年末']
    if month == 12:
        period_labels += [f'{year}年末', f'{year}年12月末']
    if '银行业理财市场' not in text or not any(label in text for label in period_labels):
        raise SourceFailure('wealth_report_identity')
    pattern = (r'投向债券、现金及银行存款、同业存单余额分别为(\d+(?:\.\d+)?)万亿元、(\d+(?:\.\d+)?)万亿元、'
               r'(\d+(?:\.\d+)?)万亿元[，,]分别占总投资资产的(\d+(?:\.\d+)?)%[、,，](\d+(?:\.\d+)?)%[、,，](\d+(?:\.\d+)?)%')
    matches = re.findall(pattern, text)
    if len(matches) != 1:
        raise SourceFailure('wealth_report_schema_or_unit')
    bond, cash, cd, bond_pct, cash_pct, cd_pct = map(Decimal, matches[0])
    total_matches = re.findall(r'理财产品投资资产合计(\d+(?:\.\d+)?)万亿元', text)
    if len(total_matches) != 1:
        raise SourceFailure('wealth_report_denominator')
    total = Decimal(total_matches[0])
    if (any(not v.is_finite() or v < 0 for v in [bond, cash, cd, bond_pct, cash_pct, cd_pct, total])
            or total <= 0 or bond_pct + cash_pct + cd_pct > 100):
        raise SourceFailure('wealth_report_value')
    # 金额以0.01万亿元、比例以0.1个百分点披露；两者舍入独立，不能强制相等。
    if any(abs(amount / total * 100 - pct) > Decimal('0.08') for amount, pct in [(bond,bond_pct),(cash,cash_pct),(cd,cd_pct)]):
        raise SourceFailure('wealth_report_ratio')
    return dict(
        date=period,  # 理财市场报告期末，ISO日期；实际公布日另存available_at。
        direct_pct=float(bond_pct),  # 债券单项占投资资产，百分数；同业存单独立列示。
        cd_pct=float(cd_pct),  # 同业存单占投资资产，百分数；取原文披露值。
        broad_pct=float(bond_pct+cd_pct),  # 两个已舍入分项之和，百分数；不声称正文精确广义比例。
        broad_status='rounded_components_sum',  # 显式标识广义数值来自舍入分项相加。
        available_at=published)  # 官网报告公布日期，日精度；不把PDF元数据当首次可知时刻。


def wealth_allocation(fetch, config, start, end):
    """自动发现后继季度/半年/年度报告；正文变更时失败保旧，不用新闻代替数值。"""
    directory = _html(fetch.get(config['url']))
    reports = {}
    for href, title in directory.links:
        match = re.fullmatch(r'中国银行业理财市场(季度|半年|年度)报告[（(](20\d{2})年(.*?)[）)]', title)
        if not match:
            continue
        kind, year, suffix = match[1], int(match[2]), match[3]
        quarter = {'一季度':3, '二季度':6, '三季度':9, '四季度':12, '上':6, '上半年':6, '':12}.get(suffix)
        if quarter is None or (kind=='半年' and quarter!=6) or (kind=='年度' and quarter!=12):
            raise SourceFailure('wealth_directory_period')
        period = _period(year, quarter)
        url = _official(config['url'], href, 'www.chinawealth.com.cn', '/lc_lcsj/lcbg/')
        if period in reports and reports[period] != url:
            raise SourceFailure('wealth_duplicate_report')
        reports[period] = url
    if not reports:
        raise SourceFailure('wealth_directory_schema')
    rows = []
    for period, url in sorted(reports.items()):
        if not start < period <= end:
            continue
        document = _html(fetch.get(url))
        published = _published(' '.join(document.text), end)
        if published is None:
            continue
        if published < period:
            raise SourceFailure('wealth_publication_before_period')
        attachments = {_official(url, link, 'www.chinawealth.com.cn', '/lc_lcsj/lcbg/') for link in document.attachments if link.lower().endswith('.pdf')}
        if len(attachments) != 1:
            raise SourceFailure('wealth_attachment_schema')
        rows.append(wealth_pdf(fetch.get(attachments.pop()), period, published, fetch.budget))
        fetch.records[-1]['parsed_document'] = dict(period=period,published=published,unit='percent',denominator='investment_assets',broad='rounded_components_sum')
    return {'holdings_wealth': rows}


def citic_pdf(body, year, published, budget, *, annual=False):
    """合并财务附注8的两个日期及公允价值合计列；母公司表与成本列不参与。"""
    pages = pdf_pages(body, budget, max_pages=600, max_bytes=12*1024*1024)
    title = re.sub(r'\s+', '', ''.join(pages[:12]))
    financial_period = f'截至{year}年12月31日止年度财务报表' if annual else f'{year}年1月1日至6月30日止期间财务报表'
    if ('中信证券' not in title or ('年度报告' if annual else '半年度报告') not in title or '600030' not in title
            or not any(financial_period in re.sub(r'\s+', '', page) for page in pages)):
        raise SourceFailure('citic_report_identity')
    if not any(all(label in re.sub(r'\s+','',page) for label in
                   ['合并资产负债表','本集团','金额单位均为人民币元']) for page in pages):
        raise SourceFailure('citic_report_scope_or_unit')
    result = {}
    document='\n'.join(pages)
    sections=list(re.finditer(r'(?m)^[ \t]*8[ \t]+金融投资[：:][ \t]*交易性金融资产.*$',document))
    current_period=_period(year,12 if annual else 6)
    for index,section in enumerate(sections):
        stop=sections[index+1].start() if index+1<len(sections) else len(document)
        block=document[section.end():stop]
        next_note=re.search(r'(?m)^[ \t]*9[ \t]+金融投资[：:]',block)
        if next_note is not None:block=block[:next_note.start()]
        compact=re.sub(r'\s+','',block)
        if '公允价值合计' not in compact or '初始投资成本合计' not in compact:
            continue
        headers = list(re.finditer(r'(20\d{2})\s*年\s*(\d+)\s*月\s*(\d+)\s*日\s+(?:项目\s+)?公允价值\s+初始投资成本',block))
        if not headers:
            raise SourceFailure('citic_table_period_or_columns')
        for header in headers:
            period = date(*map(int,header.groups())).isoformat()
            if period not in [current_period,_period(year-1,12)]:
                raise SourceFailure('citic_table_period_or_columns')
            values = _citic_amounts(block[header.end():])
            bonds, stocks, total = (values[k] for k in ['债券','股票','合计'])
            if not 0 < bonds+stocks <= total or min(bonds,stocks)<=0:
                raise SourceFailure('citic_table_denominator')
            row = dict(
                date=period,  # 合并附注8列头对应期末；同一半年报含本期及上年末比较数。
                trading_bonds_cny=float(bonds),  # 交易性金融资产债券公允价值合计，人民币元。
                trading_stocks_cny=float(stocks),  # 同表股票公允价值合计，人民币元。
                trading_assets_cny=float(total),  # 同表全部交易性金融资产公允价值合计，人民币元。
                bond_pct=float(100*bonds/total),  # 债券占同表总额，百分数；延续原指标分母。
                within_pct=float(100*bonds/(bonds+stocks)),  # 债券占债券加股票，百分数；不作全行业推断。
                available_at=published)  # 本份半年报公布日期；比较数同样来自本份报告。
            # PDF共享内容流可跨裁切页面重复出现；同一表身份只接受逐字段相同的重复。
            if period in result and result[period]!=row:
                raise SourceFailure('citic_conflicting_table')
            result[period]=row
        if len(result)==2:
            break
    if set(result)!= {current_period,_period(year-1,12)}:
        raise SourceFailure('citic_table_missing')
    return list(result.values())


def _citic_amounts(text):
    """每个日期表从六列读到本表合计；随后同页其它附注不进入这一事实。"""
    values = {}
    for line in text.splitlines():
        match = re.fullmatch(r'\s*(债券|股票|合计)\s+(.+?)\s*',line)
        if match is None:
            continue
        numbers = match[2].split()
        if len(numbers)!=6 or any(re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}|-',v) is None for v in numbers):
            raise SourceFailure('citic_table_columns')
        amounts = [Decimal(v.replace(',','')) if v!='-' else Decimal(0) for v in numbers]
        if amounts[0]+amounts[1]!=amounts[2] or amounts[3]+amounts[4]!=amounts[5]:
            raise SourceFailure('citic_table_totals')
        if match[1] in values:
            raise SourceFailure('citic_duplicate_row')
        values[match[1]]=amounts[2]
        if set(values)=={'债券','股票','合计'}:
            return values
    raise SourceFailure('citic_table_rows')


def citic_broker(fetch, config, start, end):
    """指定披露平台自动查原600030半年/年报；比较数随原报告读取，旧行不改写。"""
    identities=parse_json(fetch.post_readonly('https://www.cninfo.com.cn/new/information/topSearch/query',dict(keyWord='600030',maxNum='10')))
    if type(identities) is not list or any(type(row) is not dict for row in identities):
        raise SourceFailure('citic_security_identity')
    matches=[r for r in identities if r.get('code')=='600030']
    if len(matches)!=1 or re.fullmatch(r'[A-Za-z0-9]{1,32}',matches[0].get('orgId','')) is None:
        raise SourceFailure('citic_security_identity')
    rows, seen, expected=[],set(),None
    for page in range(1,config.get('max_pages',4)+1):
        params=dict(pageNum=str(page),pageSize='50',column='sse',tabName='fulltext',stock='600030,'+matches[0]['orgId'],
            searchkey='年度报告',secid='',plate='',category='',trade='',seDate=start[:4]+'-01-01~'+end,sortName='',sortType='',isHLtitle='false')
        raw=parse_json(fetch.post_readonly(config['url'],params))
        if type(raw) is not dict:
            raise SourceFailure('citic_directory_schema')
        items=raw.get('announcements');count=raw.get('totalAnnouncement')
        if (type(count) is not int or not 0<count<=50*config.get('max_pages',4)
                or type(items) is not list or len(items)!=min(50,count-(page-1)*50)
                or type(raw.get('hasMore')) is not bool or raw['hasMore']!=(page*50<count)):
            raise SourceFailure('citic_directory_schema')
        if expected is not None and expected!=count:
            raise SourceFailure('citic_directory_changed')
        expected=count
        for item in items:
            title=item.get('announcementTitle','');match=re.fullmatch(r'中信证券股份有限公司(20\d{2})年(半年度|年度)报告',title)
            if match is None:
                continue
            if item.get('secCode')!='600030' or item.get('orgId')!=matches[0]['orgId']:
                raise SourceFailure('citic_report_identity')
            year=int(match[1]);annual=match[2]=='年度';period=_period(year,12 if annual else 6)
            if not start<period<=end:
                continue
            url=_official('https://static.cninfo.com.cn/',item['adjunctUrl'],'static.cninfo.com.cn','/finalpage/')
            publication=re.search(r'/finalpage/(20\d{2}-\d{2}-\d{2})/',url)
            if publication is None or publication[1]>end:
                continue
            if publication[1]<period:
                raise SourceFailure('citic_publication_before_period')
            if period in seen:
                raise SourceFailure('citic_duplicate_report')
            seen.add(period)
            parsed=citic_pdf(fetch.get(url),year,publication[1],fetch.budget,annual=annual)
            rows.extend(row for row in parsed if start<row['date']<=end)
            fetch.records[-1]['parsed_document']=dict(period=period,published=publication[1],unit='CNY',scope='CITIC_consolidated_trading_financial_assets',columns='fair_value_total')
        if not raw.get('hasMore'):
            break
    else:
        raise SourceFailure('citic_directory_page_budget')
    unique={}
    for row in rows:
        previous=unique.get(row['date'])
        # 同期可在年报和后继半年报比较列重复出现；采用本次最新公布的原报告，
        # 同一公布日的数值冲突拒绝。available_at表示选中报告日，不声称最早可知。
        if previous is not None and previous['available_at']==row['available_at'] and previous!=row:
            raise SourceFailure('citic_conflicting_period')
        if previous is None or previous['available_at']<row['available_at']:
            unique[row['date']]=row
    return {'holdings_broker':sorted(unique.values(),key=lambda r:r['date'])}


def update_definition(metric, definition, rows, receipts, completed):
    """本次原数字来源回执更新采集状态；旧报告行及原方法版本保持。"""
    policy=dict(definition.get('refresh_policy',{}))
    policy.update(mode='automatic',mode_label='自动采集',automatic_refresh_enabled=True,
        source_checked_at=completed,source_frequency=definition['frequency'],
        source_latest_period=max((row['date'] for row in rows),default=None),
        freshness_status='按已取得报告期显示；未披露期间保持空缺')
    collected=[r['completed_at'] for r in receipts if r.get('status')=='success' and r.get('observations',0)>0]
    if collected:policy['source_collected_at']=max(collected)
    definition['refresh_policy']=policy
    if metric=='holdings_broker':
        definition['source']='中信证券合并半年/年报附注8：交易性金融资产'
        definition['source_url']='https://www.cninfo.com.cn/new/disclosure/stock?stockCode=600030'
        definition['frequency']='半年 / 年报含期末比较数'
    elif metric=='holdings_wealth':
        definition['frequency']='季度 / 半年 / 年度实际报告'
        definition['frequency_audit'].update(kind='quarterly_disclosure',label='季度披露')
    # 字段来源名称随当前报告家族更新；历史每份实际原件由原父对象及本轮捕获持有。
    for field in definition['field_schema'].values():
        if metric=='holdings_broker':field['source']=definition['source']
    policy['source_frequency']=definition['frequency']
