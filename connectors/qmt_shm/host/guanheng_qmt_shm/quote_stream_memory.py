"""QST及HPR组合正文的唯一离线生成实现；默认正文保持原字节。"""
from __future__ import annotations
import hashlib
from pathlib import Path
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.quote_stream_contract import validate_settings
from .memory_runtime import _prepare_runtime
from .pair import _render_memory_entry
from .private_files import create_private_directory, write_private_new

CALLBACKS = '''import threading as _threading
from guanheng_qmt_shm_agent.quote_stream import QuoteStreamAgent as _Agent
_agent, _context, _thread = None, None, None

def init(ContextInfo):
    global _agent, _context, _thread
    if _context is not None:
        raise RuntimeError("quote entry has one native context generation")
    _context, _thread = ContextInfo, _threading.get_ident()
    _agent = _Agent(ContextInfo, settings=_settings)
    _agent.start()

def _check(ContextInfo):
    if ContextInfo is not _context or _threading.get_ident() != _thread or _agent is None:
        raise RuntimeError("quote entry requires its original strategy context/thread")

def agent_tick(ContextInfo):
    _check(ContextInfo)
    return _agent.status()

def handlebar(ContextInfo):
    _check(ContextInfo)

def stop(ContextInfo):
    _check(ContextInfo)
    return _agent.request_close()
'''


COMBINED_CALLBACKS = '''import threading as _threading
from datetime import datetime as _datetime, timedelta as _timedelta
from guanheng_qmt_shm_agent.quote_stream import QuoteStreamAgent as _QuoteAgent
from guanheng_qmt_shm_agent.history_preparation_agent import ReconnectingHistoryPreparationAgent as _PreparationAgent
_quote, _preparation, _context, _thread = None, None, None, None

def _check(ContextInfo):
    if ContextInfo is not _context or _threading.get_ident() != _thread:
        raise RuntimeError("market entry requires its original strategy context/thread")

def _request_close():
    # 两个owner都收到停止；一个失败仍收束另一项，资源确认沿各自原实现。
    failure = None
    for owner in (_quote, _preparation):
        if owner is not None:
            try:
                owner.request_close()
            except BaseException as error:
                if failure is None:
                    failure = error
    if failure is not None:
        raise failure

def init(ContextInfo):
    global _quote, _preparation, _context, _thread
    if _context is not None:
        raise RuntimeError("market entry has one native context generation")
    _context, _thread = ContextInfo, _threading.get_ident()
    try:
        _quote = _QuoteAgent(ContextInfo, settings=_settings['quotes'])
        _preparation = _PreparationAgent(ContextInfo,
            trusted_bootstrap=_settings['preparation'], enabled=True,
            download_history_data=globals().get('download_history_data'),
            reconnect_seconds=_settings['preparation_reconnect_seconds'])
        ContextInfo.run_time("agent_tick", "1nSecond",
            (_datetime.now()+_timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"))
        _quote.start()
        _preparation.start()
    except BaseException as primary:
        try:
            _request_close()
        except BaseException as cleanup:
            # 启动根因仍是外层异常；关闭失败作为cause保留，两个owner均已尝试。
            raise primary from cleanup
        raise

def agent_tick(ContextInfo):
    _check(ContextInfo)
    if _preparation is None:
        raise RuntimeError("market preparation owner is not initialized")
    return _preparation.tick()

def handlebar(ContextInfo):
    _check(ContextInfo)

def stop(ContextInfo):
    _check(ContextInfo)
    return _request_close()
'''


