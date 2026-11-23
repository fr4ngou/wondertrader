"""独立WT发布状态的只读消费者；文件快照不承担进程存活或交易事实证明。"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import hashlib
import re
from time import monotonic, sleep
from uuid import UUID

from guanheng_market_client.runtime_status import CollectionStatusPending, read_status_snapshot

_STATES = {
    'disabled': '未配置', 'new': '待启动', 'starting': '启动中', 'ready': '已就绪',
    'stopping': '停止中', 'closed': '已停止', 'faulted': '失败',
}
_COMPONENTS = {'host': 'QMT通信', 'trade_host': '交易通信', 'account_host': '账户通信',
               'analysis_host': '策略数据通信', 'analysis_batch_host': '市场数据通信',
               'account_observation': '账户结果更新',
               'history': '历史查询', 'collection': '行情采集', 'analysis_window': '策略数据更新',
               'execution': '策略执行'}
_DATA_PHASES = {'constructed': '数据更新尚未开始', 'waiting_source': '等待策略数据通信',
                'reading_source': '正在读取策略数据', 'native_refresh': '正在更新策略数据',
                'published': '策略数据已发布', 'failed': '策略数据更新失败', 'stopped': '策略数据更新已停止'}
_NOTE = '以下为WT最近发布的状态；当前存活、来源连接、行情时效和策略执行结果需分别核实。'


def _require(value):
    if not value:
        raise ValueError('WT状态读取配置或协议无效')


@dataclass(frozen=True)
class RuntimeObservationConfig:
    """一次业务读取固定的路径与身份；构造不创建运行owner。"""
    # 本代公开status.json绝对路径，文件读取沿SDK共享删除句柄。
    path: Path
    # 本代控制UUID，必须与状态发布者相同。
    control_id: str
    # 逻辑实例UUID，允许正常重启后沿发布者原语义保持。
    instance_id: str
    # 本代配置原字节SHA256，64位小写十六进制。
    configuration_sha256: str

    @classmethod
    def from_settings(cls, settings):
        current = getattr(settings, 'wt_current_file', '')
        if current:
            _require(type(current) is str and Path(current).is_absolute())
            return RuntimeCurrentFile(Path(current))
        values = (settings.wt_status_file, settings.wt_control_id, settings.wt_instance_id,
                  settings.wt_configuration_sha256)
        if not any(values):
            return None
        _require(all(type(value) is str and value for value in values))
        path, control, instance, digest = values
        _require(Path(path).is_absolute() and Path(path).name == 'status.json')
        _require(str(UUID(control)) == control and str(UUID(instance)) == instance)
        _require(re.fullmatch('[a-f0-9]{64}', digest) is not None)
        return cls(Path(path), control, instance, digest)


@dataclass(frozen=True)
class RuntimeCurrentFile:
    """只保存公开指针的位置；App启动时允许文件尚未发布。"""
    # 运行侧原子发布的CURRENT绝对路径；消费者只有读权限职责。
    path: Path


def _read_snapshot(path, deadline, max_bytes=65536):
    """沿原SDK句柄与同一次截止处理发布替换，不回退到旧文件或旧身份。"""
    while True:
        if monotonic() >= deadline:
            raise TimeoutError('WT状态读取超过本次时间')
        try:
            snapshot = read_status_snapshot(path, max_bytes)
            break
        except CollectionStatusPending:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError('WT状态读取超过本次时间') from None
            sleep(min(.01, remaining))
    if monotonic() >= deadline:
        raise TimeoutError('WT状态读取超过本次时间')
    return snapshot


def resolve_runtime_configuration(configuration, deadline):
    """每次业务读取入口解析一次CURRENT，后续根/结果复核共用同一四身份。"""
    if not isinstance(configuration, RuntimeCurrentFile):
        return configuration
    value = _read_snapshot(configuration.path, deadline, 65536).value
    fields = {'wt_status_file', 'wt_control_id', 'wt_instance_id', 'wt_configuration_sha256'}
    _require(type(value) is dict and set(value) == fields | {'schema'}
             and value['schema'] == 'guanheng.wt-current.v1')
    from types import SimpleNamespace
    result = RuntimeObservationConfig.from_settings(SimpleNamespace(**{key: value[key] for key in fields}))
    _require(isinstance(result, RuntimeObservationConfig))
    return result


def _published_state(value, *, component=False):
    """只复制有限状态，不传播原错误码、诊断值和私有进程信息。"""
    _require(type(value) is dict)
    state, ready = value.get('state'), value.get('ready')
    _require(type(state) is str and state in _STATES and type(ready) is bool)
    _require(component or state != 'disabled')
    _require(not ready or state == 'ready')
    result = dict(state=state, label=_STATES[state], ready=ready)
    if component:
        for field in ('pending', 'forced'):
            flag = value.get(field)
            _require(type(flag) is bool)
            result[field] = flag
    return result


def execution_startup_status(component):
    """投影等待监督器与实际执行器的区别；旧发布缺此扩展时沿原生命周期。

    返回页面的state、label和reason，不修改WT生命周期或赋予交易资格。
    父实例的停止/故障由调用者优先处理，未知字段不复制到公开说明。
    """
    if component.get('state') != 'ready' or 'source_wait_state' not in component:
        return None
    phase, ready = component.get('source_wait_state'), component.get('execution_ready')
    if (phase == 'execution_started' and ready is True
            and type(component.get('pid')) is int and component['pid'] > 0
            and type(component.get('business_observation')) is dict):
        return None
    if ready is False:
        if (phase == 'waiting_source' and component.get('pid') is None
                and component.get('business_observation') is None):
            return dict(state='starting', label='等待QMT连接，策略执行尚未启动',
                        reason='WT等待QMT接入认证；连接恢复后沿原流程启动执行器。')
        if phase == 'starting_execution':
            return dict(state='starting', label='正在启动策略执行器',
                        reason='QMT接入认证已通过，正在恢复原账并初始化策略执行器。')
    return dict(state='unavailable', label='策略执行启动状态待核实',
                reason='WT发布的执行启动阶段与就绪信息不一致，当前交易运行资格保持未知。')


def _analysis_data(value):
    """仅投影原发布者的阶段及最后成功时间；不由服务ready推导数据或新鲜度。

    扩展缺失/无效仅使本项数据未知，公共生命周期仍由原状态合同校验。
    原last_success中的路径、摘要和来源诊断始终留在运行侧。
    """
    missing = dict(state='unavailable', label='策略数据状态暂不可用', ready=None,
                   basis_date=None, published_at=None)
    try:
        ready, phase, success = value.get('data_ready'), value.get('phase'), value.get('last_success')
        _require(type(ready) is bool and type(phase) is str and bool(phase))
        _require((success is not None) == ready)
        _require(phase != 'published' or ready)
        basis = published = None
        if ready:
            _require(type(success) is dict)
            basis, published = success.get('basis_date'), success.get('published_at')
            _require(type(basis) is str and date.fromisoformat(basis).isoformat() == basis)
            _require(type(published) is str and datetime.fromisoformat(published).utcoffset() is not None)
        return dict(state='available', label=_DATA_PHASES.get(phase, '策略数据更新阶段待确认'),
                    ready=ready, basis_date=basis, published_at=published)
    except (ValueError, TypeError, OverflowError):
        return missing


def _failure_details(name, value):
    """首次与同时报告共用已发布的关闭细节，防止关系标签掩盖超时或回收事实。"""
    label = _COMPONENTS.get(name, '其他运行组件')
    code = value.get('error_code')
    if type(code) is str and code == 'stop_timeout':
        return label + '停止超时' + ('，已使用强制回收' if value['forced'] else '')
    if value['forced']:
        return label + '报告过强制回收，正常关闭资格待核查'
    return None


def _runtime_issue(value):
    """解释原发布者的首先报告；该顺序不提供因果根因或当前存活证明。"""
    if value['state'] not in ('faulted', 'stopping'):
        return None, None
    code = value.get('error_code')
    first = next((name for name in value['components']
                  if type(code) is str and code == 'component_close_' + name), None)
    if first is not None:
        label = _COMPONENTS.get(first, '其他运行组件')
        summary = _failure_details(first, value['components'][first]) or label + '未完成正常关闭'
        return dict(relation='first_reported', summary=summary,
                    impact='本次系统正常停止尚未完成，各工作区的数据时间需分别核对。',
                    action='由维护人员核对该服务的原关闭记录、资源回收结果和未决责任。'), first
    if value['state'] == 'faulted':
        return dict(relation='unattributed', summary='运行侧已报告故障，具体原因尚待核查',
                    impact='当前运行资格需按原发布记录核实，已发布数据不代表服务仍在运行。',
                    action='由维护人员在受控运行目录核对原故障记录，按WT手册处理。'), None
    return None, None


def _component_issue(name, value, first):
    """只解释白名单状态/错误，正常停止等待不升级为故障；原诊断保持受控。"""
    if name == first or value['state'] != 'faulted' and not value['forced']:
        return None
    label = _COMPONENTS.get(name, '其他运行组件')
    summary = _failure_details(name, value) or label + '已报告故障，具体原因尚待核查'
    return dict(relation='also_reported' if first is not None else 'unattributed', summary=summary,
                impact='该服务的正常完成情况尚未确认；最后发布数据及其时间需单独核对。',
                action='由维护人员核对该服务的原停止记录和资源回收结果，保留原运行身份。')


def read_runtime_snapshot(configuration, deadline):
    """内部共享读取边界：核固定运行身份及已声明组件，返回同句柄SDK快照。"""
    _require(configuration is not None)
    configuration = resolve_runtime_configuration(configuration, deadline)
    snapshot = _read_snapshot(configuration.path, deadline)
    value = snapshot.value
    _require(value.get('schema') == 'guanheng.wt-runtime-status.v1'
             and value.get('control_id') == configuration.control_id
             and value.get('instance_id') == configuration.instance_id
             and value.get('configuration_sha256') == configuration.configuration_sha256
             and type(value.get('pid')) is int and 0 < value['pid'] < 2**32)
    _published_state(value)
    components = value.get('components')
    _require(type(components) is dict and bool(components))
    _require(all(type(name) is str and re.fullmatch('[a-z][a-z0-9_-]*', name) for name in components))
    for component in components.values():
        _published_state(component,component=True)
    return snapshot


def read_execution_reference(runtime, deadline):
    """共用NRT-R20身份边界，返回原引用与结果路径；缺定位表示尚未发布。

    只核公开引用和原ready，不读取策略、配置、账本或启动执行owner。
    调用方读取业务文件后须复核同一固定WRI的执行引用及PID。
    """
    from .managed_local_process import _inspect

    execution = runtime['components'].get('execution')
    reference = execution.get('business_observation') if execution else None
    if reference is None:
        return None, None
    _require(type(reference) is dict and set(reference) == {
        'schema', 'control_id', 'config_sha256', 'pid', 'path', 'ready_path'}
        and reference['schema'] == 'guanheng.execution-observation-reference.v1')
    control, digest, pid = reference['control_id'], reference['config_sha256'], reference['pid']
    _require(type(control) is str and str(UUID(control)) == control and type(digest) is str
        and re.fullmatch('[a-f0-9]{64}', digest) is not None
        and type(pid) is int and 0 < pid < 2**32 and execution.get('pid') == pid)
    _require(type(reference['path']) is str and type(reference['ready_path']) is str)
    path, ready_path = Path(reference['path']), Path(reference['ready_path'])
    _require(path.is_absolute() and ready_path.is_absolute() and path.name == 'strategies.json'
        and ready_path.name == 'ready.json' and path.parent == ready_path.parent and path.parent.name == control)
    _inspect(path.parent, directory=True)
    ready = _read_snapshot(ready_path, deadline, 4096).value
    _require(type(ready) is dict and set(ready) == {'schema', 'control_id', 'config_sha256', 'pid', 'closed'}
        and ready['schema'] == 'guanheng.execution.ready.v1' and ready['closed'] is False
        and ready.get('control_id') == control and ready.get('config_sha256') == digest
        and type(ready.get('pid')) is int and ready['pid'] == pid)
    return reference, path


def _execution_control(configuration, before, deadline):
    """按已准入代读取配置开关；局部失败只降级此字段，原请求截止保持。

    该布尔值描述原执行配置，不代替生命周期、来源许可及交易风控。
    每轮最多读取一个256KiB不可变配置，工作量与成交历史无关。
    """
    from .managed_local_process import _read, _json

    missing = dict(
        state='unavailable',  # 本代执行配置是否核实；缺失与配置关闭分开。
        writes_enabled=None,  # 原trader.writes_enabled，未知为null，不猜测默认值。
        label='WT下单开关暂不可核实',  # 固定中文说明，原配置和异常正文保持私有。
    )
    try:
        reference, path = read_execution_reference(before, deadline)
        if reference is None:
            return missing
        raw = _read(path.with_name('execution.json'), 256 * 1024, clock=monotonic, deadline=deadline)
        _require(hashlib.sha256(raw).hexdigest() == reference['config_sha256'])
        config = _json(raw)
        _require(type(config) is dict and config.get('schema_version') == 'guanheng.cta-execution.v1'
            and type(config.get('trader')) is dict and type(config['trader'].get('writes_enabled')) is bool)
        after = read_runtime_snapshot(configuration, deadline).value
        execution = after['components'].get('execution', {})
        _require(after['pid'] == before['pid'] and execution.get('business_observation') == reference
            and execution.get('pid') == reference['pid'])
        enabled = config['trader']['writes_enabled']
        return dict(state='available', writes_enabled=enabled,
            label='WT下单开关已开启' if enabled else 'WT下单开关已关闭')
    except (ValueError, OSError, KeyError, TypeError, OverflowError):
        if monotonic() >= deadline:
            raise TimeoutError('WT状态读取超过本次时间') from None
        return missing


def observe_runtime(configuration, deadline):
    """原有界读池调用，单次SDK读取前后核同一monotonic秒截止。

    Windows原子替换沿SDK共享删除协议，短暂Pending由统一读取接缝在原D内接续；
    路径及控制身份由安装配置固定。本函数只读，不推断进程/PID存活。
    """
    if configuration is None:
        return dict(state='unconfigured', reason='尚未配置独立WT状态读取',
                    published_at=None, runtime=None)
    configuration = resolve_runtime_configuration(configuration, deadline)
    snapshot = read_runtime_snapshot(configuration,deadline)
    value = snapshot.value
    runtime = _published_state(value)
    components = value.get('components')
    runtime['issue'], first = _runtime_issue(value)
    names = [name for name in _COMPONENTS if name in components]
    names.extend(name for name in components if name not in _COMPONENTS)
    runtime['components'] = []
    for name in names:
        component = components[name]
        published = _published_state(component, component=True)
        if name == 'execution' and value['state'] == 'ready':
            startup = execution_startup_status(component)
            if startup is not None:
                published['label'] = startup['label']
        runtime['components'].append(dict(name=name, display_name=_COMPONENTS.get(name, '其他运行组件'),
            **published, issue=_component_issue(name, component, first),
            data=_analysis_data(component) if name == 'analysis_window' else None,
            execution_control=_execution_control(configuration, value, deadline) if name == 'execution' else None))
    return dict(state='available', reason=_NOTE,
                published_at=datetime.fromtimestamp(snapshot.modified_epoch_ns / 1e9, timezone.utc).isoformat(),
                runtime=runtime)


def router(settings):
    """只读HTTP投影；共享App读池/原2秒总截止，读取失败固定503且不返回残缺快照。"""
    import asyncio
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import JSONResponse
    from .operations import utc_now

    configuration, invalid = None, False
    try:
        configuration = RuntimeObservationConfig.from_settings(settings)
    except (ValueError, TypeError):
        invalid = True
    routes = APIRouter()
    path = '/v1/ui/wt-runtime'

    @routes.get(path)
    async def status(request: Request):
        if (request.query_params or request.headers.get('content-length', '0') != '0'
                or request.headers.get('transfer-encoding')):
            raise HTTPException(422, 'WT状态只读取已配置的实例，不接受额外参数')
        future = None
        deadline = monotonic() + 2
        try:
            if invalid:
                raise ValueError('invalid configuration')
            future = request.app.state.reader.submit(lambda _remaining: observe_runtime(configuration, deadline), deadline)
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            value = await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline - monotonic()))
            return JSONResponse(headers={'Cache-Control': 'no-store'}, content=dict(
                schema_version='guanheng.wt-runtime-observation.v1', read_only=True,
                observed_at=utc_now(), **value))
        except Exception:
            return JSONResponse({'detail': '独立WT状态暂时无法读取，请核对读取配置和当前运行实例后重试。'},
                status_code=503, headers={'Cache-Control': 'no-store'})
        finally:
            if future is not None:
                future.cancel()

    @routes.api_route(path, methods=['POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'])
    async def read_only():
        return JSONResponse({'detail': 'WT状态仅提供只读查询'}, status_code=405,
                            headers={'Allow': 'GET', 'Cache-Control': 'no-store'})
    return routes
