"""纯生成常驻交易或行情/补齐/交易组合正文；三类业务沿各自原owner。"""
from guanheng_qmt_shm_agent.history_preparation import OPERATION, validate_configuration
from guanheng_qmt_shm_agent.quote_stream_contract import validate_settings
from guanheng_qmt_shm_agent.read_capabilities import FULL_TICK, HISTORY
from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
from guanheng_qmt_shm_agent.transport_profile import validate_transport_profile
from .lifecycle import validate_connection_lifecycle
from .memory_runtime import _prepare_runtime
from .pair import _TRADE_CALLBACKS, _render_memory_entry
from .account_read_composition import admit_account_read
from .analysis_read_composition import admit_analysis_read
from .analysis_batch_read_composition import admit_analysis_batch_read
from guanheng_qmt_shm_agent.source_runtime import source_runtime as admit_source_runtime, TICK_PERIOD


_CALLBACKS = ('init', 'agent_tick', 'handlebar', 'stop',
              'order_callback', 'deal_callback', 'orderError_callback')
_TRADE_ROOT = 'guanheng_qmt_shm_agent.reconnecting_trade'
_ACCOUNT_ROOT = 'guanheng_qmt_shm_agent.reconnecting_read'
_MARKET_ROOTS = ('guanheng_qmt_shm_agent.quote_stream',
                 'guanheng_qmt_shm_agent.history_preparation_agent')


COMBINED_CALLBACKS = '''import threading as _threading
from datetime import datetime as _datetime, timedelta as _timedelta
from guanheng_qmt_shm_agent.quote_stream import QuoteStreamAgent as _QuoteAgent
from guanheng_qmt_shm_agent.history_preparation_agent import ReconnectingHistoryPreparationAgent as _PreparationAgent
from guanheng_qmt_shm_agent.reconnecting_trade import ReconnectingTradingAgent as _TradeAgent
_quote, _preparation, _trade, _context, _thread = None, None, None, None, None
_stopping, _stop_failure = False, None

def _request_close():
    global _stopping, _stop_failure
    if _stopping:
        if _stop_failure is not None:
            raise _stop_failure
        return
    _stopping = True
    # 原策略线程依次撤销交易/补齐准入及行情订阅；失败仍通知每个已构造owner。
    for owner in (_trade, _preparation, _quote):
        if owner is not None:
            try:
                owner.request_close()
            except BaseException as error:
                if _stop_failure is None:
                    _stop_failure = error
    if _stop_failure is not None:
        raise _stop_failure

def init(ContextInfo):
    global _quote, _preparation, _trade, _context, _thread
    if _context is not None:
        raise RuntimeError("combined entry has one native context generation")
    _context, _thread = ContextInfo, _threading.get_ident()
    try:
        _trade = _TradeAgent(ContextInfo, trusted_bootstrap=_settings['trade'],
            trade_detail_query=globals().get('get_trade_detail_data'),
            passorder=globals().get('passorder'), cancel=globals().get('cancel'),
            enabled=True, reconnect_seconds=_settings['trade_reconnect_seconds'])
        _quote = _QuoteAgent(ContextInfo, settings=_settings['quotes'])
        _preparation = _PreparationAgent(ContextInfo,
            trusted_bootstrap=_settings['preparation'], enabled=True,
            download_history_data=globals().get('download_history_data'),
            reconnect_seconds=_settings['preparation_reconnect_seconds'])
        # 稳定交易owner先发布；set_account同步回报直接进入原SourceTradingService。
        _trade.subscribe_account()
        ContextInfo.run_time("agent_tick", "1nSecond",
            (_datetime.now()+_timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"))
        _trade.start()
        _preparation.start()
        _quote.start()
    except BaseException as primary:
        try:
            _request_close()
        except BaseException as cleanup:
            raise primary from cleanup
        raise

def _check_context(ContextInfo):
    if _trade is None:
        raise RuntimeError("trade entry requires its original context generation")
    if ContextInfo is not _context:
        _trade.request_close()
        raise RuntimeError("trade entry requires its original context generation")

def _check(ContextInfo):
    _check_context(ContextInfo)
    if _threading.get_ident() != _thread:
        raise RuntimeError("combined execution requires its original strategy thread")

def agent_tick(ContextInfo):
    _check(ContextInfo)
    if _stopping:
        return False
    # 每次只授一个重任务；补齐tick仍可推进自己的连接代际和轻量退休。
    trade_work = _trade.tick()
    preparation_work = _preparation.tick(allow_heavy=not trade_work)
    return trade_work or preparation_work

def handlebar(ContextInfo):
    _check(ContextInfo)

def order_callback(ContextInfo, orderInfo):
    _check_context(ContextInfo)
    return _trade.on_order(ContextInfo, orderInfo)

def deal_callback(ContextInfo, dealInfo):
    _check_context(ContextInfo)
    return _trade.on_deal(ContextInfo, dealInfo)

def orderError_callback(ContextInfo, orderArgs, errMsg):
    _check_context(ContextInfo)
    return _trade.on_error(ContextInfo, orderArgs, errMsg)

def stop(ContextInfo):
    _check(ContextInfo)
    return _request_close()
'''