DIAGNOSTIC_CALLBACKS = '''import threading as _threading
import time as _time
import math as _math
import json as _json
from guanheng_qmt_shm_agent.quote_stream import QuoteStreamAgent as _Agent
_agent, _context, _thread, _diag = None, None, None, None
_SAMPLES = ('600000.SH', '000001.SZ', '510300.SH')

def _source_time(value):
    # 仅记录源数值；有界整数避免诊断JSON放大，不换算或推导行情时间。
    if type(value) not in (int, float) or not 0 <= value <= 2 ** 53:
        return None
    return value if _math.isfinite(value) else None

class _Diagnostics(object):
    def __init__(self):
        # SDK回调只改本锁下的固定大小纯值；owner读副本后才查询SDK/打印。
        self.lock = _threading.Lock()
        self.last_emit = self.last_query = None
        self.state = dict(callbacks_entered=0, callbacks_completed=0,
            callback_failures=0, raw_rows=0, raw_time_rows=0,
            last_entry_wall_ms=None, last_entry_monotonic_s=None,
            last_completed_entry_wall_ms=None, last_completed_entry_monotonic_s=None,
            last_completed_sdk_max_time_ms=None,
            last_exit_monotonic_s=None, last_sdk_max_time_ms=None,
            maximum_sdk_time_ms=None, last_entry_source_age_ms=None,
            last_diagnostic_prefix_ms=None, last_agent_on_quote_ms=None,
            maximum_agent_on_quote_ms=0.0, last_callback_total_ms=None,
            maximum_callback_total_ms=0.0, snapshot_calls=0,
            snapshot_failures=0, last_snapshot_before_wall_ms=None,
            last_snapshot_after_wall_ms=None, last_snapshot_elapsed_ms=None,
            last_snapshot_times=dict((symbol, None) for symbol in _SAMPLES),
            last_snapshot_error=None, print_failures=0)

    def entry(self, data):
        entered, wall = _time.monotonic(), int(_time.time() * 1000)
        rows, time_rows, maximum = 0, 0, None
        if type(data) is dict:
            rows = len(data)
            for row in data.values():
                stamp = _source_time(row.get('time')) if type(row) is dict else None
                if stamp is not None:
                    time_rows += 1
                    maximum = stamp if maximum is None else max(maximum, stamp)
        with self.lock:
            state = self.state
            state['callbacks_entered'] += 1
            state['raw_rows'] += rows
            state['raw_time_rows'] += time_rows
            state['last_entry_wall_ms'] = wall
            state['last_entry_monotonic_s'] = entered
            state['last_sdk_max_time_ms'] = maximum
            state['last_entry_source_age_ms'] = None if maximum is None else wall - maximum
            if maximum is not None:
                previous = state['maximum_sdk_time_ms']
                state['maximum_sdk_time_ms'] = maximum if previous is None else max(previous, maximum)
        return entered, wall, maximum

    def callback(self, original, data):
        # 诊断失败仍恰好交付一次原回调；原回调异常保持原样向SDK传播。
        entered = None
        try:
            entered = self.entry(data)
        except Exception:
            pass
        started, failed = _time.monotonic(), False
        try:
            return original(data)
        except BaseException:
            failed = True
            raise
        finally:
            try:
                finished = _time.monotonic()
                # 原on_quote整体耗时含其自身Condition锁等待；不冒充纯计算耗时。
                agent_ms = max(0.0, (finished - started) * 1000)
                with self.lock:
                    state = self.state
                    state['callbacks_completed'] += 1
                    state['callback_failures'] += int(failed)
                    state['last_exit_monotonic_s'] = finished
                    state['last_agent_on_quote_ms'] = agent_ms
                    state['maximum_agent_on_quote_ms'] = max(state['maximum_agent_on_quote_ms'], agent_ms)
                    if entered is not None:
                        entry_mono, entry_wall, source_max = entered
                        # 并发回调的最后入场和最后完成可能不同，单独保存完成者入口配对。
                        state['last_completed_entry_wall_ms'] = entry_wall
                        state['last_completed_entry_monotonic_s'] = entry_mono
                        state['last_completed_sdk_max_time_ms'] = source_max
                        total_ms = max(0.0, (finished - entry_mono) * 1000)
                        state['last_diagnostic_prefix_ms'] = max(0.0, (started - entry_mono) * 1000)
                        state['last_callback_total_ms'] = total_ms
                        state['maximum_callback_total_ms'] = max(state['maximum_callback_total_ms'], total_ms)
            except Exception:
                pass

    def observe(self, context, stage):
        # 原owner同步查询同一全推缓存；不建SDK线程/定时器，不在SDK回调查询。
        now = _time.monotonic()
        if self.last_query is None or now - self.last_query >= 60.0:
            self.last_query = now
            before, wall = _time.monotonic(), int(_time.time() * 1000)
            times, error = dict((symbol, None) for symbol in _SAMPLES), None
            with self.lock:
                self.state['snapshot_calls'] += 1
            try:
                values = context.get_full_tick(list(_SAMPLES))
                if type(values) is not dict:
                    error = 'invalid_shape'
                else:
                    for symbol in _SAMPLES:
                        row = values.get(symbol)
                        if type(row) is dict:
                            times[symbol] = _source_time(row.get('time'))
            except Exception:
                # SDK错误文本可能含账户/路径；只保留固定类别。
                error = 'sdk_error'
            with self.lock:
                state = self.state
                state['snapshot_failures'] += int(error is not None)
                state['last_snapshot_before_wall_ms'] = wall
                state['last_snapshot_after_wall_ms'] = int(_time.time() * 1000)
                state['last_snapshot_elapsed_ms'] = max(0.0, (_time.monotonic() - before) * 1000)
                state['last_snapshot_times'] = times
                state['last_snapshot_error'] = error
        now = _time.monotonic()
        if self.last_emit is not None and now - self.last_emit < 10.0:
            return
        self.last_emit = now
        with self.lock:
            value = dict(self.state)
        value.update(schema_version='qmt.quote-diagnostics.v1', stage=stage,
            observed_wall_ms=int(_time.time() * 1000), observed_monotonic_s=now)
        try:
            print('GH_QST_DIAG ' + _json.dumps(value, sort_keys=True,
                separators=(',', ':'), ensure_ascii=True, allow_nan=False))
        except Exception:
            # 既有stdout不可用时保持原报价工作和打印节流，不重试占用策略线程。
            with self.lock:
                self.state['print_failures'] += 1

class _ContextProxy(object):
    def __init__(self, context, diagnostics):
        self.context, self.diagnostics = context, diagnostics

    def subscribe_whole_quote(self, markets, callback):
        def measured(data):
            return self.diagnostics.callback(callback, data)
        return self.context.subscribe_whole_quote(markets, measured)

    def unsubscribe_quote(self, token):
        return self.context.unsubscribe_quote(token)

def _check(ContextInfo):
    if ContextInfo is not _context or _threading.get_ident() != _thread or _agent is None:
        raise RuntimeError("quote entry requires its original strategy context/thread")

def init(ContextInfo):
    global _agent, _context, _thread, _diag
    if _context is not None:
        raise RuntimeError("quote entry has one native context generation")
    _context, _thread, _diag = ContextInfo, _threading.get_ident(), _Diagnostics()
    _agent = _Agent(_ContextProxy(ContextInfo, _diag), settings=_settings)
    _agent.start()
    _diag.observe(ContextInfo, 'init')

def agent_tick(ContextInfo):
    _check(ContextInfo)
    _diag.observe(ContextInfo, 'agent_tick')
    return _agent.status()

def handlebar(ContextInfo):
    _check(ContextInfo)
    _diag.observe(ContextInfo, 'handlebar')

def stop(ContextInfo):
    _check(ContextInfo)
    return _agent.request_close()
'''


