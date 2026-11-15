"""WT数据侧的定日补充事实读取；固定原件目录、单线程LRU，无外部采集副作用。"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
from pathlib import Path
from ..guanheng_market_client import strict_json
from ..guanheng_market_client.daily_facts import SHSZ_PROJECTIONS, validate_day_facts
from ..guanheng_market_client.market_snapshot import _day,_hash


def _read(path,maximum,expected):
    before=path.stat()
    if not path.is_file()or before.st_size>maximum:raise ValueError('daily facts file capacity')
    with path.open('rb')as stream:body=stream.read(before.st_size+1)
    after=path.stat()
    if (len(body)>maximum or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)
            or hashlib.sha256(body).hexdigest()!=expected):
        raise ValueError('daily facts source changed')
    return body


class DayFactsStore:
    """创建/调用/关闭均归外层市场服务线程；16MiB为缓存原JSON字节预算。"""
    def __init__(self,descriptor):
        if type(descriptor)is not dict or set(descriptor)!={'path','sha256'}:raise ValueError('daily facts descriptor invalid')
        path=Path(descriptor['path'])
        if not path.is_absolute():raise ValueError('daily facts catalog path invalid')
        path=path.resolve(strict=True);self._root=path.parent
        body=_read(path,16777216,_hash(descriptor['sha256']));index=strict_json(body)
        if (type(index)is not dict or set(index)!={'schema','days'}or index['schema']!='guanheng.daily-facts-catalog.v1'
                or type(index['days'])is not list or not 1<=len(index['days'])<=366):
            raise ValueError('daily facts catalog invalid')
        self._entries={}  # 日期到固定原件描述；生命周期固定于当前市场版本。
        self._cache=OrderedDict()  # 日期到(已校验对象,原字节数)，最近使用项在末尾。
        self._state_index={}  # 已缓存日期到证券行索引；只引用原行，随同一LRU逐出释放。
        self._bytes=0  # 当前缓存原JSON字节总数；释放和逐出同步扣减。
        self._closed=False  # 外层close后拒绝读取，内存由本对象归还。
        for entry in index['days']:
            if type(entry)is not dict or set(entry)!={'date','path','sha256'}:raise ValueError('daily facts entry invalid')
            day=_day(entry['date']);_hash(entry['sha256']);relative=Path(entry['path'])
            if day in self._entries or relative.is_absolute()or '..'in relative.parts or not str(relative):
                raise ValueError('daily facts entry identity invalid')
            self._entries[day]=dict(entry)

    def _load(self,day):
        """同一owner内复用已校验对象，避免单证券状态查询复制整个股票池。"""
        if self._closed:raise ValueError('daily facts store closed')
        if day not in self._entries:return None
        entry=self._entries[day]
        if day in self._cache:
            value,size=self._cache.pop(day)
        else:
            path=(self._root/entry['path']).resolve(strict=True)
            if not path.is_relative_to(self._root):raise ValueError('daily facts source path escaped')
            body=_read(path,8388608,entry['sha256']);value=validate_day_facts(strict_json(body));size=len(body)
            if value['date']!=day:raise ValueError('daily facts source date differs')
            while self._cache and (len(self._cache)>=8 or self._bytes+size>16777216):
                removed,(_,old)=self._cache.popitem(last=False);self._bytes-=old
                self._state_index.pop(removed,None)
            self._bytes+=size
        self._cache[day]=(value,size)
        return value

    def query(self,day,snapshot_id):
        """返回深拷贝；原件缺日返回None，损坏/读取错误沿外层IoError传播。"""
        value=self._load(day)
        if value is None:return None
        entry=self._entries[day]
        result=deepcopy(value)
        result.update(source_snapshot_id=snapshot_id,source_sha256=entry['sha256'])
        return result

    def shsz(self, day, snapshot_id):
        """只投影已校验的沪深汇总和定日事实身份，避免复制或传输全市场股票行。"""
        value = self._load(day)
        if value is None:
            return None
        result = dict(
            date=day,  # 原事实交易日。
            source_snapshot_id=snapshot_id,  # 请求固定的市场快照。
            source_sha256=self._entries[day]['sha256'])  # 完整事实原件摘要。
        for key in SHSZ_PROJECTIONS:
            if key in value:
                result[key] = dict(value[key])
        return result

    def days(self):
        """当前冻结目录内全部定日事实日期，按交易日顺序返回。"""
        if self._closed:
            raise ValueError('daily facts store closed')
        return sorted(self._entries)

    def security_state(self,day,symbol):
        """仅返回原同日交易状态和成交量；原资格不足保持原字符串，不推断停牌。"""
        value=self._load(day)
        if value is None:return None
        if day not in self._state_index:self._state_index[day]={row[1]:row for row in value['rows']}
        row=self._state_index[day].get(symbol)
        if row is None:return None
        return dict(
            tradestatus=row[6],  # 原状态0/1/?；?沿原未核实含义。
            qualification=row[7],  # 原定日身份和交易状态资格。
            volume=row[4],  # 原成交股数十进制字符串，空字符串表示未知，0表示已知零。
            close_reference=row[2])  # 原同日参考收盘价；空/零值不确认已有有效日线价格。

    def close(self):
        self._cache.clear();self._state_index.clear();self._bytes=0;self._closed=True
