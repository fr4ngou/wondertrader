"""纯生成QST/HPR/v7/v8完整行情正文；原owner及原冻结器拥有通信与SDK行为。"""
from guanheng_qmt_shm_agent.history_preparation import validate_configuration
from guanheng_qmt_shm_agent.quote_stream_contract import validate_settings
from guanheng_qmt_shm_agent.source_runtime import TICK_PERIOD
from .analysis_read_composition import admit_analysis_read
from .analysis_batch_read_composition import admit_analysis_batch_read
from .memory_runtime import _prepare_runtime
from .pair import _render_memory_entry
from .trade_source import _distinct_owners, _interval


CALLBACKS = '''import threading as _threading
from datetime import datetime as _datetime, timedelta as _timedelta
from guanheng_qmt_shm_agent.strategy_tick import TickQuoteAgent as _QuoteAgent
from guanheng_qmt_shm_agent.strategy_tick import TickPreparationAgent as _PreparationAgent
from guanheng_qmt_shm_agent.strategy_tick import TickReadAgent as _ReadAgent
_context, _thread, _quote, _preparation = None, None, None, None
_reads, _owners = [], []
_stopping, _stop_failure = False, None

def _check(ContextInfo):
    if ContextInfo is not _context or _threading.get_ident() != _thread:
        raise RuntimeError("market entry requires its original strategy context/thread")

def _request_close():
    global _stopping, _stop_failure
    if _stopping:
        if _stop_failure is not None:
            raise _stop_failure
        return
    _stopping = True
    for owner in reversed(_owners):
        try:
            owner.request_close()
        except BaseException as error:
            if _stop_failure is None:
                _stop_failure = error
    if _stop_failure is not None:
        raise _stop_failure

def init(ContextInfo):
    global _context, _thread, _quote, _preparation
    if _context is not None:
        raise RuntimeError("market entry has one native context generation")
    _context, _thread = ContextInfo, _threading.get_ident()
    try:
        _quote = _QuoteAgent(ContextInfo, settings=_settings['quotes'])
        _owners.append(_quote)
        _preparation = _PreparationAgent(ContextInfo, trusted_bootstrap=_settings['preparation'],
            enabled=True, download_history_data=globals().get('download_history_data'),
            reconnect_seconds=_settings['preparation_reconnect_seconds'])
        _owners.append(_preparation)
        for name in ('analysis_read', 'analysis_batch_read'):
            selected = _settings[name]
            owner = _ReadAgent(ContextInfo, trusted_bootstrap=selected['agent'], enabled=True,
                reconnect_seconds=selected['reconnect_seconds'])
            _owners.append(owner)
            _reads.append(owner)
        ContextInfo.run_time("agent_tick", _TICK_PERIOD,
            (_datetime.now()+_timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"))
        for owner in _owners:
            owner.start()
    except BaseException as primary:
        try:
            _request_close()
        except BaseException as cleanup:
            raise primary from cleanup
        raise

def agent_tick(ContextInfo):
    _check(ContextInfo)
    if _stopping:
        return False
    _quote.tick()
    worked = False
    for owner in _reads:
        worked = bool(owner.tick(allow_heavy=not worked)) or worked
    return bool(_preparation.tick(allow_heavy=not worked)) or worked

def handlebar(ContextInfo):
    _check(ContextInfo)

def stop(ContextInfo):
    _check(ContextInfo)
    return _request_close()
'''


def render_market_source(configuration, *, agent_root, sdk_metadata, stdlib_license, reader=None):
    """只冻结完整行情正文bytes及闭包身份；不读取账户、注册SDK或启动通信。

    configuration必须包含QST/HPR/v7/v8及原重连间隔。每个原配置先沿所属准入，
    原映射及秘密角色须彼此独立。SDK/stdlib原件仍由唯一_prepare_runtime冻结。
    """
    if type(configuration) is not dict or set(configuration) != {
            'quotes', 'preparation', 'preparation_reconnect_seconds', 'analysis_read', 'analysis_batch_read'}:
        raise ValueError('complete market Source fields differ')
    quote = validate_settings(configuration['quotes'])
    preparation = validate_configuration(configuration['preparation'])
    if set(preparation.profile['read_operations']) != {'market.full_tick', 'market.history_1m', 'market.history_prepare'}:
        raise ValueError('market Source requires original complete HPR profile')
    analysis, analysis_profile = admit_analysis_read(configuration['analysis_read'])
    batch, batch_profile = admit_analysis_batch_read(configuration['analysis_batch_read'])
    settings = dict(quotes=quote, preparation=dict(preparation.value, secret=preparation.secret),
        preparation_reconnect_seconds=_interval(configuration['preparation_reconnect_seconds']),
        analysis_read=analysis, analysis_batch_read=batch)
    _distinct_owners([quote, settings['preparation'], analysis['agent'], batch['agent']],
        [quote['profile'], preparation.profile, analysis_profile, batch_profile])
    roots = ('guanheng_qmt_shm_agent.strategy_tick',)
    memory, identity = _prepare_runtime(agent_root, sdk_metadata, stdlib_license, roots,
        **({'reader': reader} if reader is not None else {}))
    body = '_TICK_PERIOD = ' + repr(TICK_PERIOD) + '\n' + CALLBACKS
    strategy = _render_memory_entry(settings, memory, body, ('download_history_data',),
        ('init', 'agent_tick', 'handlebar', 'stop'))
    return strategy, identity
