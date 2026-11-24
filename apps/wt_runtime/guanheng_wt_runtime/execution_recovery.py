"""故障恢复的发行身份交接；券商查询和金融状态加载归原执行 owner。"""
from __future__ import annotations

import hashlib
import copy
import math
import json
import os
import re
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path
import time

from .managed_local_process import _inspect, _json, _path, _read, _require, _sha


def canonical(value):
    """与原绑定和用户状态相同的规范 ASCII 编码。"""
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def require_process_exited(pid):
    """只核Windows原PID已不存在或句柄已退出；拒绝活PID、拒绝访问及未知结果。"""
    import ctypes
    from .strategy_job import ProcessJob
    _require(type(pid) is int and 0 < pid <= 0xffffffff)
    api = ProcessJob().api  # 仅声明原Win32接口，构造不分配Job或进程。
    handle = api.OpenProcess(0x100000, False, pid)
    if not handle:
        _require(ctypes.get_last_error() == 87)  # ERROR_INVALID_PARAMETER：原PID不存在。
        return
    try:
        _require(api.WaitForSingleObject(handle, 0) == 0)
    finally:
        _require(bool(api.CloseHandle(handle)))


def record_execution_process_loss(control, *, expected=None):
    """执行恢复owner核原件和物理退出，记录故障事实；关闭/退出码保持未知。"""
    from uuid import UUID
    control = Path(control)
    _require(control.is_absolute())
    _inspect(control, directory=True)
    raw = _read(control / 'ready.json', 4096)
    ready = _json(raw)
    _require(ready['schema'] == 'guanheng.execution.ready.v1'
             and str(UUID(ready['control_id'])) == control.name
             and hashlib.sha256(_read(control / 'execution.json', 256 * 1024)).hexdigest()
             == _sha(ready['config_sha256']))
    _require(not any((control / name).exists() for name in ('closed.json', 'close-prepared.json', 'failure.json')))
    require_process_exited(ready['pid'])
    identity = {name: ready[name] for name in ('control_id', 'config_sha256', 'pid')}
    if expected is not None:
        _require(type(expected) is dict and expected == identity)
    path = control / 'owner-loss.json'
    if path.exists():
        value = _json(_read(path, 4096))
        _require(all(value.get(k) == v for k, v in identity.items())
                 and value.get('schema') == 'guanheng.execution.owner-loss.v1'
                 and value.get('reason') == 'process_lost'
                 and value.get('ready_sha256') == hashlib.sha256(raw).hexdigest())
        return value
    value = dict(
        schema='guanheng.execution.owner-loss.v1',  # 原进程物理退出故障，未授正常关闭。
        **identity,  # 原control/config/PID，全部来自已校验原ready及配置字节。
        ready_sha256=hashlib.sha256(raw).hexdigest(),  # 原ready字节身份，供Native重核。
        reason='process_lost',  # 固定故障类别；退出码和原join结果仍未知。
        observed_at=datetime.now(timezone.utc).isoformat(),  # 本次核查UTC时间，不冒充来源时点。
        observer_pid=os.getpid())  # 执行核查owner的PID，与原执行PID分别保存。
    with path.open('xb') as stream:
        stream.write(canonical(value))
    return value


def _storage_model(native):
    from .private_storage import configured_private_copy
    private = configured_private_copy(native)
    if private is None:
        return native
    model = copy.deepcopy(native)
    model['output_directory'] = private['original_output']
    model.pop('private_storage_origin')
    return model


def _business(value):
    """原Native业务配置；恢复选择不属于持仓模型身份。"""
    value=copy.deepcopy(_storage_model(value));value.pop('recovery',None);value.pop('shared_account_storage',None)
    return value


def _normalize_publication_cache(value):
    """比较时保留发布路径及来源父目录，归一同父目录下的发布器工作代和派生缓存。"""
    data=value.get('data')
    store=data.get('store') if type(data) is dict else None
    if type(store) is not dict or store.get('module') != 'GuanhengRealtimeReader':
        return
    daily=store.get('daily')
    if type(daily) is not dict or 'publication' not in daily:
        return
    publication=daily['publication']
    _require(type(publication) is dict and {'status_file','publication_file','cache_root'} <= set(publication)
             <= {'status_file','publication_file','cache_root','source_root'})
    for path in publication.values():
        _require(type(path) is str and 0 < len(path.encode('utf-8')) <= 1024
                 and all(ord(c) >= 32 and ord(c) != 127 for c in path)
                 and Path(path).is_absolute() and '..' not in Path(path).parts)
    publication.pop('cache_root')
    if 'source_root' in publication:
        source = Path(publication['source_root'])
        if Path(publication['status_file']) == source / 'STATUS.json' and source.parent != Path(source.anchor):
            publication['status_file'] = 'STATUS.json'
            publication['source_root'] = str(source.parent)


def _normalize_retained_parser_port(value):
    """行情读取端口属于本机部署，认证角色和解析器的其余配置继续参与身份比较。"""
    parsers = value.get('parsers')
    if not isinstance(parsers, list):
        return
    for parser in parsers:
        if not isinstance(parser, dict) or parser.get('module') != 'ParserQMTHostRetainedV6':
            continue
        qmt = parser.get('qmt')
        url = qmt.get('base_url') if isinstance(qmt, dict) else None
        if not isinstance(url, str):
            continue
        host, separator, port = url.removesuffix('/').rpartition(':')
        if (separator and host == 'http://127.0.0.1' and 1 <= len(port) <= 5
                and port.isascii() and port.isdecimal() and 1 <= int(port) <= 65535):
            qmt['base_url'] = 'http://127.0.0.1'


