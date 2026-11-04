"""原准备窗口的只读路由；按证券分目录，价格与成功证明仍在原Importer根。"""
import hashlib
from pathlib import Path
import re
import time

from guanheng_qmt_shm_agent.protocol import canonical, decode
from .market_generation import read_fixed
from .quote_collection_service import _inspect
from .source_history_transport import SourcePending, require
from ..guanheng_market_client import API_VERSION, validate_request


class PreparedHistoryBudget(ValueError):
    """原窗口注册扫描的显式字节预算耗尽，已有源请求和成功根保持。"""


class PreparedHistoryRepository:
    """写入沿原SourcePreparingMarket单owner；读方不取写锁、不提交来源请求。"""
    def __init__(self, root, identity, schema, maximum, *, partitioned=False):
        self.root = Path(root)  # 原持久准备workspace，包含原窗口收据和Importer根。
        self.identity = identity  # 原完整生产配置SHA，防止混用另一准备实例。
        self.schema = schema  # 原窗口收据版本，私有格式迁移使用全新配置根。
        self.maximum = maximum  # 同一owner的窗口数预算，源于显式运行配置。
        self.partitioned = partitioned  # 显式分证券布局；旧平目录保留原合同。

    def directory(self, query):
        selected = {key: query[key] for key in ('exchange', 'code', 'from', 'to')}
        key = hashlib.sha256(canonical(selected)).hexdigest()
        parent = self.root / (query['exchange'] + '.' + query['code']) if self.partitioned else self.root
        return key, parent / key

    def directories(self, query=None):
        if not self.root.exists():
            return
        _inspect(self.root, True)
        if self.partitioned:
            if query is not None:
                parent = self.root / (query['exchange'] + '.' + query['code'])
                parents = [parent] if parent.exists() else []
            else:
                parents = []
                for parent in self.root.iterdir():
                    if parent.name in ('configuration.json', 'owner.lock'):
                        continue
                    require(re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}', parent.name) is not None and parent.is_dir())
                    _inspect(parent, True)
                    parents.append(parent)
        else:
            parents = [self.root]
        count = 0
        for parent in parents:
            _inspect(parent, True)
            for path in parent.iterdir():
                if not self.partitioned and path.name in ('configuration.json', 'owner.lock'):
                    continue
                require(re.fullmatch('[0-9a-f]{64}', path.name) is not None and path.is_dir())
                _inspect(path, True)
                count += 1
                require(count <= self.maximum)
                yield path

    def count(self):
        return sum(1 for unused in self.directories())

    def find(self, query, preferred, *, deadline, byte_budget, clock=time.monotonic):
        """同次读取实际完整收据；只扫描本证券，不把窗口正文复制成第二份价格索引。"""
        candidates, states = [], {}
        for path in self.directories(query):
            receipt = path / 'receipt.json'
            if not receipt.exists():
                continue
            if clock() >= deadline:
                raise SourcePending('source registry deadline')
            _inspect(receipt)
            if receipt.stat().st_size > byte_budget[0]:
                raise PreparedHistoryBudget('source registry bytes')
            raw = read_fixed(receipt, maximum=byte_budget[0])
            byte_budget[0] -= len(raw)
            state = decode(raw)
            require(state['schema'] == self.schema and state['configuration_sha256'] == self.identity)
            selected = state['query']
            require(set(selected) == {'exchange', 'code', 'from', 'to'})
            validate_request(dict(api_version=API_VERSION, action='history.source-query',
                                  request=dict(selected, limit=query['limit'])))
            key, expected = self.directory(selected)
            require(path == expected and key == path.name)
            if key == preferred:
                states[key] = state
            if (selected['exchange'] != query['exchange'] or selected['code'] != query['code']
                    or selected['to'] < query['from'] or selected['from'] > query['to']):
                continue
            if state['published'] is not None:
                candidates.append((key, state))
        return sorted(candidates, key=lambda pair: (pair[0] != preferred, pair[0])), states


def recovery_preferences(candidates):
    """完整日选择仅来自原成功发布证明；默认差异冲突规则继续由原选择器处理。"""
    preferences = []
    for unused, state in candidates:
        value = state['published'].get('reconciled_day')
        if value is not None:
            require(type(value) is dict and set(value) == {'from', 'to', 'dataset_version'}
                    and value['from'] == state['query']['from'] and value['to'] == state['query']['to']
                    and type(value['dataset_version']) is str and value['dataset_version'])
            preferences.append(value)
    return preferences


class PreparedHistoryReader:
    """生产者及公开读方复用同一原生窗口读取；同时只拥有一个窗口Reader。"""

    def __init__(self, base_configuration, preparation, *, clock=time.monotonic):
        self.base_configuration = base_configuration  # 原生产者固定base；只取其原生文件Reader身份。
        self.preparation = preparation  # 原显式窗口与缓存预算，读方不增设业务限制。
        self.clock = clock  # 调用方同一个绝对截止所用时钟。
        self.overlay = None  # 原NativeSourceMarket拥有文件Reader和缓存。
        self.overlay_key = None  # 已打开窗口及其原成功导入身份。

    def select(self, key, published, symbol):
        from .source_market import NativeSourceMarket
        identity = (key, published['root'], published['import_receipt_sha256'])
        if identity == self.overlay_key:
            return
        self.close()
        require(published['count'] <= self.preparation['overlay_cache_bars'])
        security = ('SSE.' if symbol.endswith('.SH') else 'SZSE.') + symbol[:6]
        config = dict(mode='source-store', store_root=published['root'],
                      import_receipt_sha256=published['import_receipt_sha256'],
                      native_reader=self.base_configuration['native_reader'],
                      max_bars=self.preparation['max_rows'],
                      max_cache_bars=self.preparation['overlay_cache_bars'], preload_symbols=[security])
        self.overlay = NativeSourceMarket(config)
        self.overlay_key = identity

    def query(self, request, deadline):
        if self.clock() >= deadline:
            raise SourcePending('source readback deadline')
        result = self.overlay.call(request)
        if self.clock() >= deadline:
            raise SourcePending('source readback returned after deadline')
        return result

    def batches(self, candidates, request, deadline):
        query = request['request']
        symbol = query['code'] + ('.SH' if query['exchange'] == 'SSE' else '.SZ')
        for unused, state in candidates:
            self.select(state['window_id'], state['published'], symbol)
            result = self.query(request, deadline)
            require(result['status']['code'] == 'Ok')
            yield result['data']

    def close(self):
        if self.overlay is not None:
            self.overlay.close()
            self.overlay = None
            self.overlay_key = None
