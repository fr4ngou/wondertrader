"""WT首次运行的当前库存生产者；查询和账本继续由原原生owner负责。"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import ctypes
import math
import os
from pathlib import Path
import re
import time
from types import MappingProxyType
from uuid import uuid4
from zoneinfo import ZoneInfo

from guanheng_market_client import MarketClient

from .account_observation_process import AccountObservationConfig
from .account_scan_runtime import ManagedAccountScan
from .execution_process import ManagedPythonExecutionProcess
from .initial_inventory import _encode, _timestamp, prepare_initial_inventory
from .managed_local_process import _duration, _inspect, _json, _path, _read, _require, _sha


@dataclass(frozen=True)
class InitialInventoryStartupConfig:
    """来源引用和准备根；秘密仍由原连接的环境变量持有，价格单位沿SDK校验。"""
    state_root: Path  # 本次初始准备的E盘绝对目录；由配置指定，首次独占创建，恢复只读复用，不是金融账本根。
    account: AccountObservationConfig  # 当前券商四查询的原部署配置；必填，原Scan owner负责查询及资源关闭。
    market: object  # 只读行情连接配置映射；含地址、令牌环境变量名及秒/字节预算，不保存令牌正文或客户资源。
    max_age_seconds: float  # 当前库存和标价的最大有效时长，单位秒、范围(0,3600]；来自显式配置，不能以0表示未知。
    identity: str  # 完整启动配置规范字节的SHA256；绑定准备输入及恢复，必填，不代表事实新鲜度。
    capital: object = None  # 可选只读当前资本声明：total_cny单位CNY且含库存、source为来源；None保持原模板资本语义。

    @classmethod
    def from_dict(cls, value):
        _require(type(value) is dict and {
            'schema', 'state_root', 'account_observation', 'market', 'max_age_seconds'}
            <= set(value) <= {'schema', 'state_root', 'account_observation', 'market', 'max_age_seconds', 'capital'}
            and value['schema'] == 'guanheng.initial-inventory-start.v1')
        source, market = value['account_observation'], value['market']
        _require(type(source) is dict and set(source) == {'descriptor', 'sha256'}
            and type(market) is dict and set(market) == {
                'base_url', 'token_env', 'timeout_seconds', 'max_response_bytes'})
        account = AccountObservationConfig.from_path(source['descriptor'], source['sha256'])
        state_root = _path(value['state_root'], e_drive=True)
        _inspect(state_root.parent, directory=True)
        _require(type(market['token_env']) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', market['token_env']))
        # 原SDK构造只核地址/预算；配置阶段不访问网络或读取秘密。
        MarketClient(market['base_url'], 'configuration-only', timeout=market['timeout_seconds'],
                     max_response_bytes=market['max_response_bytes'])
        age = _duration(value['max_age_seconds'], 3600)
        from .strategy_capital import current_capital
        capital = None if 'capital' not in value else current_capital(value['capital'])
        return cls(state_root, account, MappingProxyType(dict(market)), age, sha256(_encode(value)).hexdigest(),
                   None if capital is None else MappingProxyType(capital))


class _PreparationStopped(Exception):
    """原停止Event已生效；控制权回到原监督者，不授原生ready或clean。"""


def _present(row, key):
    item = row['facts'][key]
    _require(type(item) is dict and item.get('availability') == 'present' and item.get('value') is not None)
    return item['value']


def _quantity(value):
    _require(type(value) in (int, float) and 0 <= value <= 10**12 and math.isfinite(value) and int(value) == value)
    return int(value)


class InitialInventoryExecutionProcess(ManagedPythonExecutionProcess):
    """原监督线程先准备一次输入，再启动原子进程；重启复用已确认的基准。

    Scan的Job/reader继续由ManagedAccountScan持有，原执行Job/clean继续由父类
    持有。request_close使用同一停止Event；有未回收Scan时，pending和close保持
    未完成，后续close沿原停止截止续核。准备根只保存原输入和来源身份。
    """
    def __init__(self, config, inventory, *, scanner=None, **options):
        super().__init__(config, **options)
        self.inventory = inventory
        self._scanner = scanner or ManagedAccountScan(clock=self._clock)
        self._inventory_state = 'new'
        self._scan_start_claimed = self._inventory_close_confirmed = False

    def status(self):
        value = super().status()
        with self._condition:
            value['inventory_state'] = self._inventory_state
        value['pending'] = value['pending'] or self._scanner.pending
        return value

    def _reap(self, deadline):
        scan = self._scanner.reap(deadline)
        process = super()._reap(deadline)
        return scan and process

    def close(self, timeout=2.0):
        closed = super().close(timeout)
        # 原执行Job的_reaped独立于准备Scan；每次close都续核同一Scan owner。
        with self._condition:
            deadline = self._stop_deadline if self._stop_deadline is not None else self._clock()
        scan = self._scanner.reap(deadline)
        with self._condition:
            # Scan也是本owner已准入的子作业；及时关闭资格沿首次stop D确认一次。
            # 晚回收仍释放资源，随后空Scan的reap不能补授原截止内完成。
            deadline = min(deadline, self._stop_deadline) if self._stop_deadline is not None else deadline
            expired = self._scan_start_claimed and not self._inventory_close_confirmed and self._clock() >= deadline
            if closed and scan and not expired:
                self._inventory_close_confirmed = self._scan_start_claimed
                return True
        if expired:
            self._failure('stop_timeout')
        return False

    def _inventory_check(self, deadline):
        self._check(deadline)
        if self._stop.is_set():
            raise _PreparationStopped()

    def _write(self, path, raw, deadline):
        self._inventory_check(deadline)
        with path.open('xb') as stream:
            _require(stream.write(raw) == len(raw))
            stream.flush(); os.fsync(stream.fileno())
        _require(_read(path, 20*1024*1024, clock=self._clock, deadline=deadline) == raw)
        self._inventory_check(deadline)

    def _current_facts(self, native, deadline):
        from guanheng_strategy_v1 import SYMBOLS
        settings = self.inventory
        scan = settings.account.scan
        trader = native['trader']
        _require(scan.account == trader['expected_account'] and scan.environment == trader['environment']
                 and trader['currency'] == 'CNY' and trader['profile'] == 'cny_cash_shsz_v1')
        for name, digest in settings.account.native_sha256:
            raw = _read(settings.account.installation/name, 64*1024*1024, clock=self._clock, deadline=deadline)
            _require(sha256(raw).hexdigest() == digest)
        with self._condition:
            self._inventory_check(deadline)
            self._scan_start_claimed = True
        result = self._scanner.run(scan, str(uuid4()), min(deadline, self._clock()+scan.total_seconds), self._stop)
        self._inventory_check(deadline)
        _require(result.complete and not self._scanner.pending and result.close['status'] == 'complete')
        observed = result.observation
        # 原Scan已经核运输/原生映射。这里仅提取初始库存所需的已知事实，不投影账本。
        summary, rows = observed['summary'], observed['rows']
        _require(summary['source_kind'] == 'qmt_shm_bound' and summary['observation_qualified'] is True)
        now = datetime.now(timezone.utc)
        until = now+timedelta(seconds=settings.max_age_seconds)
        for batch in summary['batches']:
            source = batch['source']
            _require(batch['delivered'] is True and source['account_id'] == scan.account
                     and source['account_environment'] == scan.environment)
            finished = _timestamp(batch['execution_finished_at'])
            _require(finished <= now < finished+timedelta(seconds=settings.max_age_seconds))
            until = min(until, finished+timedelta(seconds=settings.max_age_seconds))
        _require(len(rows['account']) == 1)
        for key in ('m_dBalance', 'm_dAvailable'):
            value = _present(rows['account'][0], key)
            _require(type(value) in (int, float) and math.isfinite(value))
        positions = {}
        for row in rows['position']:
            quantity = _quantity(_present(row, 'm_nVolume'))
            sellable = _quantity(_present(row, 'm_nCanUseVolume'))
            _require(sellable <= quantity)
            exchange, code = _present(row, 'm_strExchangeID'), _present(row, 'm_strInstrumentID')
            _require(exchange in ('SH', 'SZ') and type(code) is str and re.fullmatch(r'[0-9]{6}', code))
            symbol = code+'.'+exchange
            if not quantity:
                continue
            _require(symbol in SYMBOLS and symbol not in positions)
            positions[symbol] = dict(symbol=symbol, quantity=quantity, sellable=sellable)
        if positions:
            market = settings.market
            remaining = deadline-self._clock()
            self._inventory_check(deadline)
            client = MarketClient(market['base_url'], os.environ[market['token_env']],
                timeout=min(market['timeout_seconds'], remaining), max_response_bytes=market['max_response_bytes'])
            codes = [('SSE' if s.endswith('.SH') else 'SZSE')+'.'+s[:6] for s in sorted(positions)]
            response = client.quotes_query(codes)
            self._inventory_check(deadline)
            _require(response['status']['code'] == 'Ok')
            data = response['data']
            _require(data['metadata']['qualification'] in ('NativeVerified', 'ProductionQualified'))
            now = datetime.now(timezone.utc)
            for row in data['snapshots']:
                symbol = row['symbol'].split('.')[1]+('.SH' if row['symbol'].startswith('SSE.') else '.SZ')
                stamp = datetime.strptime(str(row['date'])+f"{row['action_time']//1000:06d}", '%Y%m%d%H%M%S')
                stamp = stamp.replace(tzinfo=ZoneInfo('Asia/Shanghai'), microsecond=row['action_time']%1000*1000)
                _require(stamp <= now < stamp+timedelta(seconds=settings.max_age_seconds))
                until = min(until, stamp+timedelta(seconds=settings.max_age_seconds))
                positions[symbol].update(mark_price=row['price'],
                    mark_source_sha256=sha256(_encode(dict(metadata=data['metadata'], snapshot=row))).hexdigest())
        now = datetime.now(timezone.utc)
        api = ctypes.WinDLL('kernel32');api.GetTickCount64.restype = ctypes.c_ulonglong
        uptime = api.GetTickCount64()
        _require(now < until)
        # 初始账本会话日由原生加载owner沿WT日历取得，券商日期已知性留在原观察。
        facts = dict(schema='guanheng.initial-inventory-facts.v2', broker_source_sha256=sha256(_encode(observed)).hexdigest(),
            captured_at=now.isoformat(), valid_until=until.isoformat(), captured_uptime_ms=uptime,
            valid_until_uptime_ms=uptime+int((until-now).total_seconds()*1000),
            positions=[positions[s] for s in sorted(positions)])
        return facts, now, uptime

    def _validate_inputs(self, deadline):
        super()._validate_inputs(deadline)
        try:
            self._prepare_inputs(deadline)
        except _PreparationStopped:
            self._inventory_state = 'stopped_before_execution'

    def _prepare_inputs(self, deadline):
        self._inventory_check(deadline)
        raw = _read(self.config.configuration, 256*1024, clock=self._clock, deadline=deadline)
        _require(sha256(raw).hexdigest() == self.config.configuration_sha256)
        native = _json(raw)
        _require(self.config.recovery_mode in ('record_clean', 'resume_clean', 'resume_reconciled') and 'takeover' not in native)
        from .execution_recovery import market_origin_configuration
        identity = dict(market_origin_configuration(native,deadline=deadline));identity.pop('recovery')
        origin = sha256(_encode(dict(configuration=identity, startup=self.inventory.identity))).hexdigest()
        root = self.inventory.state_root
        if self.config.recovery_mode in ('resume_clean', 'resume_reconciled'):
            _inspect(root, directory=True)
            receipt = _json(_read(root/'BASELINE.json', 65536, clock=self._clock, deadline=deadline))
            _require(set(receipt) == {'schema', 'origin_sha256', 'baseline_at', 'source_sha256', 'files'}
                and receipt['schema'] == 'guanheng.initial-inventory-started-input.v1' and receipt['origin_sha256'] == origin)
            files = receipt['files']
            _require(type(files) is dict and set(files) in (
                {'runtime-input.json', 'CURRENT-FACTS.json'}, {'runtime-input.json', 'CURRENT-FACTS.json', 'native-input.json'}))
            for name, digest in files.items():
                _require(sha256(_read(root/name, 20*1024*1024, clock=self._clock, deadline=deadline)).hexdigest() == _sha(digest))
            self._inventory_state = 'reused'
        else:
            from guanheng_strategy_core.contracts import EvaluationBudget
            from .execution_configured import RetainedRuntimeInput
            from .retained_evaluation import evaluate_retained
            self._inventory_state = 'reading_current_facts'
            parameters = native['strategies'][0]['parameters']['python_strategy']
            template_raw = _read(_path(parameters['input_file']), 16*1024*1024, clock=self._clock, deadline=deadline)
            _require(sha256(template_raw).hexdigest() == _sha(parameters['input_sha256']))
            facts, now, uptime = self._current_facts(native, deadline)
            prepared = prepare_initial_inventory(RetainedRuntimeInput.from_dict(_json(template_raw)), facts,
                now=now, uptime_ms=uptime, capital=None if self.inventory.capital is None else dict(self.inventory.capital))
            value = RetainedRuntimeInput.from_dict(_json(prepared.runtime_input))
            self._inventory_check(deadline)
            evaluate_retained(value.request, value.policy, budget=EvaluationBudget(max_seconds=min(5, deadline-self._clock())))
            self._inventory_check(deadline);_inspect(root.parent, directory=True);root.mkdir();_inspect(root, directory=True)
            contents = {'runtime-input.json': prepared.runtime_input, 'CURRENT-FACTS.json': _encode(facts)}
            if prepared.native_input is not None:
                contents['native-input.json'] = prepared.native_input
            files = {}
            for name, data in contents.items():
                self._write(root/name, data, deadline);files[name] = sha256(data).hexdigest()
            receipt = dict(schema='guanheng.initial-inventory-started-input.v1', origin_sha256=origin,
                baseline_at=prepared.baseline_at.isoformat(), source_sha256=prepared.source_sha256, files=files)
            self._write(root/'BASELINE.json', _encode(receipt), deadline)
            self._inventory_state = 'prepared'
        self._inventory_check(deadline)
        parameters = native['strategies'][0]['parameters']['python_strategy']
        parameters.update(input_file=str(root/'runtime-input.json'), input_sha256=files['runtime-input.json'])
        if self.inventory.capital is not None:
            account = self.inventory.account
            parameters['capital_account'] = dict(path=str(account.control_root/'current.json'),
                config_sha256=account.scan.configuration_sha256, account=account.scan.account,
                environment=account.scan.environment)
            # 首次只读估值沿同一已声明快照来源；旧持仓基准和交易计算触发保持原owner。
            parameters['capital_market'] = dict(self.inventory.market,
                max_age_seconds=self.inventory.max_age_seconds)
            quotes=native.get('market_input_origin',{}).get('quotes')
            if quotes is not None:parameters['capital_market']=dict(quotes)
        if 'native-input.json' in files:
            native['takeover'] = dict(input_file=str(root/'native-input.json'), input_sha256=files['native-input.json'])
        effective = self._directory/'execution.json'
        body = _encode(native);self._write(effective, body, deadline)
        # 原父监督者与子进程共享实际配置SHA，原clean继续核去掉recovery后的同一配置。
        self.config = replace(self.config, native=replace(self.config.native,
            configuration=effective, configuration_sha256=sha256(body).hexdigest()))