def _same_business(left, right):
    """仅比较金融模型；运行时长、发布接线和已核派生缓存定位独立，原件仍完整核验。"""
    left, right = copy.deepcopy(left), copy.deepcopy(right)
    for value in (left, right):
        duration = value['budget']['run_ms']
        _require(type(duration) is int and (duration == 0 or 1000 <= duration <= 86400000))
        value['budget'].pop('run_ms')
        _require(value.pop('native_state_save', 'native') in ('native', 'on_change'))
        _normalize_publication_cache(value)
        _normalize_retained_parser_port(value)
        # 此显式执行修正不改变金融模型；只归一化比较副本，实际配置和原件SHA保持。
        executer = value.get('executer')
        policies = executer.get('policy') if type(executer) is dict else None
        if type(policies) is dict:
            for rule in policies.values():
                if type(rule) is dict and rule.get('name') in (
                        'WtExeFact.WtStockMinImpactExeUnit','WtExeFact.WtStockMinImpactBorrowedExeUnit'):
                    # 原生执行参数可随显式发行调整，不改变资金/持仓模型；原配置SHA仍完整绑定。
                    # 分单数量属于执行参数；仅归一化比较副本，原配置和委托身份继续核验。
                    if 'lots' in rule:
                        lots = rule['lots']
                        _require(type(lots) in (int, float) and 0 < lots <= 1.7976931348623157e308)
                        rule.pop('lots')
                    if 'expire' in rule:
                        _require(type(rule['expire']) is int and 0<=rule['expire']<=4294967295)
                        rule.pop('expire')
                    if 'is_cancel_unmanaged_order' in rule:
                        _require(type(rule['is_cancel_unmanaged_order']) is bool)
                        rule.pop('is_cancel_unmanaged_order')
                if type(rule) is dict and 'replace_equal_position_target' in rule:
                    _require(type(rule['replace_equal_position_target']) is bool
                        and rule.get('name') in ('WtExeFact.WtStockMinImpactExeUnit',
                                                'WtExeFact.WtStockMinImpactBorrowedExeUnit'))
                    rule.pop('replace_equal_position_target')
        strategies = value.get('strategies')
        if type(strategies) is not list:
            continue
        for strategy in strategies:
            parameters = strategy.get('parameters') if type(strategy) is dict else None
            python = parameters.get('python_strategy') if type(parameters) is dict else None
            if type(python) is not dict:
                continue
            if 'market_window' in python:
                from .execution_market_window import MarketWindowFile
                # 时效是显式部署参数；复用原校验，比较副本保持窗口路径及原配置SHA。
                MarketWindowFile.from_dict(python['market_window'])
                python['market_window'].pop('max_age_seconds')
            if 'capital_account' not in python:
                continue
            account = python['capital_account']
            _require(type(account) is dict and set(account) == {'path', 'config_sha256', 'account', 'environment'})
            for name, maximum in (('path', 1024), ('account', 63)):
                text = account[name]
                _require(type(text) is str and 0 < len(text.encode('utf-8')) <= maximum
                         and all(ord(character) >= 32 and ord(character) != 127 for character in text))
            path = Path(account['path'])
            _require(path.is_absolute() and '..' not in path.parts)
            _sha(account['config_sha256'])
            _require(type(account['environment']) is str and account['environment'] in ('simulation', 'live'))
            # 仅从深拷贝的比较投影移除发布定位及程序身份；账户/环境和原读取时CAP绑定保持严格。
            account.pop('path')
            account.pop('config_sha256')
    return left == right


def _market_sources(marker):
    """只读来源声明；秘密只以环境变量名出现，连接固定本机服务。"""
    def endpoint(value):
        _require(type(value) is str)
        url=urlsplit(value)
        _require(url.scheme=='http' and url.hostname=='127.0.0.1' and url.port is not None
            and url.username is None and url.password is None and url.path in ('','/')
            and not url.query and not url.fragment)
    quotes=marker.get('quotes')
    if quotes is not None:
        _require(type(quotes)is dict and set(quotes)=={'base_url','token_env','timeout_seconds','max_response_bytes','max_age_seconds'})
        endpoint(quotes['base_url'])
        _require(type(quotes['token_env'])is str and quotes['token_env'].isidentifier()
            and type(quotes['timeout_seconds'])in(int,float)and 0<quotes['timeout_seconds']<=30
            and type(quotes['max_response_bytes'])is int and 8192<=quotes['max_response_bytes']<=16*1024*1024
            and type(quotes['max_age_seconds'])in(int,float)and 0<quotes['max_age_seconds']<=3600)
    parser=marker.get('parser')
    if parser is not None:
        _require(type(parser)is dict and set(parser)=={'module','base_url','key_id_env','hmac_secret_env'}
            and parser['module']=='ParserQMTHostRetainedV6')
        endpoint(parser['base_url'])
        _require(all(type(parser[k])is str and parser[k].isidentifier()for k in ('key_id_env','hmac_secret_env')))
    return quotes,parser


def execution_permission_origin_configuration(native, *, deadline=float('inf'), depth=0):
    """原账显式变更执行权限；仅归一化开关和运输引用，账户/模型/账根逐项保持。

    origin以原配置文件和SHA冻结，不授金融动作。实际准入继续核原关闭、查询、
    未决命令及金融文件。最多16跳，支持后继原账停写及正常发行接续。
    """
    marker = native.get('execution_permission_origin')
    if marker is None:return native
    _require(depth < 16 and type(marker) is dict and set(marker) == {'schema','file','sha256'}
        and marker['schema'] == 'guanheng.execution-permission-origin.v1')
    path = _path(marker['file']);_require(path.name == 'execution.json')
    body = _read(path,256*1024,deadline=deadline,clock=time.monotonic)
    _require(hashlib.sha256(body).hexdigest() == _sha(marker['sha256']))
    origin = _json(body)
    before,after = _business(origin),_business(native)
    before.pop('execution_permission_origin',None);after.pop('execution_permission_origin')
    before.pop('installation_root',None);after.pop('installation_root',None)
    def extension_installation(model, configuration):
        extension = model.get('strategy_extension_origin', {})
        reference = extension.get('dependency_handoff')
        if reference is None:
            return
        _require(type(reference) is dict and set(reference) == {'file', 'sha256'})
        raw = _read(_path(reference['file']), 1024 * 1024, deadline=deadline, clock=time.monotonic)
        _require(hashlib.sha256(raw).hexdigest() == _sha(reference['sha256']))
        proof = _json(raw)
        installation = proof.pop('current_installation')
        _require(type(installation) is dict and set(installation) == {'file', 'sha256'})
        path = _path(installation['file'])
        manifest = _read(path, 256 * 1024, deadline=deadline, clock=time.monotonic)
        _require(hashlib.sha256(manifest).hexdigest() == _sha(installation['sha256']))
        extension['dependency_handoff'] = proof
        static_names = set(configuration['base_data'].values())
        static_names.update(configuration['environment'].get(key) for key in ('fees', 'filters'))
        actual = _path(configuration['installation_root']).parent / 'execution-install.json'
        if actual != path:
            # 旧权限代可能继承原依赖清单；实际安装仍需使用相同的静态交易资料。
            actual_manifest = _json(_read(actual, 256 * 1024, deadline=deadline, clock=time.monotonic))
        else:
            actual_manifest = _json(manifest)
        files, fixed = actual_manifest['files'], _json(manifest)['files']
        keys = ['app/' + name for name in static_names if name]
        _require(all(_sha(files[key]) == _sha(fixed[key]) for key in keys))
        return {key: files[key] for key in keys}
    before_extension = before.get('strategy_extension_origin', {})
    after_extension = after.get('strategy_extension_origin', {})
    if before_extension.get('dependency_handoff') != after_extension.get('dependency_handoff'):
        _require(extension_installation(before, origin) == extension_installation(after, native))
    old,current = before['trader'],after['trader']
    _require(type(old.get('writes_enabled')) is bool and type(current.get('writes_enabled')) is bool
        and old['writes_enabled'] is not current['writes_enabled'])
    # 其余Trader字段（账户、环境、profile、预算及查询语义）继续精确相同。
    for key in ('writes_enabled','base_url','binding_id','binding_sha256','instance_id','key_id_env','hmac_secret_env'):
        _require((key in old) == (key in current))
        if key in old:current[key] = copy.deepcopy(old[key])
    _require(_same_business(before, after))
    if 'strategy_extension_origin' in native:
        return origin
    return execution_permission_origin_configuration(origin,deadline=deadline,depth=depth+1)