def _interval(seconds):
    return validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read', reconnect_seconds=seconds))['reconnect_seconds']


def _private_trade(admitted):
    return dict(admitted.value, secret=admitted.secret,
                trade_binding=admitted.trade_binding, writes_enabled=admitted.writes_enabled)


def _account_callbacks(has_market):
    """从原三owner模板明确扩展；默认模板原字节保持，新增连接不复制业务实现。"""
    body = COMBINED_CALLBACKS
    replacements = [
        ('from guanheng_qmt_shm_agent.reconnecting_trade import ReconnectingTradingAgent as _TradeAgent',
         'from guanheng_qmt_shm_agent.reconnecting_trade import ReconnectingTradingAgent as _TradeAgent\n'
         'from guanheng_qmt_shm_agent.reconnecting_read import ReconnectingReadAgent as _ReadAgent'),
        ('_quote, _preparation, _trade, _context, _thread = None, None, None, None, None',
         '_quote, _preparation, _trade, _account_read, _context, _thread = None, None, None, None, None, None'),
        ('global _quote, _preparation, _trade, _context, _thread',
         'global _quote, _preparation, _trade, _account_read, _context, _thread'),
        ('for owner in (_trade, _preparation, _quote):',
         'for owner in (_trade, _account_read, _preparation, _quote):'),
        ('''        _quote = _QuoteAgent(ContextInfo, settings=_settings['quotes'])
        _preparation = _PreparationAgent(ContextInfo,
            trusted_bootstrap=_settings['preparation'], enabled=True,
            download_history_data=globals().get('download_history_data'),
            reconnect_seconds=_settings['preparation_reconnect_seconds'])''',
         '''        _account_read = _ReadAgent(ContextInfo,
            trusted_bootstrap=_settings['account_read']['agent'],
            trade_detail_query=globals().get('get_trade_detail_data'), enabled=True,
            reconnect_seconds=_settings['account_read']['reconnect_seconds'])
        if 'quotes' in _settings:
            _quote = _QuoteAgent(ContextInfo, settings=_settings['quotes'])
            _preparation = _PreparationAgent(ContextInfo,
                trusted_bootstrap=_settings['preparation'], enabled=True,
                download_history_data=globals().get('download_history_data'),
                reconnect_seconds=_settings['preparation_reconnect_seconds'])'''),
        ('''        _preparation.start()
        _quote.start()''',
         '''        _account_read.start()
        if _preparation is not None:
            _preparation.start()
        if _quote is not None:
            _quote.start()'''),
        ('''        _trade.request_close()
        raise RuntimeError("trade entry requires its original context generation")''',
         '''        _request_close()
        raise RuntimeError("trade entry requires its original context generation")'''),
        ('''    preparation_work = _preparation.tick(allow_heavy=not trade_work)
    return trade_work or preparation_work''',
         '''    # 轻量连接/退休始终推进；重任务依次让给交易、只读账户、HPR。
    account_work = _account_read.tick(allow_heavy=not trade_work)
    preparation_work = False
    if _preparation is not None:
        preparation_work = _preparation.tick(allow_heavy=not (trade_work or account_work))
    return trade_work or account_work or preparation_work'''),
    ]
    for old, new in replacements:
        if body.count(old) != 1:
            raise ValueError('original combined callback template changed')
        body = body.replace(old, new)
    if not has_market:
        for line in ('from guanheng_qmt_shm_agent.quote_stream import QuoteStreamAgent as _QuoteAgent\n',
                     'from guanheng_qmt_shm_agent.history_preparation_agent import ReconnectingHistoryPreparationAgent as _PreparationAgent\n'):
            if body.count(line) != 1:
                raise ValueError('original market callback import changed')
            body = body.replace(line, '')
    return body



