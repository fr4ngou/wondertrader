"""原乐咕公开页面全A市值/GDP快照；保留展示值与独立页面百分数。"""
from datetime import date
from decimal import Context, Decimal, localcontext
from html.parser import HTMLParser
import math
import re

from .source_fetch import SourceFailure


METRIC = 'valuation_marketcap_gdp_latest'
URL = 'https://legulegu.com/stockdata/marketcap-gdp'
FORMULA = '公开页面总市值/GDP百分数 / 100；不以舍入分子分母重算'
BOUNDARY = '仅原归档和实际采集到的页面快照；缺失日期不插补。沪深含B月末模型独立保留。'


class _Page(HTMLParser):
    """只提取固定页面节点文本；不执行脚本、图表请求或访问配额操作。"""
    def __init__(self, budget):
        super().__init__(convert_charrefs=True)
        self.budget = budget  # 原采集总截止，节点解析不续期。
        self.stack = []  # 当前非空元素，含目标键及其局部文本；由本解析器拥有。
        self.values = {}  # 每种目标节点的实际出现次数与完整文本；重复由领域准入拒绝。

    def handle_starttag(self, tag, attributes):
        self.budget.remaining()
        if tag in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
            return
        attrs = dict(attributes)
        classes = set(attrs.get('class', '').split())
        keys = [key for key in ('metric-market-cap','metric-gdp','metric-ratio','data-view-head-updated-time')
                if key in classes]
        if attrs.get('id') == 'data-description':
            keys.append('description')
        if tag == 'p':
            keys.append('paragraph')
        if len(self.stack) >= 128:
            raise SourceFailure('legu_gdp_page_capacity')
        self.stack.append([tag, keys, []])

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, -1, -1):
            if self.stack[index][0] == tag:
                for _, keys, text in self.stack[index:]:
                    for key in keys:
                        self.values.setdefault(key, []).append(''.join(text))
                del self.stack[index:]
                break

    def handle_data(self, value):
        self.budget.remaining()
        for _, keys, parts in self.stack:
            if keys:
                if sum(map(len, parts)) + len(value) > 8192:
                    raise SourceFailure('legu_gdp_page_capacity')
                parts.append(value)


def _single(values, key):
    result = values.get(key, [])
    if len(result) != 1:
        raise SourceFailure('legu_gdp_page_schema')
    return re.sub(r'\s+', '', result[0])


def page_snapshot(body, budget):
    """返回页面观察日、万亿舍入原值及百分数换算；不构造历史或同日指数事实。"""
    budget.remaining()
    if len(body) > min(2*1024*1024, budget.response_bytes):
        raise SourceFailure('legu_gdp_page_capacity')
    try:
        parser = _Page(budget)
        parser.feed(body.decode('utf8'))
        parser.close()
        values = parser.values
        day = _single(values, 'data-view-head-updated-time')
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError('date')
        numeric = r'(\d{1,20}(?:\.\d{1,12})?)'
        market = re.fullmatch('总市值'+numeric+r'万亿(?:元)?', _single(values, 'metric-market-cap'))
        gdp = re.fullmatch('GDP'+numeric+r'万亿(?:元)?', _single(values, 'metric-gdp'))
        percent = re.fullmatch('总市值/GDP'+numeric+'%', _single(values, 'metric-ratio'))
        description = re.fullmatch(r'(\d{4})年(\d{2})月(\d{2})日，总市值比GDP值为：'+numeric+'%',
                                   _single(values, 'description'))
        if not all((market, gdp, percent, description)):
            raise SourceFailure('legu_gdp_page_schema')
        if (f'{description[1]}-{description[2]}-{description[3]}' != day
                or Decimal(description[4]) != Decimal(percent[1])):
            raise SourceFailure('legu_gdp_page_identity')
        notes = [re.sub(r'\s+', '', text) for text in values.get('paragraph', [])]
        if not any(text.startswith('∑A股市值（上交所、深交所、北交所已上市股票）') for text in notes):
            raise SourceFailure('legu_gdp_market_scope')
        if '上年度国内生产总值（GDP），采用上一年度的全年GDP数值进行计算。' not in notes:
            raise SourceFailure('legu_gdp_denominator_definition')
        # 三个数分别来自页面；舍入后的分子/分母不参与ratio计算。
        with localcontext(Context(prec=40)):
            market_value, gdp_value = float(Decimal(market[1])), float(Decimal(gdp[1]))
            ratio = float(Decimal(percent[1])/Decimal(100))
        if (not all(math.isfinite(value) for value in (market_value, gdp_value, ratio))
                or gdp_value <= 0 or market_value < 0 or ratio < 0):
            raise SourceFailure('legu_gdp_page_values')
        return dict(date=day, ratio=ratio, marketcap_trillion=market_value,
                    gdp_trillion=gdp_value, gdp_year=date.fromisoformat(day).year-1, available_at=None)
    except SourceFailure:
        raise
    except (ValueError, TypeError, UnicodeError, ArithmeticError):
        raise SourceFailure('legu_gdp_page_schema') from None