def market_origin_configuration(native, *, deadline=float('inf')):
    """显式行情接入只沿原配置/SHA回到基准；其余业务字段逐项保持。

    原参考只允许一跳且没有另一份origin，避免循环别名。准备阶段尚未注入
    takeover，按相同阶段比较；Native准入再核实际原takeover及状态文件。
    """
    native=strategy_extension_configuration(_storage_model(native),deadline=deadline)
    # 已发布的历史运行代只按实际配置接账。旧标记不再触发回投或换标。
    if 'role_replacement' in native:
        return native
    native=execution_permission_origin_configuration(native,deadline=deadline)
    marker=native.get('market_input_origin')
    if marker is None:return native
    _require(type(marker) is dict and {'schema','file','sha256'}<=set(marker)<={'schema','file','sha256','quotes','parser'}
        and marker['schema']=='guanheng.market-input-origin.v1')
    path=_path(marker['file']);_require(path.name=='execution.json')
    raw=_read(path,256*1024,deadline=deadline,clock=time.monotonic)
    _require(hashlib.sha256(raw).hexdigest()==_sha(marker['sha256']))
    origin=_json(raw);_require('market_input_origin' not in origin)
    preparing='takeover' not in native and 'takeover' in origin
    if preparing:origin.pop('takeover')
    before,after=_business(origin),_business(native);after.pop('market_input_origin')
    _require(type(after.get('strategies')) is list and len(after['strategies'])==1
        and type(before.get('strategies')) is list and len(before['strategies'])==1)
    current=after['strategies'][0]['parameters']['python_strategy']
    previous=before['strategies'][0]['parameters']['python_strategy']
    quotes,parser=_market_sources(marker)
    if quotes is not None and not preparing:
        _require(current.get('capital_market')==quotes and 'capital_market'in previous)
        current['capital_market']=copy.deepcopy(previous['capital_market'])
    if parser is not None:
        new_parsers,old_parsers=after['parsers'],before['parsers']
        _require(len(new_parsers)==len(old_parsers)==1 and old_parsers[0]['module']=='ParserQMTHostV6'
            and new_parsers[0]['module']==parser['module'])
        new_parsers[0]['module']=old_parsers[0]['module']
        for k in ('base_url','key_id_env','hmac_secret_env'):
            _require(new_parsers[0]['qmt'][k]==parser[k])
            new_parsers[0]['qmt'][k]=old_parsers[0]['qmt'][k]
    _require('market_window' not in previous and 'market_window' in current)
    window=current.pop('market_window')
    _require(type(window) is dict and set(window)=={'path','max_age_seconds'}
        and type(window['path']) is str and Path(window['path']).is_absolute()
        and type(window['max_age_seconds']) in (int,float)
        and math.isfinite(window['max_age_seconds']) and 1<=window['max_age_seconds']<=604800)
    daily=after['data']['store']['daily'];old_daily=before['data']['store']['daily']
    _require('publication' not in old_daily and 'adjustment' not in old_daily)
    publication=daily.pop('publication');adjustment=daily.pop('adjustment','none')
    _require(adjustment in ('none','front_ratio') and type(publication) is dict
        and {'status_file','publication_file','cache_root'}<=set(publication)
        <={'status_file','publication_file','cache_root','source_root'}
        and all(type(v) is str and Path(v).is_absolute() for v in publication.values())
        and Path(publication['publication_file'])==Path(window['path']))
    if preparing:
        # 原准备器随后用BASELINE的runtime-input替换模板引用；此处返回真正的
        # 准备配置投影，由原origin哈希完整约束模板及启动账户/报价，不改写BASELINE。
        for name in ('input_file','input_sha256','capital_account','capital_market'):
            if name in current:previous[name]=current[name]
            else:previous.pop(name,None)
    _require(_same_business(before, after))
    if preparing:
        # 库存BASELINE绑定原模型投影；预算取已验原件，实际执行仍使用本代run_ms。
        before['recovery']=copy.deepcopy(native['recovery'])
        return before
    return origin


def _extension_row(native, *, deadline=float('inf')):
    marker = native.get('strategy_extension_origin')
    if marker is None:
        return None
    reference = marker['added_strategy']
    _require(type(reference) is dict and set(reference) == {'file', 'sha256'})
    raw = _read(_path(reference['file']), 64 * 1024, deadline=deadline, clock=time.monotonic)
    _require(hashlib.sha256(raw).hexdigest() == _sha(reference['sha256']))
    added = _json(raw)
    rows = native['strategies']
    _require(type(rows) is list and sum(row == added for row in rows) == 1)
    return added