def _analysis_callbacks(has_market, has_account):
    """只组合原owner；旧四owner模板保持，新增只读连接共享同一个调度点。"""
    body = _account_callbacks(has_market)
    replacements = [
        ('_trade, _account_read, _context, _thread = None, None, None, None, None, None',
         '_trade, _account_read, _analysis_read, _context, _thread = None, None, None, None, None, None, None'),
        ('global _quote, _preparation, _trade, _account_read, _context, _thread',
         'global _quote, _preparation, _trade, _account_read, _analysis_read, _context, _thread'),
        ('for owner in (_trade, _account_read, _preparation, _quote):',
         'for owner in (_trade, _account_read, _analysis_read, _preparation, _quote):'),
        ("        if 'quotes' in _settings:",
         "        _analysis_read = _ReadAgent(ContextInfo,\n"
         "            trusted_bootstrap=_settings['analysis_read']['agent'], enabled=True,\n"
         "            reconnect_seconds=_settings['analysis_read']['reconnect_seconds'])\n"
         "        if 'quotes' in _settings:"),
        ('        _account_read.start()',
         '        if _account_read is not None:\n            _account_read.start()\n        _analysis_read.start()'),
        ('    account_work = _account_read.tick(allow_heavy=not trade_work)',
         '    account_work = False\n    if _account_read is not None:\n'
         '        account_work = _account_read.tick(allow_heavy=not trade_work)\n'
         '    analysis_work = _analysis_read.tick(allow_heavy=not (trade_work or account_work))'),
        ('preparation_work = _preparation.tick(allow_heavy=not (trade_work or account_work))',
         'preparation_work = _preparation.tick(allow_heavy=not (trade_work or account_work or analysis_work))'),
        ('return trade_work or account_work or preparation_work',
         'return trade_work or account_work or analysis_work or preparation_work'),
        ('重任务依次让给交易、只读账户、HPR。', '重任务依次让给交易、只读账户、分析、HPR。'),
    ]
    for old, new in replacements:
        if body.count(old) != 1:
            raise ValueError('original account callback template changed')
        body = body.replace(old, new)
    if not has_account:
        block = """        _account_read = _ReadAgent(ContextInfo,
            trusted_bootstrap=_settings['account_read']['agent'],
            trade_detail_query=globals().get('get_trade_detail_data'), enabled=True,
            reconnect_seconds=_settings['account_read']['reconnect_seconds'])
"""
        if body.count(block) != 1:
            raise ValueError('original account construction changed')
        body = body.replace(block, '')
    return body


def _distinct_owners(values, profiles):
    if len({item['transport']['windows_session_id'] for item in values}) != 1:
        raise ValueError('combined owners require the same Windows session')
    layouts = [validate_transport_profile(item['transport'], item['route'],
        item['max_frame'], profile) for item, profile in zip(values, profiles)]
    if len({layout.name for layout in layouts}) != len(layouts):
        raise ValueError('combined owners require distinct memory mappings')
    if len({item['secret'] for item in values}) != len(values):
        raise ValueError('combined owners require distinct IPC secrets')


def _batch_analysis_callbacks(has_market, has_account, has_analysis):
    """沿同一个原调度点加入 v8 owner，保持各原业务实现及单重任务额度。"""
    body = _analysis_callbacks(has_market, has_account)
    replacements = [
        ('_trade, _account_read, _analysis_read, _context, _thread = None, None, None, None, None, None, None',
         '_trade, _account_read, _analysis_read, _analysis_batch_read, _context, _thread = None, None, None, None, None, None, None, None'),
        ('global _quote, _preparation, _trade, _account_read, _analysis_read, _context, _thread',
         'global _quote, _preparation, _trade, _account_read, _analysis_read, _analysis_batch_read, _context, _thread'),
        ('for owner in (_trade, _account_read, _analysis_read, _preparation, _quote):',
         'for owner in (_trade, _account_read, _analysis_read, _analysis_batch_read, _preparation, _quote):'),
        ("        if 'quotes' in _settings:",
         "        _analysis_batch_read = _ReadAgent(ContextInfo,\n"
         "            trusted_bootstrap=_settings['analysis_batch_read']['agent'], enabled=True,\n"
         "            reconnect_seconds=_settings['analysis_batch_read']['reconnect_seconds'])\n"
         "        if 'quotes' in _settings:"),
        ('        _analysis_read.start()',
         '        if _analysis_read is not None:\n            _analysis_read.start()\n        _analysis_batch_read.start()'),
        ('    analysis_work = _analysis_read.tick(allow_heavy=not (trade_work or account_work))',
         '    analysis_work = False\n    if _analysis_read is not None:\n'
         '        analysis_work = _analysis_read.tick(allow_heavy=not (trade_work or account_work))\n'
         '    batch_work = _analysis_batch_read.tick(allow_heavy=not (trade_work or account_work or analysis_work))'),
        ('preparation_work = _preparation.tick(allow_heavy=not (trade_work or account_work or analysis_work))',
         'preparation_work = _preparation.tick(allow_heavy=not (trade_work or account_work or analysis_work or batch_work))'),
        ('return trade_work or account_work or analysis_work or preparation_work',
         'return trade_work or account_work or analysis_work or batch_work or preparation_work'),
        ('重任务依次让给交易、只读账户、分析、HPR。', '重任务依次让给交易、只读账户、v7分析、v8批量、HPR。'),
    ]
    for old, new in replacements:
        if body.count(old) != 1:
            raise ValueError('original analysis callback template changed')
        body = body.replace(old, new)
    if not has_analysis:
        block = """        _analysis_read = _ReadAgent(ContextInfo,
            trusted_bootstrap=_settings['analysis_read']['agent'], enabled=True,
            reconnect_seconds=_settings['analysis_read']['reconnect_seconds'])
"""
        if body.count(block) != 1:
            raise ValueError('original analysis construction changed')
        body = body.replace(block, '')
    return body