def render_strategy(settings, *, agent_root, sdk_metadata, license_bytes, diagnostics=False,
                    history_bootstrap=None, history_reconnect_seconds=1.0, input_reader=None):
    """返回ASCII正文及源闭包身份；可选诊断或历史补齐由显式输入选择。

    diagnostics缺省保持既有正文/身份字段；启用后只记录有界时间与计数，
    SDK查询仍由原策略owner调用。history_bootstrap将下载能力装配到同一
    条目，沿独立认证SHM和有界原队列，不扩展文件、网络或交易入口。
    """
    if type(diagnostics) is not bool:
        raise ValueError('diagnostics must be explicit bool')
    admitted = validate_settings(settings)
    if history_bootstrap is not None:
        if diagnostics:
            raise ValueError('select quote diagnostics or combined preparation explicitly')
        from guanheng_qmt_shm_agent.history_preparation import validate_configuration
        from guanheng_qmt_shm_agent.read_capabilities import FULL_TICK, HISTORY
        from guanheng_qmt_shm_agent.history_preparation import OPERATION
        from guanheng_qmt_shm_agent.transport_profile import validate_transport_profile
        from guanheng_qmt_shm.lifecycle import validate_connection_lifecycle
        history = validate_configuration(history_bootstrap)
        lifecycle = validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
            mode='resident-read', reconnect_seconds=history_reconnect_seconds))
        if (set(history.profile['read_operations']) - {FULL_TICK, HISTORY, OPERATION}
                or history.value['transport']['kind'] != 'builtin-shm'
                or admitted['transport']['windows_session_id'] != history.value['transport']['windows_session_id']):
            raise ValueError('combined preparation requires market-only scope in the same Windows session')
        quote_layout = validate_transport_profile(admitted['transport'], admitted['route'],
            admitted['max_frame'], admitted['profile'])
        history_layout = validate_transport_profile(history.value['transport'], history.route,
            history.value['max_frame'], history.profile)
        if quote_layout.name == history_layout.name:
            raise ValueError('quote and preparation require distinct memory mappings')
        private = dict(quotes=admitted,
            preparation=dict(history.value, secret=history.secret),
            preparation_reconnect_seconds=lifecycle['reconnect_seconds'])
        runtime, identity = _prepare_runtime(agent_root, sdk_metadata, license_bytes,
            ('guanheng_qmt_shm_agent.quote_stream', 'guanheng_qmt_shm_agent.history_preparation_agent'),
            **({'reader': input_reader} if input_reader is not None else {}))
        strategy = _render_memory_entry(private, runtime, COMBINED_CALLBACKS,
            ('download_history_data',), ('init', 'agent_tick', 'handlebar', 'stop'))
        return strategy, dict(identity, strategy_sha256=hashlib.sha256(strategy).hexdigest(),
            strategy_bytes=len(strategy), profile=admitted['profile'], history_profile=history.profile,
            history_reconnect_seconds=lifecycle['reconnect_seconds'])
    runtime, identity = _prepare_runtime(agent_root, sdk_metadata, license_bytes,
        ('guanheng_qmt_shm_agent.quote_stream',),
        **({'reader': input_reader} if input_reader is not None else {}))
    callbacks = DIAGNOSTIC_CALLBACKS if diagnostics else CALLBACKS
    strategy = _render_memory_entry(admitted, runtime, callbacks, (),
        ('init', 'agent_tick', 'handlebar', 'stop'))
    identity = dict(identity, strategy_sha256=hashlib.sha256(strategy).hexdigest(),
        strategy_bytes=len(strategy), profile=admitted['profile'])
    if diagnostics:
        identity['diagnostics'] = True
    return strategy, identity