def strategy_extension_configuration(native, *, deadline=float('inf')):
    """仅投影已冻结新增行；原单策略业务准入继续核其余所有字段。"""
    # 双策略权限接续先核与同一实际策略集合的旧权限，再投影旧单策略历史。
    for unused in range(16):
        if 'strategy_extension_origin' not in native or 'execution_permission_origin' not in native:
            break
        marker = native['execution_permission_origin']
        raw = _read(_path(marker['file']), 256 * 1024, deadline=deadline, clock=time.monotonic)
        _require(hashlib.sha256(raw).hexdigest() == _sha(marker['sha256']))
        if 'strategy_extension_origin' not in _json(raw):
            break
        native = execution_permission_origin_configuration(native, deadline=deadline)
    else:
        raise ValueError('execution_permission_origin_depth')
    marker=native.get('strategy_extension_origin')
    if marker is None:return native
    _require(type(marker)is dict and {'schema','file','sha256','added_strategy'}<=set(marker)
        <={'schema','file','sha256','added_strategy','dependency_handoff','retired_targets'}
        and marker['schema']=='guanheng.strategy-extension-origin.v1')
    def pinned(reference,maximum):
        _require(type(reference)is dict and set(reference)=={'file','sha256'})
        raw=_read(_path(reference['file']),maximum,deadline=deadline,clock=time.monotonic)
        _require(hashlib.sha256(raw).hexdigest()==_sha(reference['sha256']))
        return _json(raw)
    _require(_path(marker['file']).name=='execution.json')
    origin=pinned({k:marker[k]for k in ('file','sha256')},256*1024)
    added = _extension_row(native, deadline=deadline)
    from .original_live import CONFIRM_LIVE_VERSION
    from .strategy_profiles import ORIGINAL_PROFILE, RETAINED_PROFILE, valid_strategy_id

    _require('strategy_extension_origin' not in origin and type(origin.get('strategies')) is list
             and len(origin['strategies']) == 1)
    retained = origin['strategies'][0]
    _require(retained['parameters']['python_strategy']['schema'] == RETAINED_PROFILE)
    p=added['parameters']['python_strategy']
    strategy_id = added['id']
    confirmation = p['strategy_version'] == CONFIRM_LIVE_VERSION
    amount = p['initial_capital_cny']
    _require(valid_strategy_id(strategy_id) and valid_strategy_id(retained['id'])
        and strategy_id.casefold() != retained['id'].casefold()
        and p['schema'] == ORIGINAL_PROFILE and type(p['strategy_version']) is str and 0 < len(p['strategy_version']) <= 64
        and type(amount) is str and re.fullmatch(r'[0-9]{1,25}(?:\.[0-9]{1,2})?', amount) is not None
        and any(digit in '123456789' for digit in amount)
        and (not confirmation or 'execution_symbol_589680' not in p)
        and p['state_mode']=='new'
        and p['activation_mode']=='signals-from-activation')
    rows=native['strategies']
    _require(len(rows) == 2 and sum(row['id'] == retained['id'] for row in rows) == 1)
    projected=copy.deepcopy(native);projected.pop('strategy_extension_origin')
    projected['strategies']=[row for row in projected['strategies'] if row['id'] == retained['id']]
    from .execution_dependency_handoff import normalize_dependencies, retired_target_symbols
    retirements=retired_target_symbols(marker, origin)
    _require('role_replacement' not in native)
    if 'dependency_handoff'in marker:
        projected=normalize_dependencies(projected,origin,marker['dependency_handoff'],marker['sha256'],
            execution_symbol=p.get('execution_symbol_589680'),confirmation=confirmation,
            execution_securities=p.get('execution_securities'),retired_targets=retirements,deadline=deadline)
    else:
        _require(not retirements)
    if 'role_replacement' in origin:
        _require(retirements)
        # 只把旧标记带入比较视图，保留前代真实输入及账本身份。
        projected['role_replacement']=copy.deepcopy(origin['role_replacement'])
    _require(compatible_business_configuration(projected,origin,deadline=deadline))
    return projected


def compatible_business_configuration(current, previous, *, deadline=float('inf')):
    """同一原模型允许显式市场引用接入；原窗口内容继续由数据owner发布。"""
    # 旧双ctx不能在投影时被丢弃；后继新增行必须逐值保持。
    if 'strategy_extension_origin'in previous:
        _require('strategy_extension_origin'in current and _extension_row(current,deadline=deadline)==_extension_row(previous,deadline=deadline)
            and {k:v for k,v in current['strategy_extension_origin'].items()if k!='dependency_handoff'}
                =={k:v for k,v in previous['strategy_extension_origin'].items()if k!='dependency_handoff'}
            and ('dependency_handoff'not in previous['strategy_extension_origin']or'dependency_handoff'in current['strategy_extension_origin']))
    before=_business(market_origin_configuration(previous,deadline=deadline))
    after=_business(market_origin_configuration(current,deadline=deadline))
    if ('takeover' in current)!=('takeover' in previous):
        # 准备器尚未注入原库存引用；实际Native配置会再次完整核此字段。
        before.pop('takeover',None);after.pop('takeover',None)
        # 材料准备尚未注入库存文件；原BASELINE和实际Native准入再完整核输入。
        for value in (before,after):
            parameters=value['strategies'][0]['parameters']['python_strategy']
            for name in ('input_file','input_sha256','capital_account','capital_market'):parameters.pop(name,None)
    return _same_business(before, after)


def predecessor_configuration(native, *, deadline=float('inf')):
    """返回材料已绑定的前代原配置，供状态身份使用其真实市场配置。"""
    selection=native['recovery']['transition'];raw=_read(Path(selection['file']),1024*1024,deadline=deadline,clock=time.monotonic)
    _require(hashlib.sha256(raw).hexdigest()==_sha(selection['sha256']))
    transition=_json(raw);body=_read(Path(transition['predecessor_configuration']),256*1024,deadline=deadline,clock=time.monotonic)
    _require(hashlib.sha256(body).hexdigest()==_sha(transition['predecessor_configuration_sha256']))
    return _json(body)



