"""原生日线与原Writer闭合尾部的只读来源适配；不下载、不修改采集器。"""
from __future__ import annotations

import configparser
import csv
from dataclasses import asdict
from datetime import datetime
import hashlib
import io
from pathlib import Path
import re
import tempfile
import threading

from ..guanheng_market_client import API_VERSION, MarketUnavailable, encode_json, strict_json, validate_request, validate_response
from ..guanheng_market_client.source_history import daily_selection_metadata, validate_source_daily_data, validate_source_metadata
from .models import SourceSession
from .price_quality import validate_price_quality,summarize_source_bars
from ..guanheng_market_client.daily_contract import source_daily_security
from .native_history import NativeHistory, source_file_metadata
from .source_market import _require, _hash


def _read(path, maximum):
    """原文件只读双核；文件大小、修改身份及字节摘要同时约束。"""
    before = path.stat()
    _require(path.is_file() and before.st_size <= maximum)
    with path.open('rb') as stream:
        raw = stream.read(before.st_size + 1)
    after = path.stat()
    _require(len(raw) <= maximum and (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns))
    return raw


def _metadata(source, content, dataset, profile):
    # source为原捕获身份；content_id为原件摘要；价格和量额保持profile原单位。
    return dict(source=source, qualification='DevelopmentVerified', dataset_version=dataset,
                content_id=content, source_license=profile['source_license'], adjustment='none',
                factor_version='', minute_boundary='unknown', timezone='Asia/Shanghai',
                value_semantics='source', timestamp_semantics='source_date', period='1d',
                **{k:profile[k] for k in ('price_unit','volume_unit','amount_unit')})


def _select(rows, query, empty_metadata, *, archive=None):
    """保留最新limit个日期；逐段来源完整覆盖实际返回bar。"""
    chosen = [rows[d] for d in sorted(rows) if query['from'] <= d <= query['to']][-query['limit']:]
    bars, parts = [], []
    for bar, metadata in chosen:
        if not parts or parts[-1]['metadata'] != metadata:
            # offset为0起行号；count为连续行数；metadata只属于该段原来源。
            parts.append(dict(offset=len(bars), count=0, metadata=metadata))
        parts[-1]['count'] += 1
        bars.append(bar)
    result = dict(metadata=parts[0]['metadata'] if parts else empty_metadata,
                  bars=bars, coverage='Unknown', missing_dates=[],
                  selection=dict(period='1d', limit=query['limit']))
    if len(parts) > 1:
        result.update(provenance=parts, metadata=daily_selection_metadata(bars, parts))
    if archive is not None:
        result['archive']=archive
    return validate_source_daily_data(result, query)


