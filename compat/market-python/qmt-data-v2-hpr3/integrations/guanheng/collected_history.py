"""原Writer的闭合DSB直接进入统一历史查询；状态和解码沿现有owner。"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import asdict
import hashlib
from pathlib import Path
import re
import tempfile
import threading

from ..guanheng_market_client import (
    API_VERSION, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, MarketProtocolError,
    MarketUnavailable, encode_json, strict_json, validate_request, validate_response,
)
from .models import IntegrationUnavailable, SourceSession
from .native_history import NativeHistory, SourceHistoryMetadata
from .source_history_selection import SourceSelectionConflict, select_sources
from .source_market import NativeSourceMarket, _metadata, _minute, _require, _hash


class CollectedSourceMarket:
    """服务线程拥有原Reader；每次按当前DSB内容读取，归档追加后立即可见。

    collection.source声明采集数据集身份，不声称还原每根bar的原QMT传输会话。
    本入口只读his/min1；盘中形成中的DMB和分钟通知继续由原NMR消费。
    """

    def __init__(self, config, *, max_response_bytes=8 * 1024 * 1024):
        self._owner = threading.get_ident()
        self._closed = False
        self._base = self._reader = None
        self._supplements = []
        try:
            fields = {'mode', 'base', 'collection', 'native_reader', 'max_bars', 'max_file_bytes'}
            _require(type(config) is dict and set(config) in (fields, fields | {'supplements'}))
            supplements = config.get('supplements', [])
            _require(type(supplements) is list)
            _require(config['mode'] == 'source-collected')
            _require(type(config['base']) is dict and config['base'].get('mode') in (
                'source-store', 'source-stores', 'source-catalog'))
            _require(type(max_response_bytes) is int and 1024 <= max_response_bytes <= MAX_RESPONSE_BYTES)
            self._maximum = max_response_bytes
            for name, maximum in (('max_bars', 1000000), ('max_file_bytes', 268435456)):
                _require(type(config[name]) is int and 1 <= config[name] <= maximum)
            native = config['native_reader']
            _require(type(native) is dict and set(native) == {'library', 'sha256'})
            _require(type(native['library']) is str and Path(native['library']).is_absolute())
            _hash(native['sha256'])
            c = config['collection']
            _require(type(c) is dict and set(c) == {
                'storage_root', 'source', 'source_license', 'price_unit', 'volume_unit', 'amount_unit', 'symbols'})
            _require(type(c['storage_root']) is str and Path(c['storage_root']).is_absolute())
            self._root = Path(c['storage_root']).resolve(strict=True)
            _require(self._root.is_dir())
            _require(type(c['source']) is dict and set(c['source']) == {
                'provider', 'instance_id', 'session_id', 'generation'})
            self._source = SourceSession(**c['source'])
            _require(self._source.provider == 'Qmt')
            symbols = c['symbols']
            _require(type(symbols) is list and 1 <= len(symbols) <= 10000)
            _require(all(type(s) is str and re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}', s) for s in symbols))
            _require(len(set(symbols)) == len(symbols))
            self._symbols = frozenset(symbols)
            # 复制已校验的领域值，避免外部配置对象变更影响运行中的文件解释。
            self._profile = dict(source_license=c['source_license'], price_unit=c['price_unit'],
                                 volume_unit=c['volume_unit'], amount_unit=c['amount_unit'])
            self._metadata('0' * 64)
            self._base = NativeSourceMarket(config['base'], max_response_bytes=max_response_bytes)
            self._reader = NativeHistory(Path(native['library']), native['sha256'],
                                        max_bars=config['max_bars'], max_file_bytes=config['max_file_bytes'])
            self._max_file = config['max_file_bytes']
            # 独立导入根继续由原来源商店准入和读取；不修改base注册或Writer文件。
            for supplement in supplements:
                self._supplements.append(NativeSourceMarket(supplement, max_response_bytes=max_response_bytes))
        except BaseException:
            self.close()
            raise

    def _check(self):
        if threading.get_ident() != self._owner or self._closed:
            raise MarketUnavailable('采集归档reader已关闭或调用线程不符')

    def _metadata(self, content):
        profile_identity = hashlib.sha256(encode_json(dict(source=asdict(self._source), **self._profile))).hexdigest()
        return SourceHistoryMetadata(
            source=self._source, qualification='DevelopmentVerified',
            dataset_version='wt-collected-min1-v1:' + profile_identity,
            content_id=content, period='1m', expected_count=None,
            minute_boundary='right', **self._profile)

    def _file_identity(self, path):
        """只消费原文件的有界字节；不在Writer目录取得冻结路径租约。"""
        digest, used = hashlib.sha256(), 0
        _require(path.resolve(strict=True).is_relative_to(self._root))
        with path.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                used += len(block)
                _require(used <= self._max_file)
                digest.update(block)
        return digest.hexdigest(), used

    def _read(self, security, query):
        exchange, code = security.split('.')
        path = self._root / 'his' / 'min1' / exchange / (code + '.dsb')
        if not path.exists():
            return None
        _require(path.resolve(strict=True).is_relative_to(self._root))
        # 原文件ABI按冻结文件取得路径租约。动态采集根继续归Writer写入，
        # 因此先在普通只读句柄双核内容，再对本次私有副本调用原ABI；
        # 避免把冻结目录的租约施加到正在归档的Writer目录。
        with path.open('rb') as stream:
            _require(path.stat().st_size <= self._max_file)
            captured = stream.read(self._max_file + 1)
        _require(20 <= len(captured) <= self._max_file)
        content = hashlib.sha256(captured).hexdigest()
        observed = content, len(captured)
        _require(self._file_identity(path) == observed)
        with tempfile.TemporaryDirectory(prefix='gh-collected-read-') as directory:
            snapshot = Path(directory) / (code + '.dsb')
            with snapshot.open('xb') as stream:
                _require(stream.write(captured) == len(captured))
            del captured
            history = self._reader.read_source_file(snapshot, code + ('.SH' if exchange == 'SSE' else '.SZ'),
                                                    self._metadata(content))
        # 解码私有副本期间原归档可能被下一次写入替换；该轮保留Unavailable，
        # 后继查询重新捕获新版本，避免对变化中的原文件授予本轮稳定读取资格。
        _require(self._file_identity(path) == observed)
        labels = tuple(_minute(bar.occurred_at) for bar in history.bars)
        _require(all(a < b for a, b in zip(labels, labels[1:])))
        end = bisect_right(labels, query['to'])
        start = max(bisect_left(labels, query['from']), end - query['limit'])
        bars = []
        for index in range(start, end):
            bar = history.bars[index]
            bars.append(dict(symbol=security, minute=labels[index], **{
                field: getattr(bar, field) for field in ('open', 'high', 'low', 'close', 'volume', 'amount')}))
        return dict(metadata=_metadata(history.metadata), bars=bars, coverage='Unknown',
                    missing_minutes=[], selection=dict(period_minutes=1, limit=query['limit']))

    def call(self, request):
        self._check()
        raw = encode_json(request)
        if len(raw) > MAX_REQUEST_BYTES:
            raise MarketProtocolError('来源历史请求超过字节预算')
        request = validate_request(strict_json(raw))
        if request['action'] == 'capabilities':
            unavailable = dict(supported=False, qualification='Unavailable', reason='采集归档只提供历史读取')
            data = dict(source=asdict(self._source), snapshot=dict(unavailable), trading=dict(unavailable),
                        history=dict(supported=True, qualification='DevelopmentVerified',
                                     reason='原WT归档与已有历史合并，逐段来源和实际覆盖见返回值'))
            result = dict(api_version=API_VERSION, status=dict(code='Ok', reason=''), data=data)
        elif request['action'] != 'history.source-query':
            return self._base.call(request)
        else:
            query = request['request']
            security = query['exchange'] + '.' + query['code']
            original = self._base.call(request)
            if security not in self._symbols and not self._supplements:
                return original
            try:
                recent = self._read(security, query) if security in self._symbols else None
                if recent is None and not self._supplements:
                    return original
                batches = [recent] if recent is not None else []
                if original['status']['code'] == 'Ok':
                    batches.append(original['data'])
                for supplement in self._supplements:
                    # 注册表来自原NativeSourceMarket已验证的成功收据；区分未登记与读取失败。
                    if (security, '1m') not in supplement._registered:
                        continue
                    response = supplement.call(request)
                    if response['status']['code'] != 'Ok':
                        return response
                    batches.append(response['data'])
                if not batches:
                    return original
                merged = select_sources(batches, query)
                data = merged if merged is not None else batches[0]
                result = dict(api_version=API_VERSION, status=dict(code='Ok', reason=''), data=data)
            except SourceSelectionConflict:
                result = dict(api_version=API_VERSION, status=dict(code='Unavailable', reason='相同分钟的来源原值冲突'), data={})
            except (OSError, ValueError, IntegrationUnavailable, MarketUnavailable):
                result = dict(api_version=API_VERSION, status=dict(code='Unavailable', reason='原WT采集归档尚未稳定可读'), data={})
        if len(encode_json(result)) > self._maximum:
            raise MarketProtocolError('来源历史响应超过字节预算')
        return validate_response(result, request)

    def close(self):
        if threading.get_ident() != self._owner:
            raise MarketUnavailable('采集归档reader属于创建线程')
        if self._closed:
            return
        failure = None
        owners = [self._base, self._reader, *self._supplements]
        for owner in reversed(owners):
            try:
                if owner is not None:
                    owner.close()
            except BaseException as error:
                # 一个close失败仍释放其余已创建Reader；最终保留原base关闭异常优先级。
                failure = error
        self._reader = self._base = None
        self._supplements = []
        self._closed = True
        if failure is not None:
            raise failure