def restoration_origin(transition, *, deadline=float('inf')):
    """核部署者显式原件恢复材料；只读取原Native已接收的状态，不写金融文件。"""
    reference=transition.get('restoration')
    if reference is None:return None
    def pinned(reference,maximum):
        _require(type(reference)is dict and set(reference)=={'file','sha256'})
        raw=_read(_path(reference['file']),maximum,clock=time.monotonic,deadline=deadline)
        _require(hashlib.sha256(raw).hexdigest()==_sha(reference['sha256']))
        return _json(raw)
    value=pinned(reference,1024*1024)
    _require(type(value)is dict and set(value)=={'schema','current_clean_sha256','archive_directory','snapshot_admission','snapshot_transition'}
        and value['schema']=='guanheng.execution-restoration.v1')
    archive=_path(value['archive_directory']);_inspect(archive,directory=True)
    clean=pinned(dict(file=str(archive/'clean.json'),sha256=value['current_clean_sha256']),256*1024)
    _require(clean['schema']=='guanheng.cta-clean.v2'and clean['closed']is True
        and clean['closed_config_sha256']==transition['predecessor_configuration_sha256']
        and Path(clean['closed_receipt']).parent==Path(transition['predecessor_control_directory']))
    for name,h in clean['files'].items():
        relative=Path(name);_require(not relative.is_absolute()and '..'not in relative.parts)
        raw=_read(archive/relative,4*1024*1024,clock=time.monotonic,deadline=deadline);_require(hashlib.sha256(raw).hexdigest()==_sha(h))
    admitted=pinned(value['snapshot_admission'],256*1024);snapshot=pinned(value['snapshot_transition'],1024*1024)
    _require(admitted['schema']=='guanheng.cta-reconciled.v1'and admitted['admission_kind']=='clean_transition'
        and admitted['transition_sha256']==value['snapshot_transition']['sha256']
        and admitted['state_files']==snapshot['state_files']==transition['state_files'])
    admission_path=Path(value['snapshot_admission']['file']);_require(admission_path.name=='reconciled.json')
    ready=_json(_read(admission_path.parent/'ready.json',4096,clock=time.monotonic,deadline=deadline))
    _require(all(admitted[k]==ready[k]for k in ('control_id','config_sha256','pid')))
    origin=Path(snapshot['predecessor_control_directory']);_require(admitted['predecessor_control_id']==origin.name)
    raw=_read(origin/'execution.json',256*1024,clock=time.monotonic,deadline=deadline)
    _require(hashlib.sha256(raw).hexdigest()==snapshot['predecessor_configuration_sha256'])
    binding=_read(origin/'python-binding.json',256*1024,clock=time.monotonic,deadline=deadline)
    _require(hashlib.sha256(binding).hexdigest()==snapshot['predecessor_python_binding_sha256'])
    configuration=_json(raw);_require(configuration['trader']['writes_enabled']is False)
    return dict(configuration=configuration,configuration_sha256=snapshot['predecessor_configuration_sha256'],control_directory=origin,binding=_json(binding))


def initialization_abort_origin(transition, *, current=None, deadline=float('inf')):
    """核准入后、就绪前失败且状态未变的原owner，保留真实失败生命周期。"""
    reference=transition.get('initialization_abort')
    if reference is None:return None
    _require('restoration'not in transition and type(reference)is dict and set(reference)=={'file','sha256'})
    previous=_path(transition['predecessor_control_directory'])
    _require(_path(reference['file'])==previous/'reconciled.json'and not(previous/'ready.json').exists())
    def read(path,maximum):return _read(path,maximum,clock=time.monotonic,deadline=deadline)
    raw=read(previous/'reconciled.json',256*1024)
    _require(hashlib.sha256(raw).hexdigest()==_sha(reference['sha256']))
    admitted=_json(raw);failure=_json(read(previous/'failure.json',4096));closed=_json(read(previous/'close-prepared.json',4096))
    kind = admitted['admission_kind']
    _require(admitted['schema']=='guanheng.cta-reconciled.v1'
        and kind in ('clean_transition', 'process_lost_reconciled')
        and failure['schema']=='guanheng.execution.failure.v1'and failure['stage']=='cta'
        and closed['schema']=='guanheng.execution.close-prepared.v1'and closed['closed']is True
        and closed['ok']is False and closed['recovery_ready']is False)
    for value in (admitted,failure,closed):
        _require(value['control_id']==previous.name and value['config_sha256']==transition['predecessor_configuration_sha256']
            and value['pid']==failure['pid'])
    require_process_exited(failure['pid'])
    prior_raw=read(previous/'execution.json',256*1024)
    _require(hashlib.sha256(prior_raw).hexdigest()==transition['predecessor_configuration_sha256'])
    prior=_json(prior_raw)
    selected=prior['recovery']['transition'];snapshot_raw=read(_path(selected['file']),1024*1024)
    _require(hashlib.sha256(snapshot_raw).hexdigest()==selected['sha256']==admitted['transition_sha256'])
    snapshot=_json(snapshot_raw)
    _require(snapshot['schema']=='guanheng.execution-recovery-transition.v1'
        and not any(k in snapshot for k in ('restoration','initialization_abort'))
        and snapshot['state_files']==admitted['state_files']==transition['state_files'])
    origin=_path(snapshot['predecessor_control_directory']);_require(origin.name==admitted['predecessor_control_id'])
    config_raw=read(origin/'execution.json',256*1024);binding_raw=read(origin/'python-binding.json',256*1024)
    _require(hashlib.sha256(config_raw).hexdigest()==snapshot['predecessor_configuration_sha256']
        and hashlib.sha256(binding_raw).hexdigest()==snapshot['predecessor_python_binding_sha256'])
    configuration=_json(config_raw)
    _require(compatible_business_configuration(prior,configuration,deadline=deadline))
    if kind == 'process_lost_reconciled':
        prior_trader, source_trader = prior['trader'], configuration['trader']
        _require(current is None or current['trader'] == prior_trader)
        if prior_trader != source_trader:
            # 已接账且从未开放队列的只读代可继续停写，不能用该路径恢复写权限。
            _require(source_trader['writes_enabled'] is True
                     and prior_trader == dict(source_trader, writes_enabled=False)
                     and prior.get('execution_permission_origin') == {
                         'schema': 'guanheng.execution-permission-origin.v1',
                         'file': str(origin / 'execution.json'),
                         'sha256': snapshot['predecessor_configuration_sha256'],
                     })
        _validate_lost_initialization_abort(previous, origin, admitted, raw, failure, snapshot,
                                            configuration, transition, read)
        return dict(configuration=configuration,configuration_sha256=snapshot['predecessor_configuration_sha256'],
                    control_directory=origin,binding=_json(binding_raw))
    live = (configuration['trader']['writes_enabled'] or prior['trader']['writes_enabled']
            or current is not None and current['trader']['writes_enabled'])
    if live:
        # 已授权模式仅接续同一柜台与权限；完整零执行和原认领证明排除重复副作用。
        _require(prior['trader'] == configuration['trader']
                 and (current is None or current['trader'] == prior['trader']))
        _validate_idle_initialization(previous, failure)
        claim = _path(configuration['output_directory']) / ('.cta-reconciled-' + _sha(admitted['transition_sha256']) + '.json')
        _require(read(claim, 256 * 1024) == raw)
    terminal=_json(read(origin/'closed.json',4096));ready=_json(read(origin/'ready.json',4096))
    _require(ready['schema']=='guanheng.execution.ready.v1'and ready['control_id']==origin.name
        and ready['config_sha256']==snapshot['predecessor_configuration_sha256']and ready['pid']==terminal['pid'])
    _require(terminal['schema']=='guanheng.execution.closed.v2'and terminal['closed']is True
        and terminal['ok']is True and terminal['recovery_ready']is True and terminal['resources_closed']is True
        and terminal['exit_code']==0 and terminal['error_code']is None
        and terminal['control_id']==origin.name and terminal['config_sha256']==snapshot['predecessor_configuration_sha256'])
    consumed=_json(read(_path(configuration['output_directory'])/'.cta-clean.consumed.json',256*1024))
    _require(consumed['schema']=='guanheng.cta-clean.v2'and consumed['closed']is True
        and consumed['installation_sha256']==snapshot['predecessor_installation_sha256']
        and consumed['control_id']==origin.name and consumed['pid']==ready['pid']
        and consumed['closed_config_sha256']==snapshot['predecessor_configuration_sha256']
        and _path(consumed['closed_receipt'])==origin/'closed.json'and consumed['files']==transition['state_files'])
    return dict(configuration=configuration,configuration_sha256=snapshot['predecessor_configuration_sha256'],control_directory=origin,binding=_json(binding_raw))


