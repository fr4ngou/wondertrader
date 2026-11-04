"""账户、策略与实例的只读页面投影；原金融值和生命周期各归原发布者。"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import os
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

from .strategy_catalog import strategy_definition
from .wt_runtime_observation import (RuntimeObservationConfig, RuntimeCurrentFile, read_runtime_snapshot,
    observe_runtime, resolve_runtime_configuration)
from .reading import ReadCapacityError
from guanheng_market_client.runtime_status import read_status_snapshot


def _missing(reason):
    return dict(value=None, reason=reason)


def _execution_lifecycle(reference, deadline):
    """沿已核执行引用读固定生命周期回执；旧执行器缺少回执时保持原未知字段。"""
    if reference is None:
        return {}
    result = {}
    for event, closed in (('started', False), ('finished', True)):
        if monotonic() >= deadline:
            break
        path = Path(reference['path']).with_name('lifecycle-'+event+'.json')
        try:
            value = read_status_snapshot(path, 4096).value
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            result['execution_'+event+'_at'] = ''
            continue
        expected = {'schema', 'control_id', 'config_sha256', 'pid', 'closed', 'event_at'}
        if (not isinstance(value, dict) or set(value) != expected
            or value['schema'] != 'guanheng.execution.'+event+'.v1'
            or any(value[key] != reference[key] for key in ('control_id','config_sha256','pid'))
            or value['closed'] is not closed):
            result['execution_'+event+'_at'] = ''
            continue
        result['execution_'+event+'_at'] = value['event_at']
    return result


def project_execution(runtime, strategy, report=None):
    """ready表示原组件就绪；实际策略结果另验，文件mtime不充当运行开始时间。"""
    component = runtime['components'].get('execution') if runtime else None
    state = 'unconfigured' if runtime is None else 'not_started' if component is None else component['state']
    if component and runtime['state'] in ('stopping', 'closed', 'faulted'):
        state = runtime['state']
    labels = dict(unconfigured='尚未配置策略运行读取', not_started='策略未启动', disabled='策略未启动',
        new='策略待启动', starting='策略启动中', ready='策略执行组件已就绪',
        stopping='策略停止中', closed='策略已停止', faulted='策略运行失败', unavailable='策略状态暂不可用')
    if state == 'ready' and strategy:
        label = ('运行中 · 等待新行情' if strategy.get('status') == 'waiting_market_input'
            else 'WT已发布策略计算结果' if strategy.get('decision_at') is not None else strategy['status_label'])
    else:
        label = labels[state]
    started_at = _missing('WT现有公开结果未提供本次策略启动时间。')
    duration = _missing('缺少策略启动时间，无法确定运行时长。')
    # 启动时间由原生执行器session.start成功后发布；资金基准与文件mtime分别解释。
    origin = report.get('execution_started_at') if isinstance(report, dict) else None
    if origin is not None:
        try:
            if not isinstance(origin, str) or not 1 <= len(origin) <= 64:
                raise ValueError('strategy_start_time')
            stamp = datetime.fromisoformat(origin)
            now = datetime.now(timezone.utc)
            if stamp.utcoffset() is None or stamp > now:
                raise ValueError('strategy_start_time')
            started_at = dict(value=origin, reason=None)
        except (ValueError, TypeError, OverflowError):
            started_at = _missing('本次发布的策略启动时间格式无效。')
            duration = _missing('启动时间未通过校验，运行时长保持未知。')
        else:
            end = report.get('execution_finished_at')
            if end is not None:
                try:
                    finished = datetime.fromisoformat(end)
                    if finished.utcoffset() is None or not stamp <= finished <= now:
                        raise ValueError('strategy_finish_time')
                    duration = dict(value=int((finished-stamp).total_seconds()), reason=None)
                except (ValueError, TypeError, OverflowError):
                    duration = _missing('停止时间未通过校验，运行时长保持未知。')
            else:
                duration = (dict(value=int((now-stamp).total_seconds()), reason=None) if state == 'ready'
                    else _missing('策略当前未运行；原发布未提供停止时间，运行时长保持未知。'))
    return dict(state=state, label=label,
        reason='当前WT实例未配置策略执行器；账户持仓可独立查看。' if state == 'not_started'
            else '运行状态以WT最近发布为准，组件就绪与策略计算结果分别核实。',
        started_at=started_at, duration_seconds=duration)


def observe_details(settings, configuration, deadline):
    from .wt_business_observation import read_business, observe_account
    from .strategy_runtime_projection import project_strategy
    from .account_publication import observe_published_account

    # CURRENT读取失败沿503保留浏览器原成功结果；同轮账户与策略共用本代身份。
    configuration = resolve_runtime_configuration(configuration, deadline)
    runtime = None
    runtime_error = False
    try:
        runtime = read_runtime_snapshot(configuration, deadline).value if configuration else None
    except (ValueError, OSError, TimeoutError):
        runtime_error = True
    account = None
    account_reason = None
    try:
        operation = observe_published_account if settings.account_source == 'wt_account_publication' else observe_account
        account = operation(configuration, deadline).model_dump(mode='json')
    except (ValueError, OSError, TimeoutError):
        account_reason = '账户结果本次读取失败，请核对WT账户发布；策略状态单独显示。'

    strategy, report, lifecycle = None, None, {}
    strategy_reason = None
    if runtime and 'execution' in runtime['components']:
        try:
            strategies, _reference, _state = read_business(configuration, deadline)
            if strategies is not None:
                strategy = project_strategy(dict(schema='guanheng.configured-cta-observation.v1', strategies=strategies),runtime_state=_state)
                report = strategies.get('resonance-regime-v1') if strategy else None
                lifecycle = _execution_lifecycle(_reference, deadline)
        except (ValueError, OSError, TimeoutError, KeyError, TypeError):
            strategy_reason = '策略计算结果本次读取失败，账户数据保持独立。'
    execution = project_execution(runtime, strategy, dict(report or {}, **lifecycle))
    if runtime_error:
        execution.update(state='unavailable', label='策略状态暂不可用', reason='本次WT运行状态读取失败，请重新读取。')
    budget = _missing('当前没有可读取的WT策略预算；账户可用资金归账户所有。')
    if strategy and strategy.get('capital_baseline'):
        budget = dict(value=strategy['capital_baseline']['total_cny'], reason=None)
    elif report and (report.get('outcome') or {}).get('state'):
        # project_strategy已通过原NSQ构造器核验同一state；预算仅复制原policy值。
        try:
            amount = Decimal(report['outcome']['state']['policy']['initial_capital_cny'])
            if amount.is_finite() and 0 <= amount <= 9007199254740991:
                budget = dict(value=str(amount), reason=None)
        except (InvalidOperation, TypeError, KeyError):
            pass
    return dict(schema_version='guanheng.strategy-details.v1', read_only=True,
        observed_at=datetime.now(timezone.utc).isoformat(), strategy=strategy_definition(strategy['strategy_id'],strategy['strategy_version'])if strategy else strategy_definition('resonance-regime-v1',None),
        # 本轮已解析的公开运行身份摘要；未配置为null，只用于隔离跨代展示缓存。
        runtime_scope_id=hashlib.sha256(repr((str(configuration.path), configuration.control_id,
            configuration.instance_id, configuration.configuration_sha256)).encode('utf8')).hexdigest()
            if isinstance(configuration, RuntimeObservationConfig) else None,
        assignment=dict(scope='current-account-inventory', label='现有持仓归属此策略',
            reason='按用户确认展示当前账户持仓；历史开仓和成交记录不迁移。'),
        execution=execution, account=account, account_reason=account_reason,
        calculation=strategy, calculation_reason=strategy_reason, budget_cny=budget,
        capital_baseline=None if strategy is None else strategy.get('capital_baseline'),
        capital=None if strategy is None else strategy.get('capital'),
        returns=dict(cumulative_pct=_missing('缺少本次策略起始本金、期间现金流及连续净值基准，累计收益率暂不可计算。')))


def load_instances(settings):
    """显式安装目录清单；最多8个身份，不扫描或加载WT私有运行配置。"""
    primary = RuntimeObservationConfig.from_settings(settings)
    rows = [('账户WT', primary)]
    filename = os.environ.get('GUANHENG_WT_INSTANCE_CATALOG', '')
    if not filename:
        return rows
    path = Path(filename)
    if not path.is_absolute():
        raise ValueError('invalid WT instance catalog')
    value = read_status_snapshot(path, 65536).value
    if type(value) is not dict or set(value) != {'schema', 'instances'} or value['schema'] != 'guanheng.wt-instance-catalog.v1':
        raise ValueError('invalid WT instance catalog')
    items = value['instances']
    if type(items) is not list or len(items) > 7:
        raise ValueError('invalid WT instance count')
    seen = {primary.instance_id} if isinstance(primary, RuntimeObservationConfig) else set()
    fields = {'wt_status_file', 'wt_control_id', 'wt_instance_id', 'wt_configuration_sha256'}
    for item in items:
        if type(item) is not dict or set(item) != fields | {'label'}:
            raise ValueError('invalid WT instance item')
        label = item['label']
        if type(label) is not str or not 1 <= len(label) <= 64 or any(ord(c) < 32 for c in label):
            raise ValueError('invalid WT instance label')
        config = RuntimeObservationConfig.from_settings(SimpleNamespace(**{key: item[key] for key in fields}))
        if config is None or config.instance_id in seen:
            raise ValueError('duplicate WT instance')
        seen.add(config.instance_id)
        rows.append((label, config))
    return rows


def observe_instances(rows, deadline):
    result = []
    for label, config in rows:
        # 动态行的展示身份由稳定公开指针位置确定；账户金融scope仍由实际本代身份生成。
        identity = str(config.path) if isinstance(config, RuntimeCurrentFile) else config.instance_id if config else 'unconfigured'
        scope = hashlib.sha256(identity.encode('utf8')).hexdigest()
        try:
            value = observe_runtime(config, deadline)
        except (ValueError, OSError, TimeoutError):
            value = dict(state='unavailable', reason='此WT实例读取失败，请核对其状态文件和运行身份。', published_at=None, runtime=None)
        result.append(dict(scope_id=scope, label=label, **value))
    return dict(schema_version='guanheng.wt-instances.v1', read_only=True,
        observed_at=datetime.now(timezone.utc).isoformat(), instances=result)


def router(settings, configuration, invalid):
    """兼容新增GET共用App有界读池和原2秒总截止，不构造WT运行owner。"""
    import asyncio
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import JSONResponse

    routes = APIRouter()
    try:
        instances, catalog_error = load_instances(settings), False
    except (ValueError, OSError, TypeError):
        instances, catalog_error = [('账户WT', configuration)], True

    @routes.get('/v1/ui/strategy-details')
    @routes.get('/v1/ui/wt-instances')
    async def read(request: Request):
        if request.query_params or request.headers.get('content-length', '0') != '0' or request.headers.get('transfer-encoding'):
            raise HTTPException(422, '详情读取不接受额外参数')
        multi = request.url.path.endswith('wt-instances')
        if invalid:
            raise HTTPException(503, 'WT详情读取配置无效，请由维护人员核对实例目录。')
        deadline, future = monotonic() + 2, None
        try:
            operation = (lambda: observe_instances(instances, deadline)) if multi else (lambda: observe_details(settings, configuration, deadline))
            future = request.app.state.reader.submit(lambda _remaining: operation(), deadline)
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            result = await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline - monotonic()))
            if multi and catalog_error:
                result['catalog_reason'] = '补充WT实例目录读取配置无效，当前保留主账户实例；请核对实例目录。'
            return JSONResponse(result, headers={'Cache-Control': 'no-store'})
        except (ValueError, OSError, TimeoutError, ReadCapacityError, KeyError, TypeError):
            raise HTTPException(503, 'WT详情本次读取超时或失败，请重新读取。') from None
        finally:
            if future is not None:
                future.cancel()
    @routes.api_route('/v1/ui/strategy-details', methods=['POST','PUT','PATCH','DELETE','HEAD','OPTIONS','TRACE','CONNECT'])
    @routes.api_route('/v1/ui/wt-instances', methods=['POST','PUT','PATCH','DELETE','HEAD','OPTIONS','TRACE','CONNECT'])
    async def read_only():
        return JSONResponse({'detail':'详情仅提供只读查询'}, status_code=405,
            headers={'Allow':'GET','Cache-Control':'no-store'})
    return routes