def history(fetch, config, start, end):
    """原公开页面一次读取，仅返回窗口内当前实际快照，调用者拥有合并及CAS。"""
    if config.get('url') != URL or config.get('datasets') != [METRIC]:
        raise SourceFailure('legu_gdp_configuration')
    row = page_snapshot(fetch.get(URL), fetch.budget)
    return {METRIC: [row] if start <= row['date'] <= end else []}


def update_definition(definition, rows, receipts, checked_at):
    """仅在本指标有本轮来源回执时更新观察说明；旧行、方法版本和其他模型保持。"""
    if not receipts:
        return
    definition.update(label='沪深北全A市值 / 上年GDP · 页面观察快照',
        source='乐咕乐股公开页面原值；既有归档与后继实际采集',
        frequency='实际公开页面快照；连续日频历史缺口保留', points=True)
    definition['limitations'] = [
        '总市值按页面说明覆盖上交所、深交所、北交所A股；GDP按页面说明采用上年度全年值。',
        '市值、GDP及百分比各自保留页面展示舍入值；ratio仅将页面百分数除以100。',
        BOUNDARY,
        '当前页面未提供来源首次可知时间和同日沪深300报价；未知字段留空，旧参考事实保留。']
    definition['field_schema']['ratio']['formula'] = FORMULA
    definition['field_schema']['gdp_year']['formula'] = '按页面上年度说明与该观察日年份减1登记'
    for line in definition.get('lines', []):
        if line['key'] == 'ratio':
            line['formula'] = FORMULA
        elif line['key'] == 'csi300_reference':
            line['reading'] = '只读既有同日指数事实；新快照缺少同日来源时为空，不跨日补值。'
    definition['how_to_read']['boundary'] = BOUNDARY
    definition['reading'] = ('比例取公开页面百分数÷100，市值和GDP是页面万亿展示值。'
        '各点代表实际存入的观察日，两个观察点之间没有补造数据。'+BOUNDARY)
    audit = definition['frequency_audit']
    audit.update(kind='observed_snapshots', label='实际页面快照', daily_ready=False,
                 full_listed_history_complete=False, reason=BOUNDARY)
    archive = definition.get('history_audit')
    if archive is not None:
        archive.update(current_count=len(rows), start=rows[0]['date'] if rows else None,
            end=rows[-1]['date'] if rows else None, frequency=definition['frequency'],
            history_status='observed_page_snapshots', label=definition['label'], explanation=BOUNDARY)
    review = definition.get('reference_review')
    if review is not None:
        review.update(label=definition['label'], limitations=list(definition['limitations']),
                      lines=definition.get('lines', []), reading=definition['reading'],
                      status='实际页面快照；连续历史缺口保留')
    policy = definition.get('refresh_policy', {})
    successful = any(row['status'] in ('success','no_new_observations') for row in receipts)
    policy.update(automatic_refresh_enabled=True, mode='snapshot', mode_label='原采集器持续保存页面快照',
        source_checked_at=checked_at, source_latest_period=rows[-1]['date'] if rows else None,
        source_frequency=definition['frequency'],
        freshness_status='本轮原页面检查成功' if successful else '本轮来源失败，保留已发布快照')
    if successful:
        policy['source_collected_at'] = checked_at
    definition['refresh_policy'] = policy