def _validate_idle_initialization(previous, failure):
    """初始化未就绪且执行队列从未准入；只读和已授权模式共用原零副作用证据。"""
    queue = failure['execution_queue']
    counters = ('fault', 'accepted', 'entered', 'delivered', 'rejected', 'queued_commands', 'payload_bytes')
    _require(failure['closed'] is False and set(queue) == {*counters, 'accepting', 'inflight'}
             and queue['accepting'] is False and queue['inflight'] is False
             and all(type(queue[k]) is int and queue[k] == 0 for k in counters))
    _require(not any((previous / name).exists() for name in ('closed.json', 'lifecycle-started.json')))


def _validate_lost_initialization_abort(previous, origin, admitted, admission_raw, failure,
                                        snapshot, configuration, transition, read):
    """核原进程丢失交接及未进入执行的失败代，保留所有原收据。"""
    _validate_idle_initialization(previous, failure)
    _require(not any((origin / name).exists() for name in ('closed.json', 'close-prepared.json', 'failure.json')))
    _require(_path(snapshot['predecessor_configuration']) == origin / 'execution.json'
             and admitted['successor_installation_sha256'] == snapshot['successor_installation_sha256']
                 == transition['predecessor_installation_sha256'])
    output = _path(configuration['output_directory'])
    claim = output / ('.cta-reconciled-' + _sha(admitted['transition_sha256']) + '.json')
    _require(read(claim, 256 * 1024) == admission_raw)
    ready_raw = read(origin / 'ready.json', 4096)
    ready = _json(ready_raw)
    identity = dict(control_id=origin.name, config_sha256=snapshot['predecessor_configuration_sha256'],
                    pid=ready['pid'])
    loss = _json(read(origin / 'owner-loss.json', 4096))
    installed = _json(read(origin / 'installation-identity.json', 4096))
    _require(all(all(item.get(k) == v for k, v in identity.items()) for item in (ready, loss, installed))
             and ready['schema'] == 'guanheng.execution.ready.v1'
             and loss['schema'] == 'guanheng.execution.owner-loss.v1'
             and loss['reason'] == 'process_lost'
             and loss['ready_sha256'] == hashlib.sha256(ready_raw).hexdigest()
             and installed['schema'] == 'guanheng.execution-installation.v1'
             and installed['installation_sha256'] == snapshot['predecessor_installation_sha256'])
    require_process_exited(ready['pid'])


def state_origin(transition, *, current=None, deadline=float('inf')):
    """显式恢复和初始化失败分别核严格凭证，再提供原状态owner。"""
    _require(not('restoration'in transition and 'initialization_abort'in transition))
    return restoration_origin(transition,deadline=deadline)or initialization_abort_origin(
        transition,current=current,deadline=deadline)


def state_origin_configuration(native, *, deadline=float('inf')):
    """状态身份和初始观察沿被恢复原owner；真实最新进程前代仍独立保留。"""
    selection=native['recovery']['transition'];raw=_read(_path(selection['file']),1024*1024,clock=time.monotonic,deadline=deadline)
    _require(hashlib.sha256(raw).hexdigest()==selection['sha256']);value=_json(raw)
    origin=state_origin(value,current=native,deadline=deadline)
    return origin['configuration']if origin else predecessor_configuration(native,deadline=deadline)


def _normalized(binding):
    site = Path(binding['site_root'])
    prefix = Path(binding['python']).parent.parent
    result = {}
    for name, value in binding['files']:
        path = Path(name)
        key = ('site/' + path.relative_to(site).as_posix() if path.is_relative_to(site)
               else 'venv/' + path.relative_to(prefix).as_posix() if path.is_relative_to(prefix)
               else str(path))
        _require(key not in result)
        result[key] = _sha(value)
    return result


def _compatible_python(previous, current, *, strategy_upgrade=False, strategy_extension=False,
                       source_handoff=False):
    """同业务发行允许策略及数量实现升级；纯Core及解释器仍须逐件相同。

    strategy_upgrade仅由已核前后完整业务配置的transition路径传入。部署材料
    绑定实际前后源码，既有金融状态仍由当前原加载器校验，不能以换包改变账户、
    资本、输入、策略参数或输出根。
    """
    before,after=_normalized(previous),_normalized(current)
    from .strategy_profiles import SOURCE_OWNER_PACKAGES, PACKAGE_DISTRIBUTIONS
    def source_key(key, package):
        distribution = PACKAGE_DISTRIBUTIONS[package].replace('-', '_')
        return (key.startswith('site/'+package+'/')
                or key.startswith('site/'+distribution+'-') and key.endswith('.dist-info/METADATA'))
    # 首次接入须完整新增；既有owner的版本升级另要求同业务发行资格。
    first_source_owners = tuple(package for package in SOURCE_OWNER_PACKAGES
                                if not any(source_key(key, package) for key in before))
    for key in before.keys()|after.keys():
        if before.get(key)!=after.get(key):
            _require(key.startswith('site/guanheng_wt_runtime/')
                or key.startswith('site/guanheng_wt_runtime-')and key.endswith('.dist-info/METADATA')
                or key=='venv/pyvenv.cfg'
                or strategy_upgrade and (
                    key.startswith('site/guanheng_strategy_v1/')
                    or key.startswith('site/guanheng_strategy_v1-') and key.endswith('.dist-info/METADATA'))
                # 已核完整同业务transition才接纳数量实现升级；原冻结状态仍由NSQ构造器重验。
                or strategy_upgrade and (
                    key.startswith('site/guanheng_strategy_native/')
                    or key.startswith('site/guanheng_strategy_native-') and key.endswith('.dist-info/METADATA'))
                or strategy_extension and any(key.startswith('site/'+package+'/')
                    or key.startswith('site/'+package+'-') and key.endswith('.dist-info/METADATA')
                    for package in ('guanheng_strategy_original','guanheng_market_client'))
                # 两项资格共同允许通信实现升级；账户、权限、业务和原状态继续由原transition核同。
                or source_handoff and any(source_key(key, package) and (
                    strategy_upgrade or key not in before and key in after and package in first_source_owners)
                    for package in SOURCE_OWNER_PACKAGES))