def _market_settings(market, trade):
    """复用原准入；组合层只核同Windows会话、独立映射及IPC秘密角色。"""
    if (type(market) is not dict or set(market) !=
            {'quotes', 'preparation', 'preparation_reconnect_seconds'}):
        raise ValueError('explicit market composition fields differ')
    quote = validate_settings(market['quotes'])
    preparation = validate_configuration(market['preparation'])
    interval = _interval(market['preparation_reconnect_seconds'])
    if (set(preparation.profile['read_operations']) - {FULL_TICK, HISTORY, OPERATION}
            or preparation.value['transport']['kind'] != 'builtin-shm'):
        raise ValueError('combined preparation requires market-only builtin SHM scope')
    values = (quote, dict(preparation.value, secret=preparation.secret), _private_trade(trade))
    profiles = (quote['profile'], preparation.profile, trade.profile)
    _distinct_owners(values, profiles)
    return dict(quotes=quote, preparation=values[1], preparation_reconnect_seconds=interval)


def render_trade_source(trade_bootstrap, *, agent_root, sdk_metadata, stdlib_license,
                        reconnect_seconds, market=None, account_read=None, analysis_read=None,
                        analysis_batch_read=None, source_runtime=None, reader=None):
    """返回完整ASCII内存正文bytes和一次冻结的闭包身份，不创建运行资源。

    market=None只生成原交易回调；显式market装配三owner及单一定时器。
    reader仅交给原freeze读取已批准离线源码，严格配对可传其原_read。
    IPC秘密只进入私有正文；此接口没有HTTP凭据，HTTP角色隔离由配对准入核验。
    """
    trade = validate_trade_configuration(trade_bootstrap)
    if trade.value['transport']['kind'] != 'builtin-shm':
        raise ValueError('trade strategy requires explicit builtin SHM')
    interval = _interval(reconnect_seconds)
    settings = _private_trade(trade)
    roots = (_TRADE_ROOT,)
    injected = ('get_trade_detail_data', 'passorder', 'cancel')
    if market is None:
        original_import = 'from {namespace}.trading_agent import RestrictedTradingAgent as _Agent'
        original_arguments = 'passorder=globals().get("passorder"), cancel=globals().get("cancel"))'
        if _TRADE_CALLBACKS.count(original_import) != 1 or _TRADE_CALLBACKS.count(original_arguments) != 1:
            raise ValueError('original trade callback template changed')
        body = _TRADE_CALLBACKS.replace(original_import,
            'from {namespace}.reconnecting_trade import ReconnectingTradingAgent as _Agent')
        body = body.replace(original_arguments,
            'passorder=globals().get("passorder"), cancel=globals().get("cancel"), enabled=True, reconnect_seconds='
            + repr(interval) + ')').format(namespace='guanheng_qmt_shm_agent')
    else:
        settings = dict(_market_settings(market, trade), trade=settings, trade_reconnect_seconds=interval)
        roots += _MARKET_ROOTS
        injected += ('download_history_data',)
        body = COMBINED_CALLBACKS
    if account_read is not None:
        account_read, read_profile = admit_account_read(account_read)
        if market is None:
            settings = dict(trade=_private_trade(trade), trade_reconnect_seconds=interval)
            values, profiles = [_private_trade(trade)], [trade.profile]
        else:
            # 市场准入已完成；这里只组合原profile，不修改任何owner的账号或能力。
            quote = validate_settings(settings['quotes'])
            preparation = validate_configuration(settings['preparation'])
            values = [quote, dict(preparation.value, secret=preparation.secret), _private_trade(trade)]
            profiles = [quote['profile'], preparation.profile, trade.profile]
        _distinct_owners(values + [account_read['agent']], profiles + [read_profile])
        settings['account_read'] = account_read
        roots += (_ACCOUNT_ROOT,)
        body = _account_callbacks(market is not None)
    if analysis_read is not None:
        analysis_read, analysis_profile = admit_analysis_read(analysis_read)
        if market is None and account_read is None:
            settings = dict(trade=_private_trade(trade), trade_reconnect_seconds=interval)
        values, profiles = [_private_trade(trade)], [trade.profile]
        if market is not None:
            quote = validate_settings(settings['quotes'])
            preparation = validate_configuration(settings['preparation'])
            values += [quote, dict(preparation.value, secret=preparation.secret)]
            profiles += [quote['profile'], preparation.profile]
        if account_read is not None:
            values += [account_read['agent']]
            profiles += [read_profile]
        _distinct_owners(values + [analysis_read['agent']], profiles + [analysis_profile])
        settings['analysis_read'] = analysis_read
        roots += (_ACCOUNT_ROOT,)
        body = _analysis_callbacks(market is not None, account_read is not None)
    if analysis_batch_read is not None:
        analysis_batch_read, batch_profile = admit_analysis_batch_read(analysis_batch_read)
        if market is None and account_read is None and analysis_read is None:
            settings = dict(trade=_private_trade(trade), trade_reconnect_seconds=interval)
        values, profiles = [_private_trade(trade)], [trade.profile]
        if market is not None:
            quote = validate_settings(settings['quotes'])
            preparation = validate_configuration(settings['preparation'])
            values += [quote, dict(preparation.value, secret=preparation.secret)]
            profiles += [quote['profile'], preparation.profile]
        if account_read is not None:
            values += [account_read['agent']]
            profiles += [read_profile]
        if analysis_read is not None:
            values += [analysis_read['agent']]
            profiles += [analysis_profile]
        _distinct_owners(values + [analysis_batch_read['agent']], profiles + [batch_profile])
        settings['analysis_batch_read'] = analysis_batch_read
        roots += (_ACCOUNT_ROOT,)
        body = _batch_analysis_callbacks(market is not None, account_read is not None, analysis_read is not None)
    source_runtime = admit_source_runtime(source_runtime)
    if (analysis_read is not None or analysis_batch_read is not None) and (source_runtime is None or source_runtime['mode'] != 'strategy_tick'):
        raise ValueError('analysis composition requires explicit strategy_tick source runtime')
    if source_runtime is not None and source_runtime['mode'] == 'strategy_tick':
        # 一个来源驱动服务全部业务owner；默认模板及金融profile保持。
        replacements = {
            'reconnecting_trade import ReconnectingTradingAgent': 'strategy_tick import TickTradingAgent',
            'reconnecting_read import ReconnectingReadAgent': 'strategy_tick import TickReadAgent',
            'history_preparation_agent import ReconnectingHistoryPreparationAgent': 'strategy_tick import TickPreparationAgent',
            'quote_stream import QuoteStreamAgent': 'strategy_tick import TickQuoteAgent'}
        for original, replacement in replacements.items():
            body = body.replace(original, replacement)
        # 沿官方原run_time使用毫秒周期；仍只有同一个agent_tick timer。
        # 空闲poll直接返回，让原1秒连接预算与2秒I/O期限有实际推进机会。
        if body.count('"1nSecond"') != 1:
            raise ValueError('original source timer differs')
        body = body.replace('"1nSecond"', repr(TICK_PERIOD))
        if market is not None:
            marker = '    trade_work = _trade.tick()'
            if body.count(marker) != 1:
                raise ValueError('original strategy tick marker differs')
            body = body.replace(marker, '    _quote.tick()\n' + marker)
        roots += ('guanheng_qmt_shm_agent.strategy_tick',)
    memory, identity = _prepare_runtime(agent_root, sdk_metadata, stdlib_license, roots,
                                       **({'reader': reader} if reader is not None else {}))
    return _render_memory_entry(settings, memory, body, injected, _CALLBACKS), identity
