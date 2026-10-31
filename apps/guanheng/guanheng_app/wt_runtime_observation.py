"""独立WT发布状态的只读消费者；文件快照不承担进程存活或交易事实证明。"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import re
from time import monotonic
from uuid import UUID

from guanheng_market_client.runtime_status import read_status_snapshot

_STATES = {
    'disabled': '未配置', 'new': '待启动', 'starting': '启动中', 'ready': '基础就绪',
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
    """安装时固定的只读路径与运行身份；构造不读取文件、不创建运行owner。"""
    path: Path
    control_id: str
    instance_id: str
    configuration_sha256: str

    @classmethod
    def from_settings(cls, settings):
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
    if monotonic() >= deadline:
        raise TimeoutError('WT状态读取超过本次时间')
    snapshot = read_status_snapshot(configuration.path)
    if monotonic() >= deadline:
        raise TimeoutError('WT状态读取超过本次时间')
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


def observe_runtime(configuration, deadline):
    """原有界读池调用，单次SDK读取前后核同一monotonic秒截止。

    Windows原子替换沿SDK共享删除协议；路径及控制身份由安装配置固定。
    本函数没有停止、订阅或重试操作，也不推断进程/PID存活。
    """
    if configuration is None:
        return dict(state='unconfigured', reason='尚未配置独立WT状态读取',
                    published_at=None, runtime=None)
    snapshot = read_runtime_snapshot(configuration,deadline)
    value = snapshot.value
    runtime = _published_state(value)
    components = value.get('components')
    runtime['issue'], first = _runtime_issue(value)
    names = [name for name in _COMPONENTS if name in components]
    names.extend(name for name in components if name not in _COMPONENTS)
    runtime['components'] = [dict(name=name, display_name=_COMPONENTS.get(name, '其他运行组件'),
        **_published_state(components[name], component=True),
        issue=_component_issue(name, components[name], first),
        data=_analysis_data(components[name]) if name == 'analysis_window' else None) for name in names]
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