def load_transition(native, identities=None, *, binding=None, deadline=float('inf')):
    """核固定前后代身份及原证据；返回前代代码身份，不修改原 KV。"""
    selection = native['recovery']
    _require(selection['mode'] == 'resume_reconciled')
    reference = selection['transition']
    _require(type(reference) is dict and set(reference) == {'file', 'sha256'})
    path = Path(reference['file']); _require(path.is_absolute())
    raw = _read(path, 1024 * 1024, deadline=deadline,clock=time.monotonic)
    _require(hashlib.sha256(raw).hexdigest() == _sha(reference['sha256']))
    value = _json(raw)
    required={'schema', 'predecessor_configuration', 'predecessor_configuration_sha256',
        'predecessor_control_directory', 'predecessor_installation_sha256', 'successor_installation_sha256',
        'predecessor_python_binding_sha256', 'successor_python_code_identity', 'state_files'}
    _require(required<=set(value)<=required|{'restoration','initialization_abort'}
        and value['schema'] == 'guanheng.execution-recovery-transition.v1')
    previous_configuration=predecessor_configuration(native,deadline=deadline)
    _require_storage_predecessor(native, previous_configuration, value['predecessor_control_directory'],
                                 value['predecessor_configuration_sha256'])
    _require(compatible_business_configuration(native,previous_configuration,deadline=deadline))
    previous = Path(value['predecessor_control_directory']); _inspect(previous, directory=True)
    old_raw = _read(previous / 'python-binding.json', 256 * 1024, deadline=deadline,clock=time.monotonic)
    _require(hashlib.sha256(old_raw).hexdigest() == _sha(value['predecessor_python_binding_sha256']))
    old = _json(old_raw)
    _require(old['schema'] == 'guanheng.cta-python-binding.v1')
    if identities is not None:
        _require(binding is not None and digest(identities) == value['successor_python_code_identity'])
        # 上文已核显式发行材料和完整业务配置；换实现属于发行，不要求改零持仓角色。
        from .strategy_profiles import source_handoff
        source_owners = source_handoff(native, deadline=deadline)
        _compatible_python(old,binding,strategy_upgrade=True,
            strategy_extension='strategy_extension_origin'in native,source_handoff=source_owners)
    restored=state_origin(value,current=native,deadline=deadline)
    if restored is not None and identities is not None:
        _compatible_python(restored['binding'],binding,strategy_upgrade=True,
            strategy_extension='strategy_extension_origin'in native,source_handoff=source_owners)
    return value, digest(dict((restored['binding']if restored else old)['files']))


def strategy_state_mode(native, strategy_id, *, deadline=float('inf')):
    """从已核恢复源确定新增ctx首次初始化或既有ctx恢复；不读取/重置策略资金。"""
    if 'strategy_extension_origin'not in native:return None
    strategy_extension_configuration(_storage_model(native),deadline=deadline)
    mode=native['recovery']['mode']
    if mode=='resume_clean':return 'resume'
    _require(mode=='resume_reconciled')
    transition,unused=load_transition(native,deadline=deadline)
    origin=state_origin_configuration(native,deadline=deadline)
    prior = next((row for row in origin['strategies'] if row['id'] == strategy_id), None)
    names = (f'stradata/{strategy_id}.json', f'userdata/ud_{strategy_id}.json')
    files = transition['state_files']
    if prior is not None:
        if names[0] not in files:
            profile = prior['parameters']['python_strategy']['schema']
            if profile != 'guanheng.original-live-cta.v1' or names[1] not in files:
                raise ValueError('recovery_missing_strategy_state')
            raw = _read(Path(origin['output_directory']) / names[1], 4 * 1024 * 1024,
                        clock=time.monotonic, deadline=deadline)
            if hashlib.sha256(raw).hexdigest() != files[names[1]]:
                raise ValueError('recovery_strategy_userdata_digest')
            state = _json(_json(raw)['guanheng.quantity.state.v1'].encode('ascii'))
            empty = {'sequence': 0, 'plan': None, 'buys': [], 'sells': [], 'last_date': None,
                     'last_source': None, 'consumed_sha': None, 'consumed_codes': {},
                     'intent_known_at': None, 'intent_prices': {}}
            if (state.get('schema') != 'guanheng.original-live-intent.v1'
                    or type(state.get('sequence')) is not int
                    or any(key not in state or state[key] != value for key, value in empty.items())
                    or state.get('atr_protection', {}) != {}):
                raise ValueError('recovery_strategy_targets_required')
        return 'resume'
    added = _extension_row(native, deadline=deadline)
    _require(added is not None and strategy_id == added['id']
        and all(name.casefold()not in {key.casefold()for key in transition['state_files']}for name in names))
    return 'new'


def prior_strategy_observations(native, strategy_id, *, deadline):
    """沿已绑定的原恢复链读取原件；只提供旧观察与原摘要，不授估值/现金资格。

    消费方核当前账、数量和周期。每一跳先核原配置SHA及相同业务配置，最多16跳；
    缺原件或链冲突由调用者保留资金未知，原金融状态与恢复准入保持独立。
    """
    current, visited = native, set()
    for unused in range(16):
        _require(time.monotonic() < deadline)
        if current.get('recovery', {}).get('mode') != 'resume_reconciled':
            return
        transition, unused_identity = load_transition(current, deadline=deadline)
        restored=state_origin(transition,deadline=deadline)
        previous = restored['control_directory']if restored else Path(transition['predecessor_control_directory'])
        _require(previous not in visited)
        visited.add(previous)
        path = previous/'execution.json'
        expected_sha=restored['configuration_sha256']if restored else transition['predecessor_configuration_sha256']
        _require(path == previous / 'execution.json')
        raw = _read(path, 256 * 1024, deadline=deadline,clock=time.monotonic)
        _require(hashlib.sha256(raw).hexdigest() == expected_sha)
        prior = _json(raw)
        _require(compatible_business_configuration(current,prior,deadline=deadline))
        ready = _json(_read(previous / 'ready.json', 4096, deadline=deadline,clock=time.monotonic))
        body = _read(previous / 'strategies.json', 1024 * 1024, deadline=deadline,clock=time.monotonic)
        report = _json(body)
        _require(report['control_id'] == ready['control_id'] and report['pid'] == ready['pid']
            and report['config_sha256'] == ready['config_sha256'] == hashlib.sha256(raw).hexdigest())
        observation = report['strategies'].get(strategy_id)
        if type(observation) is dict:
            yield observation, dict(path=str(previous / 'strategies.json'),
                sha256=hashlib.sha256(body).hexdigest(), control_id=ready['control_id'])
        current = prior


