"""独立WT进程所有者：配置身份、组件依赖及有界启动/关闭。

本层只组合已有组件，不计算仓位、不重发委托、不解释券商金融数据。
各组件的ready仅证明自己的监听/初始化；来源、数据和交易资格继续由原接口表达。
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import threading
import time
from uuid import UUID

from .managed_local_process import _duration, _json, _path, _read, _require, _sha


_ORDER = ('host', 'trade_host', 'account_host', 'analysis_host', 'analysis_batch_host', 'account_observation',
          'history', 'collection', 'analysis_window', 'execution')
_KINDS = {'host': ('qmt_read', 'qmt_history_preparation'),
          'trade_host': ('qmt_trade',),
          # HPR与账户查询各用原Host；同一WT拥有它们，观衡只消费账户结果。
          'account_host': ('qmt_read',),
          'analysis_host': ('qmt_read',),
          # 单证券分析与批量市场分析各用原配对，省略批量组件时原顺序保持。
          'analysis_batch_host': ('qmt_read',),
          'account_observation': ('native_account_observation',),
          'history': ('source_market',), 'collection': ('quote_collection',),
          'analysis_window': ('analysis_window',),
          'execution': ('execution',)}


@dataclass(frozen=True)
class ComponentConfig:
    """原部署descriptor及原字节SHA；kind选择固定组件，不接受代码入口注入。"""
    kind: str  # 已登记组件工厂类型；来自运行配置的非空标识，不接受任意代码入口。
    descriptor: str  # 该组件部署描述的绝对文件路径；来自运行配置，必填，组件owner按其协议消费。
    sha256: str  # 部署描述原字节SHA256；由配置提供，必填，用于绑定已审材料，不代表运行状态。
    wait_for_source: bool = False  # 执行组件是否等待原来源就绪；默认False沿原启动方式，仅execution可显式启用。

    def __post_init__(self):
        _path(self.descriptor)
        _sha(self.sha256)
        _require(type(self.wait_for_source) is bool
                 and (not self.wait_for_source or self.kind == 'execution'))


@dataclass(frozen=True)
class RuntimeConfig:
    """唯一运行实例的不可变配置；启动/关闭预算为整套组件共享秒数。"""
    instance_id: str  # 运行实例的规范UUID文本；来自显式配置，必填，跨正常重启保持同一实例身份。
    components: tuple[tuple[str, ComponentConfig], ...]  # 按固定依赖序排列的(组件名,配置)不可变元组；必填，实际进程归Runtime拥有。
    startup_seconds: float  # 整套组件共享的启动预算，单位秒、范围(0,600]；来自配置，不能按组件重复计时。
    stop_seconds: float  # 整套组件共享的关闭预算，单位秒、范围(0,120]；来自配置，0或缺失不表示无限等待。

    def __post_init__(self):
        _require(type(self.instance_id) is str and str(UUID(self.instance_id)) == self.instance_id)
        _duration(self.startup_seconds, 600)
        _duration(self.stop_seconds, 120)
        _require(type(self.components) is tuple and 1 <= len(self.components) <= len(_ORDER))
        names = []
        for name, component in self.components:
            _require(name in _KINDS and type(component) is ComponentConfig
                     and component.kind in _KINDS[name])
            names.append(name)
        _require(tuple(names) == tuple(name for name in _ORDER if name in names))
        # 四查询发布依赖本实例的账户通信；先核配置，避免启动缺来源的半套组件。
        # 未声明发布组件的旧配置继续使用原相对顺序及原工厂。
        _require('account_observation' not in names or 'account_host' in names)
        # 策略窗口的来源通信也归本 WT；页面和执行器只消费已发布窗口。
        _require('analysis_window' not in names or 'analysis_host' in names)
        _require(not any(component.wait_for_source for _, component in self.components)
                 or 'trade_host' in names)

    @classmethod
    def from_path(cls, path, expected_sha256):
        """校验64KiB以内配置和SHA，返回纯值；不创建进程、不读取秘密或改运行状态。"""
        raw = _read(_path(path), 65536)
        _require(hashlib.sha256(raw).hexdigest() == _sha(expected_sha256))
        value = _json(raw)
        _require(set(value) == {'schema', 'instance_id', 'components', 'startup_seconds', 'stop_seconds'}
                 and value['schema'] == 'guanheng.wt-runtime.v1')
        components = value['components']
        _require(type(components) is dict and components and set(components) <= set(_ORDER))
        selected = []
        for name in _ORDER:
            if name in components:
                item = components[name]
                _require(type(item) is dict and {'kind', 'descriptor', 'sha256'} <= set(item)
                         <= {'kind', 'descriptor', 'sha256', 'wait_for_source'})
                _require('wait_for_source' not in item or name == 'execution')
                selected.append((name, ComponentConfig(**item)))
        return cls(value['instance_id'], tuple(selected), value['startup_seconds'], value['stop_seconds'])


def create_process(component):
    """固定工厂；执行适配由执行模块交付，缺模块/坏descriptor直接拒绝启动。"""
    if component.kind == 'execution':
        from .execution_process import create_process as execution_process
        return execution_process(component.descriptor, component.sha256)
    if component.kind == 'qmt_read':
        from .qmt_host_process import HostProcessConfig, QmtHostProcess
        return QmtHostProcess(HostProcessConfig.from_path(component.descriptor, component.sha256))
    if component.kind == 'qmt_history_preparation':
        from .history_preparation_process import HistoryPreparationProcessConfig, HistoryPreparationProcess
        return HistoryPreparationProcess(HistoryPreparationProcessConfig.from_path(component.descriptor, component.sha256))
    if component.kind == 'qmt_trade':
        # 交易与历史补齐各保留原owner；选择交易通信不会挤掉既有HPR通道。
        from .trade_host_process import create_process as trade_host_process
        return trade_host_process(component.descriptor, component.sha256)
    if component.kind == 'native_account_observation':
        from .account_observation_process import create_process as account_observation_process
        return account_observation_process(component.descriptor, component.sha256)
    if component.kind == 'source_market':
        from .source_market_process import SourceMarketProcessConfig, SourceMarketProcess
        return SourceMarketProcess(SourceMarketProcessConfig.from_path(component.descriptor, component.sha256))
    if component.kind == 'quote_collection':
        from .quote_collection_process import QuoteCollectionProcessConfig, QuoteCollectionProcess
        return QuoteCollectionProcess(QuoteCollectionProcessConfig.from_path(component.descriptor, component.sha256))
    if component.kind == 'analysis_window':
        from .analysis_window_process import create_process as analysis_window_process
        return analysis_window_process(component.descriptor, component.sha256)
    raise ValueError('invalid WT component kind')


class Runtime:
    """每组件一个owner；调用者串行start/close，request_close可来自信号或控制线程。

    status只读取安全DTO，不向来源发请求。初始化先验证全部组件，启动失败仍由本对象
    逆依赖关闭已经启动的组件。失败及未知结果保留原组件状态，不自动构造第二代进程。
    """
    def __init__(self, config, *, factory=create_process, clock=time.monotonic):
        _require(type(config) is RuntimeConfig)
        self.config, self._clock = config, clock
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._attempted, self._state, self._error = False, 'new', None
        self._stop_deadline = None
        # 工厂构造仅验证配置。全部成功后才允许任何start，避免缺执行模块时先启动半套服务。
        owners, capital_accounts, observation = [], [], None
        for name, component in config.components:
            owner = factory(component)
            if name == 'account_observation':
                observation = getattr(owner, 'config', None)
            inventory = getattr(owner, 'inventory', None)
            if inventory is not None and inventory.capital is not None:
                capital_accounts.append(inventory.account)
            if component.wait_for_source:
                from .execution_source_wait import SourceWaitingExecution, TradeSourceProbe
                owner = SourceWaitingExecution(owner, TradeSourceProbe(component.descriptor, component.sha256))
            owners.append((name, owner))
        for account in capital_accounts:
            _require(observation is not None and observation.control_root == account.control_root
                     and observation.scan.configuration_sha256 == account.scan.configuration_sha256)
        self._owners = tuple(owners)

    def status(self):
        """返回组件公开状态的值快照；PID/ready描述进程，qmt_connection沿组件原语义。"""
        with self._lock:
            components = {name: owner.status() for name, owner in self._owners}
            return {'schema': 'guanheng.wt-runtime-status.v1', 'instance_id': self.config.instance_id,
                    'state': self._state, 'error_code': self._error,
                    'ready': self._state == 'ready' and not self._stop.is_set(),
                    'components': components}

    def start(self, deadline):
        """沿绝对monotonic截止依次启动；失败由调用者finally调用close收口。"""
        _require(type(deadline) in (int, float) and math.isfinite(deadline))
        with self._lock:
            if self._attempted or self._stop.is_set():
                return False
            self._attempted, self._state = True, 'starting'
        end = min(deadline, self._clock() + self.config.startup_seconds)
        for name, owner in self._owners:
            if self._stop.is_set() or self._clock() >= end or not owner.start(end):
                with self._lock:
                    self._state, self._error = 'faulted', 'component_start_' + name
                return False
        with self._lock:
            if self._stop.is_set() or self._clock() >= end:
                self._state, self._error = 'faulted', 'startup_interrupted'
                return False
            self._state = 'ready'
        return True

    def check(self):
        """只查原owner状态；组件自行故障时停止整套依赖，保留有限错误码。"""
        for name, owner in self._owners:
            status = owner.status()
            if not status['ready'] or status.get('error_code') is not None:
                with self._lock:
                    self._state, self._error = 'faulted', 'component_runtime_' + name
                return False
        return True

    def request_close(self):
        """只通知本运行owner；组件停机由close按逆依赖执行。"""
        self._stop.set()

    def wait_close_request(self, timeout):
        """等待内存停止通知，秒数由监督循环给出；返回True只表示收到请求。"""
        _require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 120)
        return self._stop.wait(timeout)

    def close(self, timeout):
        """共用首次关闭截止，先执行/采集再历史/Host；全部实际关闭才返回True。"""
        _require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 120)
        self._stop.set()
        with self._lock:
            if self._state == 'closed':
                return True
            end = self._clock() + min(timeout, self.config.stop_seconds)
            self._stop_deadline = min(end, self._stop_deadline) if self._stop_deadline is not None else end
            end = self._stop_deadline
            self._state = 'stopping'
        success = True
        for name, owner in reversed(self._owners):
            try:
                owner.request_close()
                closed = owner.close(max(0, end - self._clock()))
            except Exception:
                closed = False
            if not closed:
                success = False
                with self._lock:
                    self._error = self._error or 'component_close_' + name
        with self._lock:
            self._state = 'closed' if success else 'faulted'
        return success
