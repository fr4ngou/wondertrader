"""Data-owned证券停牌披露；仅影响对应证券日期的价格缺口，不改变市场日历。"""
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urlparse

from .daily_data_update import _load
from .market_generation import read_fixed


def load_trading_exceptions(descriptor):
    """核归一事实及官方HTTP原件，返回(symbol, ISO日期)到原记录；不联网、不填价。

    事实内容由Data owner依明确披露归一；这里核其原件绑定，不从行情缺日推断停牌。
    null描述符表示没有已准入例外，未知日期继续正常gap/HPR流程。
    """
    if descriptor is None:return {}
    value=_load(descriptor)
    if (type(value)is not dict or set(value)!={'schema','records'}
            or value['schema']!='guanheng.price-trading-exceptions.v1'or type(value['records'])is not list):
        raise ValueError('price trading exceptions invalid')
    result={}
    for row in value['records']:
        if (type(row)is not dict or set(row)!={'symbol','date','no_trade','evidence'}or row['no_trade']is not True
                or type(row['symbol'])is not str or row['symbol'].split('.')[0]not in('SSE','SZSE','BSE')
                or len(row['symbol'].split('.'))!=2 or len(row['symbol'].split('.')[1])!=6
                or not row['symbol'].split('.')[1].isascii()or not row['symbol'].split('.')[1].isdigit()
                or date.fromisoformat(row['date']).isoformat()!=row['date']
                or type(row['evidence'])is not list or not row['evidence']):
            raise ValueError('price trading exception record invalid')
        key=(row['symbol'],row['date'])
        if key in result:raise ValueError('price trading exception duplicate')
        for evidence in row['evidence']:
            if (type(evidence)is not dict or set(evidence)!={'path','sha256','bytes','url','status','received_at'}
                    or evidence['status']!=200 or type(evidence['bytes'])is not int or evidence['bytes']<1
                    or not Path(evidence['path']).is_absolute()
                    or urlparse(evidence['url']).scheme!='https'
                    or urlparse(evidence['url']).hostname not in('www.sse.com.cn','www.szse.cn','fund.szse.cn')):
                raise ValueError('price trading exception source invalid')
            if datetime.fromisoformat(evidence['received_at'].replace('Z','+00:00')).utcoffset()is None:
                raise ValueError('price trading exception clock invalid')
            body=read_fixed(evidence['path'],maximum=16777216,identity=evidence['sha256'])
            if len(body)!=evidence['bytes']:raise ValueError('price trading exception bytes differ')
        result[key]=row
    return result