class DailyOverlayMarket:
    """单服务线程拥有原Reader；固定历史与动态收盘输出按日期衔接。

    配置字段：mode选择本适配；base为原读取配置；archive为不可变清单
    path/sha256或None；native_reader为原Reader的library/sha256；
    max_file_bytes为每原件字节上限；max_bars为每DSB记录上限；
    response_shape为segments逐段或dataset显式QMT派生批次。
    snapshots允许None；启用时storage_root归原Writer所有，scratch_root归
    本适配在E盘临时使用，session_id为原收盘marker时段，source为原采集
    身份，source_license及三单位沿原声明，symbols限定可消费的WT证券。
    archive.entries每项：symbol为WT证券，path为清单内相对DSB，sha256
    固定字节，rows为总数，first/last为YYYYMMDD日期，provenance用
    offset/count连续覆盖全部行，metadata保留对应行原来源和单位。
    """

    def __init__(self, config, *, max_response_bytes=8 * 1024 * 1024):
        from .source_market import create_native_source_market
        self._owner = threading.get_ident()
        self._base = self._reader = None
        self._closed = False
        try:
            _require(type(config) is dict and set(config) == {'mode','base','archive','native_reader','snapshots','max_file_bytes','max_bars','response_shape'})
            _require(config['mode'] == 'source-daily-overlay')
            # segments返回逐段来源；dataset供旧SDK读取显式QMT派生日线数据集。
            self._shape = config['response_shape']
            _require(self._shape in ('segments','dataset'))
            self._maximum = max_response_bytes
            self._max_file = config['max_file_bytes']
            self._max_bars = config['max_bars']
            _require(type(self._max_file) is int and 1024 <= self._max_file <= 268435456)
            _require(type(self._max_bars) is int and 1 <= self._max_bars <= 1000000)
            self._entries = {}
            archive = config['archive']
            if archive is not None:
                _require(set(archive) == {'path','sha256'})
                path = Path(archive['path']).resolve(strict=True)
                raw = _read(path, 16 * 1024 * 1024)
                _require(hashlib.sha256(raw).hexdigest() == _hash(archive['sha256']))
                manifest = strict_json(raw)
                _require(manifest.get('schema') in ('guanheng.daily-native-archive.v1','guanheng.daily-native-archive.v2'))
                _require(set(manifest)==({'schema','entries','helper_sha256'}if manifest['schema'].endswith('.v2')else {'schema','entries'}))
                _require(type(manifest['entries']) is list and len(manifest['entries']) <= 20000)
                version2=manifest['schema']=='guanheng.daily-native-archive.v2'
                if version2:_hash(manifest['helper_sha256'])
                self._archive_root = path.parent
                for entry in manifest['entries']:
                    _require(set(entry) == ({'symbol','path','sha256','rows','first','last','provenance','source_rows_sha256','price_range_quality'}if version2 else {'symbol','path','sha256','rows','first','last','provenance'}))
                    _require(type(entry['symbol']) is str and re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}',entry['symbol']))
                    dsb = (path.parent / entry['path']).resolve(strict=True)
                    _require(dsb.is_relative_to(path.parent) and 1 <= entry['rows'] <= self._max_bars)
                    _hash(entry['sha256'])
                    count = 0
                    for part in entry['provenance']:
                        _require(set(part) == {'offset','count','metadata'} and part['offset'] == count and type(part['count']) is int and part['count'] > 0)
                        validate_source_metadata(part['metadata'],period='1d')
                        count += part['count']
                    _require(count == entry['rows'])
                    basis=entry['provenance'][0]['metadata']['adjustment']
                    _require(all(part['metadata']['adjustment']==basis for part in entry['provenance']))
                    key=(entry['symbol'],basis)
                    _require(key not in self._entries and (version2 or basis=='none'))
                    if version2:
                        _hash(entry['source_rows_sha256']);validate_price_quality(entry['price_range_quality'],entry['rows'],allow_consistent=True)
                    self._entries[key] = entry
            native = config['native_reader']
            _require(set(native) == {'library','sha256'})
            self._reader = NativeHistory(Path(native['library']),native['sha256'], max_bars=self._max_bars,max_file_bytes=self._max_file)
            self._snapshots = config['snapshots']
            if self._snapshots is not None:
                s = self._snapshots
                _require(set(s) == {'storage_root','scratch_root','session_id','source','source_license','price_unit','volume_unit','amount_unit','symbols'})
                self._storage = Path(s['storage_root']).resolve(strict=True)
                self._scratch = Path(s['scratch_root']).resolve(strict=True)
                _require(self._scratch.is_dir() and self._scratch.drive.upper() == 'E:')
                _require(self._storage.is_dir() and type(s['session_id']) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,32}',s['session_id']))
                self._snapshot_source = SourceSession(**s['source'])
                _require(self._snapshot_source.provider == 'Qmt')
                _require(type(s['symbols']) is list and len(s['symbols']) <= 10000)
                _require(all(re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}',v) for v in s['symbols']))
                validate_source_metadata(_metadata(s['source'],'0'*64,'wt-native-snapshot-daily.v1',s),period='1d')
            self._base = create_native_source_market(config['base'],max_response_bytes=max_response_bytes)
        except BaseException:
            self.close()
            raise

    def _native(self, path, security, metadata, count=None, *, decoding_version=None, expected_identity=None,quality=None):
        raw = _read(path,self._max_file)
        content = hashlib.sha256(raw).hexdigest()
        if expected_identity is not None:
            _require(content == expected_identity)
        header = source_file_metadata(metadata,content,count,decoding_version=decoding_version,quality=quality)
        code, exchange = security.split('.')[1],security.split('.')[0]
        history = self._reader.read_source_file(path,source_daily_security(exchange,code),header)
        if quality is not None:_require(summarize_source_bars(history.bars)==quality)
        _require(hashlib.sha256(_read(path,self._max_file)).hexdigest() == content)
        bars = [dict(symbol=security,date=int(bar.occurred_at.strftime('%Y%m%d')),
                     **{k:getattr(bar,k) for k in ('open','high','low','close','volume','amount')}) for bar in history.bars]
        return bars, content

    def _archive(self, key):
        security=key[0];entry = self._entries[key]
        path = self._archive_root / entry['path']
        metadata = entry['provenance'][0]['metadata']
        bars, content = self._native(path,security,metadata,entry['rows'],decoding_version='wt-daily-native-archive.v1',expected_identity=entry['sha256'],quality=entry.get('price_range_quality'))
        _require(content == entry['sha256'] and bars[0]['date'] == entry['first'] and bars[-1]['date'] == entry['last'])
        rows = {}
        for part in entry['provenance']:
            for bar in bars[part['offset']:part['offset']+part['count']]:
                rows[bar['date']] = (bar,part['metadata'])
        _require(len(rows) == entry['rows'])
        return rows,metadata

    def _tail(self, security, after, query):
        s = self._snapshots
        if s is None or security not in s['symbols']:
            return {}
        marker_path = self._storage/'marker.ini'
        marker_raw = _read(marker_path,65536)
        marker = configparser.ConfigParser(interpolation=None)
        marker.read_string(marker_raw.decode('utf8'))
        closed = int(marker['markers'][s['session_id']])
        datetime.strptime(str(closed),'%Y%m%d')
        if closed <= after:
            return {}
        exchange,code = security.split('.')
        path = self._storage/'his/day'/exchange/(code+'.dsb')
        result = {}
        if path.exists():
            captured = _read(path,self._max_file)
            identity = hashlib.sha256(captured).hexdigest()
            metadata = _metadata(s['source'],identity,'wt-collected-day-v1',s)
            # 原文件ABI只对E盘私有副本加读取租约，Writer仍持有原目录写入权。
            with tempfile.TemporaryDirectory(dir=self._scratch,prefix='day-read-') as directory:
                snapshot = Path(directory)/(code+'.dsb')
                snapshot.write_bytes(captured)
                bars,unused = self._native(snapshot,security,metadata)
            _require(hashlib.sha256(_read(path,self._max_file)).hexdigest() == identity)
            result = {b['date']:(b,metadata) for b in bars if after < b['date'] <= closed}
        if after < min(closed,query['to']):
            # 原day按日期优先；最大日期不证明中间日期连续，逐日期补缺。
            native_dates = frozenset(result)
            paths = sorted((self._storage/'his/snapshot').glob('????????.csv'))
            # 文件名是写入自然日；仅CSV date决定交易日。尾部扫描有界64文件。
            paths = [p for p in paths if p.stem.isdigit()][-64:]
            for snapshot in paths:
                raw = _read(snapshot,self._max_file)
                _require(raw.endswith(b'\n'))
                digest = hashlib.sha256(raw).hexdigest()
                metadata = _metadata(s['source'],digest,'wt-native-snapshot-daily.v1',s)
                reader = csv.DictReader(io.StringIO(raw.decode('utf8')))
                _require(reader.fieldnames == ['date','exchg','code','open','high','low','close','settle','volume','turnover','openinterest','upperlimit','lowerlimit','preclose','presettle','preinterest'])
                for row in reader:
                    _require(None not in row and all(type(v) is str and v for v in row.values()))
                    if row['exchg'] != exchange or row['code'] != code:
                        continue
                    day = int(row['date'])
                    if not max(after,query['from']-1) < day <= min(closed,query['to']) or day in native_dates:
                        continue
                    bar = dict(symbol=security,date=day,**{k:float(row[v]) for k,v in [('open','open'),('high','high'),('low','low'),('close','close'),('volume','volume'),('amount','turnover')]})
                    _require(day not in result or result[day][0] == bar)
                    result[day] = (bar,metadata)
                _require(hashlib.sha256(_read(snapshot,self._max_file)).hexdigest() == digest)
        _require(_read(marker_path,65536) == marker_raw)
        return result

    def call(self, request):
        _require(threading.get_ident() == self._owner and not self._closed)
        request = validate_request(strict_json(encode_json(request)))
        # Writer日线和收盘快照属于原价；供应商前复权沿base的显式分析价商店读取。
        if request['action'] != 'history.source-daily-query':
            return self._base.call(request)
        query = request['request']
        security = query['exchange']+'.'+query['code'];basis=query.get('adjustment','none');key=(security,basis)
        if basis!='none'and key not in self._entries:return self._base.call(request)
        frozen = query.get('view') == 'archive'
        # 冻结视图保留已绑定SHA的静态DSB；动态Writer尾部独立排除。
        if frozen and key not in self._entries:
            return self._base.call(request)
        try:
            if key in self._entries:
                rows,metadata = self._archive(key)
                last = max(rows)
            else:
                original = self._base.call(request)
                if original['status']['code'] != 'Ok':
                    return original
                data = original['data']
                metadata = data['metadata']
                rows = {b['date']:(b,metadata) for b in data['bars']}
                newest = self._base.call(dict(api_version=API_VERSION,action='history.source-daily-query',request=dict(exchange=query['exchange'],code=query['code'],**{'from':10000101,'to':20991231,'limit':1})))
                _require(newest['status']['code'] == 'Ok')
                last = max((b['date'] for b in newest['data']['bars']),default=0)
            if not frozen and basis=='none':
                rows.update(self._tail(security,last,query))
            archive=(dict(first_date=min(rows),last_date=max(rows),count=len(rows))
                if frozen and query.get('include_archive',False)else None)
            data = _select(rows,query,metadata,archive=archive)
            if self._shape == 'dataset' and 'provenance' in data:
                _require(all(part['metadata']['source']['provider'] == 'Qmt' for part in data['provenance']))
                identity = data['metadata']['content_id']
                data['metadata'].update(
                    # 独立派生批次；不冒充旧静态DAT或全推运输的捕获会话。
                    source=dict(provider='Qmt',instance_id='wt-daily-derived-dataset',session_id='daily-selection:'+identity,generation=1),
                    dataset_version='wt-native-daily-derived.v1:'+identity,
                    source_license='Derived QMT source values from static DSB and completed WT Writer output; original identities bound in content_id')
                del data['provenance']
            result = dict(api_version=API_VERSION,status=dict(code='Ok',reason=''),data=data)
        except (OSError,ValueError,KeyError,configparser.Error,MarketUnavailable):
            result = dict(api_version=API_VERSION,status=dict(code='IoError',reason='原生日线或闭合快照读取失败'),data={})
        _require(len(encode_json(result)) <= self._maximum)
        return validate_response(result,request)

    def close(self):
        if self._closed:
            return
        _require(threading.get_ident() == self._owner)
        try:
            if self._base is not None:
                self._base.close()
        finally:
            if self._reader is not None:
                self._reader.close()
            self._closed = True
