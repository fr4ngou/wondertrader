"""采集owner已发布的分钟恢复只读接线；查询不持有生产锁、不访问来源Host。"""
from itertools import chain
from pathlib import Path
import hashlib
import threading
import time

from guanheng_qmt_shm_agent.protocol import canonical, decode
from ..guanheng_market_client import API_VERSION, validate_request, validate_response
from .market_generation import read_fixed
from .source_history_repository import PreparedHistoryRepository, PreparedHistoryReader, recovery_preferences
from .source_history_selection import select_sources, SourceSelectionConflict
from .source_history_transport import SourcePending, require


class RecoveredSourceMarket:
    """创建线程拥有原Reader；只读同一个生产配置及其原子发布收据。"""

    def __init__(self, configuration, *, max_response_bytes=8388608, clock=time.monotonic):
        self.owner = threading.get_ident()  # 原服务线程拥有全部原生对象和关闭。
        self.base = self.reader = None  # 原行情读取与原已发布窗口读取，各沿既有生命周期。
        self.closed = False  # 成功关闭后禁止继续读取。
        self.clock = clock  # 同次读取共用一个绝对截止。
        self.maximum = max_response_bytes  # 原公开服务响应字节上限。
        try:
            require(type(configuration) is dict and set(configuration) == {'mode', 'base', 'producer'}
                    and configuration['mode'] == 'source-recovered')
            descriptor = configuration['producer']
            require(type(descriptor) is dict and set(descriptor) == {'path', 'sha256'}
                    and Path(descriptor['path']).is_absolute())
            producer = decode(read_fixed(descriptor['path'], maximum=16777216, identity=descriptor['sha256']))
            require(type(producer) is dict and set(producer) == {'mode', 'base', 'preparation'}
                    and producer['mode'] == 'source-preparing' and producer['base']['mode'] == 'source-collected'
                    and configuration['base']['mode'] == 'source-collected')
            # 日线消费可保留自己的原目录/文件Reader；分钟数据集和标准Reader须与同一生产者完全一致。
            for key in ('collection', 'minute_native'):
                require(producer['base'][key] == configuration['base'][key])
            c = producer['preparation']
            require(c['enabled'] is True and c['retained_reads'] is True
                    and c['closed_day_recovery'] is True and c['partitioned_receipts'] is True)
            require(type(c['timeout_seconds']) in (int, float) and .1 <= c['timeout_seconds'] <= 30
                    and type(c['max_bytes']) is int and 1 <= c['max_bytes'] <= 67108864
                    and type(c['max_windows']) is int and 1 <= c['max_windows'] <= 1000000)
            root = Path(c['workspace'])
            require(root.is_absolute() and root.drive.upper() == 'E:')
            self.producer = producer  # 仅固定配置及凭据环境变量名称；此读方不加载来源密钥。
            self.identity = hashlib.sha256(canonical(producer)).hexdigest()  # 原准备owner收据身份。
            self.repository = PreparedHistoryRepository(root, self.identity,
                'qmt.source-history-preparation-receipt.v5', c['max_windows'], partitioned=True)
            self.reader = PreparedHistoryReader(producer['base'], c, clock=clock)
            from .source_market import create_native_source_market
            self.base = create_native_source_market(configuration['base'], max_response_bytes=max_response_bytes)
        except BaseException:
            self.close()
            raise

    def call(self, request):
        require(threading.get_ident() == self.owner and not self.closed)
        request = validate_request(decode(canonical(request)))
        if request['action'] != 'history.source-query':
            return self.base.call(request)
        c = self.producer['preparation']
        deadline = self.clock() + c['timeout_seconds']
        def failure(code, reason):
            return dict(api_version=API_VERSION, status=dict(code=code, reason=reason), data={})
        try:
            original, native_batches = self.base.source_batches(request)
            if self.clock() >= deadline:
                raise SourcePending('native base returned after deadline')
            if self.repository.root.exists():
                marker = read_fixed(self.repository.root / 'configuration.json', maximum=c['max_bytes'])
                require(marker == canonical(self.producer))
            candidates, unused = self.repository.find(request['request'], None, deadline=deadline,
                byte_budget=[c['max_bytes']], clock=self.clock)
            prepared = self.reader.batches(candidates, request, deadline)
            data = select_sources(chain(prepared, native_batches),
                request['request'], preferred_ranges=recovery_preferences(candidates))
            if self.clock() >= deadline:
                raise SourcePending('native selection returned after deadline')
            if data is None:
                return original
            require(len(canonical(data)) <= self.maximum)
            return validate_response(dict(api_version=API_VERSION, status=dict(code='Ok', reason=''), data=data), request)
        except SourceSelectionConflict:
            return failure('Conflict', '已发布来源分钟存在不同原值，保留原件待核查')
        except SourcePending:
            return failure('Pending', '原生分钟读取尚待完成，请按原查询重读')
        except (OSError, ValueError, KeyError, TypeError):
            return failure('Unavailable', '分钟恢复收据、固定身份或原生读取未通过')

    def close(self):
        require(threading.get_ident() == self.owner)
        if self.reader is not None:
            self.reader.close()
            self.reader = None
        if self.base is not None:
            self.base.close()
            self.base = None
        self.closed = True
