"""证券业务用途归价格资料边界；已知Source类型与官方规则共同准入，不猜证券类型。"""
from datetime import datetime
import re


_FUND = dict(
    rule_id='sse.fund-code-business.2026-05-22',  # 官方基金产品代码业务用途规范版本。
    effective_from='2026-05-22',  # 只用于本规范生效后的目标日，不推造早期资格。
    url='https://www.sse.com.cn/lawandrules/guide2025/jjznlc/c/10819325/files/ec2a8b512f3c49cead27243181d28d79.docx',  # 官方原件。
    sha256='15e86c0beff808f5b3b35fb7a78681a6176bfcda6d8f9e27923aa0f78d6905ee')  # 已核原文件字节。
_STATISTICS = dict(
    rule_id='szse.turnover-statistics.2023-09-04',  # 官方成交量统计指标定义表版本。
    effective_from='2023-09-04',  # 保守采用本份已核技术文件日期。
    url='https://www.szse.cn/www/marketServices/technicalservice/guide/P020230904549038313109.pdf',  # 官方原件。
    sha256='607f00fa59b446f1d963cc301337bd16ec5378ccfe7fc6ffec96163a0b6844e8')  # 已核原文件字节。
_STATISTIC_CODES = frozenset(('395001','395002','395004','395005','395006','395011','395012',
    '395013','395015','395032','395033','395034','395041','395099'))


def non_price_role(identity, day):
    """返回有官方正面依据的非OHLC用途；None保留正常价格核查，不授上市/成交资格。

    identity已由原SecurityReference核验；类型来自实际Source或保留原件。仅在该类型
    的业务域内解释官方代码用途，未知类型和规范生效前日期均不据代码补推类型。
    """
    # Source最低Python3.6.8不提供date.fromisoformat；固定ISO日历日期走同一标准库准入。
    if type(day)is not str or re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',day)is None:
        raise ValueError('price role requires ISO calendar day')
    datetime.strptime(day,'%Y-%m-%d')
    if (type(identity) is not dict or re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}',identity.get('symbol','')) is None
            or identity.get('security_type') not in ('stock','etf','index','unknown')):
        raise ValueError('price role requires verified canonical security identity')
    market, code = identity['symbol'].split('.')
    kind = identity['security_type']
    role = evidence = None
    if market == 'SSE' and kind == 'etf' and day >= _FUND['effective_from'] and code.startswith('5'):
        if code[-1] == '3': role = 'fund_subscription'
        elif code[-1] == '4': role = 'fund_subscription_cash'
        if role is not None: evidence = _FUND
    elif (market == 'SZSE' and kind == 'index' and day >= _STATISTICS['effective_from']
            and code in _STATISTIC_CODES):
        role, evidence = 'turnover_statistic', _STATISTICS
    if role is None: return None
    return dict(
        role=role,  # 网上认购、认购资金或成交量统计，均不是该身份的OHLC证券。
        reason='not_price_instrument',  # 价格任务适用性；与原Source完整名册分别记录。
        evidence=dict(evidence))  # 固定官方原件/版本，不覆盖原Source资料。


def source_price_role(member, day):
    """同版Source/Host可用的纯目录接缝；原v9成员及raw响应保持字节不变。

    market/type来自实际SDK目录已验证的原成员。返回独立业务用途，不把ETF板块
    类型改成另一种证券，也不把所有5开头代码作为基金；缺类型继续unknown。
    """
    raw=member.get('symbol')
    if type(raw) is not str or re.fullmatch(r'[0-9]{6}\.(SH|SZ|BJ)',raw) is None:
        raise ValueError('price role requires original Source member')
    market={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[raw[-2:]]
    if member.get('market')!=raw[-2:]:raise ValueError('price role Source market differs')
    return non_price_role(dict(symbol=market+'.'+raw[:6],security_type=member.get('security_type')),day)