def _read(path, maximum):
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum+1)
    if len(raw) > maximum:
        raise ValueError('quote stream build input exceeds byte budget')
    return raw


def generate(settings, *, agent_root, sdk_metadata, license_bytes, output, diagnostics=False,
             history_bootstrap=None, history_reconnect_seconds=1.0):
    """独占创建受保护目录；正文及内存来源身份含私有设置，均沿原私有写入口。"""
    strategy, identity = render_strategy(settings, agent_root=agent_root,
        sdk_metadata=sdk_metadata, license_bytes=license_bytes, diagnostics=diagnostics,
        history_bootstrap=history_bootstrap, history_reconnect_seconds=history_reconnect_seconds)
    output = Path(output)
    create_private_directory(output)
    write_private_new(output/'strategy.py', strategy)
    write_private_new(output/'CPYTHON-LICENSE.txt', license_bytes)
    write_private_new(output/'memory-runtime.json', canonical(identity))
    safe = {'schema_version': 'qmt.quote-stream-material.v1',
        'strategy_sha256': identity['strategy_sha256'], 'strategy_bytes': len(strategy),
        'runtime_sha256': identity['runtime_sha256'], 'symbols_sha256': settings['profile']['symbols_sha256'],
        'symbol_count': len(settings['symbols']), 'qualified_in_qmt': False, 'order_ready': False}
    if diagnostics:
        safe['diagnostics'] = True
    if history_bootstrap is not None:
        safe['history_preparation'] = True
    write_private_new(output/'RESULT.json', canonical(safe))
    return safe