def execution_state_files(root):
    """读取原生金融状态 JSON，返回原接续协议使用的相对路径与字节摘要。"""
    files = {}
    for directory in ('stradata', 'userdata', 'portfolio'):
        folder = root / directory
        if not folder.exists():
            continue
        _inspect(folder, directory=True)
        for path in sorted(folder.iterdir()):
            _inspect(path)
            if path.suffix.lower() == '.json':
                files[path.relative_to(root).as_posix()] = hashlib.sha256(_read(path, 4 * 1024 * 1024)).hexdigest()
    _require(files and len(files) <= 1536)
    return files


def _require_storage_predecessor(native, previous, predecessor_control, predecessor_sha):
    from .private_storage import configured_private_copy
    private = configured_private_copy(native)
    prior = configured_private_copy(previous)
    if native.get('output_directory') == previous.get('output_directory'):
        _require(native.get('private_storage_origin') == previous.get('private_storage_origin'))
        return
    if Path(native['output_directory']) == Path(previous['output_directory']):
        _require(native.get('private_storage_origin') == previous.get('private_storage_origin'))
    else:
        _require(prior is None and private is not None
                 and _path(private['original_output']) == _path(previous['output_directory'])
                 and _path(private['predecessor_control']) == Path(predecessor_control)
                 and private['predecessor_configuration_sha256'] == predecessor_sha)


def prepare_transition(configuration, predecessor_configuration, predecessor_control, destination, *,
                       successor_python=None, initialization_abort=False):
    """冻结发行交接材料；只读取上代状态，实际准入由持有租约的 Native 再核。"""
    from .execution_process import PythonExecutionProcessConfig
    configuration, predecessor_configuration, predecessor_control, destination = map(
        Path, (configuration, predecessor_configuration, predecessor_control, destination))
    native = _json(_read(configuration, 256 * 1024))
    old_raw = _read(predecessor_configuration, 256 * 1024)
    old = _json(old_raw)
    _require(compatible_business_configuration(native,old))
    root = Path(native['output_directory'])
    _require_storage_predecessor(native, old, predecessor_control, hashlib.sha256(old_raw).hexdigest())
    marker = root / '.cta-clean.json'
    if root != Path(old['output_directory']):
        from .private_storage import configured_private_copy, pending_target_marker
        _require(not initialization_abort)
        copy = configured_private_copy(native)
        marker = pending_target_marker(root, copy['native_files']['.cta-clean.json'])
    current = PythonExecutionProcessConfig.load(Path(native['installation_root']).parent,
        configuration, predecessor_control.parent)
    identities = dict(current.python_files)
    if successor_python is not None:
        import sys
        interpreter = Path(successor_python)
        # 部署解释器是发行身份的一部分；材料生成CLI与无窗口owner可使用不同入口。
        _require(interpreter.parent == current.pythonw.parent and interpreter.name.lower() in ('python.exe', 'pythonw.exe'))
        identities.pop(str(current.pythonw))
        identities[str(interpreter)] = hashlib.sha256(_read(interpreter, 32 * 1024 * 1024)).hexdigest()
        base = Path(sys._base_executable)
        identities.pop(str(base))
        successor_base = base.with_name(interpreter.name)
        identities[str(successor_base)] = hashlib.sha256(_read(successor_base, 32 * 1024 * 1024)).hexdigest()
    binding = _read(predecessor_control / 'python-binding.json', 256 * 1024)
    if marker.exists():
        origin = _json(_read(marker, 256 * 1024))
        old_installation = origin['installation_sha256']
    elif (predecessor_control / 'installation-identity.json').exists():
        origin = _json(_read(predecessor_control / 'installation-identity.json', 4096))
        old_installation = origin['installation_sha256']
    elif (predecessor_control / 'reconciled.json').exists():
        origin = _json(_read(predecessor_control / 'reconciled.json', 256 * 1024))
        old_installation = origin['successor_installation_sha256']
    else:
        origin = _json(_read(root / '.cta-clean.consumed.json', 256 * 1024))
        old_installation = origin['installation_sha256']
    manifest = _json(_read(current.installation / 'execution-install.json', 256 * 1024))
    files = execution_state_files(root)
    value = dict(
        schema='guanheng.execution-recovery-transition.v1',  # 固定发行交接协议；不代表上次正常退出。
        predecessor_configuration=str(predecessor_configuration),  # 前代实际Native配置的绝对路径。
        predecessor_configuration_sha256=hashlib.sha256(old_raw).hexdigest(),  # 前代原配置字节摘要。
        predecessor_control_directory=str(predecessor_control),  # 原ready/关闭或故障收据所在目录。
        predecessor_installation_sha256=old_installation,  # 原owner保存的完整安装清单摘要。
        successor_installation_sha256=digest(manifest['files']),  # 本代完整安装清单摘要。
        predecessor_python_binding_sha256=hashlib.sha256(binding).hexdigest(),  # 原Python绑定文件字节摘要。
        successor_python_code_identity=digest(identities),  # 实际部署解释器与源码集合的规范身份。
        state_files=files)  # 原金融JSON相对路径到字节摘要；仅作准入证据，不生成账本。
    if initialization_abort:
        admission = predecessor_control / 'reconciled.json'
        value['initialization_abort'] = dict(file=str(admission),
            sha256=hashlib.sha256(_read(admission, 256 * 1024)).hexdigest())
        initialization_abort_origin(value, current=native)
        spent = root / ('.cta-initialization-abort-' + predecessor_control.name + '.json')
        _require(not spent.exists() and not spent.with_suffix('.json.pending').exists())
    raw = canonical(value)
    with destination.open('xb') as stream:
        stream.write(raw)
    return dict(file=str(destination), sha256=hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='冻结自有执行故障恢复发行交接材料；不启动或修改金融状态')
    for name in ('configuration', 'predecessor-configuration', 'predecessor-control', 'destination'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--successor-python', type=Path, required=True, help='正式owner实际使用的解释器入口')
    parser.add_argument('--initialization-abort', action='store_true', help='沿已接收状态和就绪前失败收据准备后继')
    args = parser.parse_args()
    print(json.dumps(prepare_transition(args.configuration, args.predecessor_configuration,
        args.predecessor_control, args.destination, successor_python=args.successor_python,
        initialization_abort=args.initialization_abort)))
