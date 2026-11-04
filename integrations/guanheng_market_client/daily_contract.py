"""WT来源日线共用的证券与价格口径；只校验纯值，不连接行情或交易。"""
import re

# 仅来源日线使用；分钟、报价和交易保持其原市场范围。
SOURCE_DAILY_MARKETS = {'SSE': 'SH', 'SZSE': 'SZ', 'BSE': 'BJ'}
REFERENCE_PREFIX = 'qmt-front-ratio-reference:'  # 当前可见供应商分析价原件SHA，独立因子资格未知。


def source_daily_symbol(value, *, allow_bse=True):
    """返回原六位供应商代码；BJ需由显式新日线合同选择。"""
    pattern = r'[0-9]{6}\.(SH|SZ|BJ)' if allow_bse else r'[0-9]{6}\.(SH|SZ)'
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise ValueError('source daily security invalid')
    return value


def source_daily_security(exchange, code):
    """将WT日线市场及六位代码转换为原供应商身份，不猜测证券类别。"""
    if exchange not in SOURCE_DAILY_MARKETS or type(code) is not str:
        raise ValueError('source daily market invalid')
    return source_daily_symbol(code + '.' + SOURCE_DAILY_MARKETS[exchange])


def source_price_basis(adjustment, reference, *, allow_reference):
    """none保持空参考；front_ratio只承认显式来源捕获身份，不重算价格或因子。"""
    if adjustment == 'none':
        return reference == ''
    return (allow_reference and adjustment == 'front_ratio' and type(reference) is str
        and re.fullmatch(re.escape(REFERENCE_PREFIX) + '[0-9a-f]{64}', reference) is not None)
