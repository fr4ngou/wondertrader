"""WT统一日线数据持续更新入口；父WT Job拥有SDK/DLL阻塞时的最终物理回收。"""
from pathlib import Path
import sys

_RELEASE_ROOT = Path(__file__).resolve().parents[2]
if str(_RELEASE_ROOT) not in sys.path:
    sys.path.insert(0, str(_RELEASE_ROOT))

import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import math
import os
import re
import time
from uuid import UUID,uuid4

from integrations.guanheng.daily_data_update import run_update, _save, _load
from integrations.guanheng.daily_data_inputs import prepare_update
from integrations.guanheng.daily_input_recovery import observe_input_reads, close_input_discovery, registered_requests
from integrations.guanheng.market_generation import GenerationPublisher, read_fixed
from integrations.guanheng_market_client import strict_json

ZONE = timezone(timedelta(hours=8))


def target_date(calendar, now):
    """按原输入闭合窗口和官方日历选最近交易日；显式as-of独立准入。"""
    from guanheng_app.observation.calendars import closed_day_cutoff, official_calendar
    cutoff = closed_day_cutoff(now)
    rows, _ = official_calendar(calendar)
    if not calendar['coverage_start'] <= cutoff <= calendar['coverage_end']:
        raise ValueError('daily service outside calendar coverage')
    days = [row['date'] for row in rows if row['is_open'] == 1 and row['date'] <= cutoff]
    if not days:
        raise ValueError('daily service closed day unavailable')
    return max(days)


def validate_configuration(value):
    """有限预算及固定时区先准入；各原源配置沿所属工厂再次完整校验。"""
    required = {'schema', 'directory', 'raw_store', 'template', 'inputs', 'schedule', 'cycle_seconds', 'retry_seconds'}
    if (type(value) is not dict or not required<=set(value)or set(value)-required-{'price_scope','observation_repair_root'}
            or value['schema'] != 'guanheng.daily-data-service.v1'):
        raise ValueError('daily service configuration invalid')
    for key in ('directory', 'raw_store'):
        if type(value[key]) is not str or not Path(value[key]).is_absolute():
            raise ValueError('daily service directory invalid')
    if 'observation_repair_root' in value:
        root = value['observation_repair_root']
        if type(root) is not str or not Path(root).is_absolute() or root.startswith(('\\\\','//')):
            raise ValueError('daily service observation repair root invalid')
    schedule = value['schedule']
    if (type(schedule) is not dict or set(schedule) != {'timezone', 'at', 'poll_seconds'}
            or schedule['timezone'] != 'Asia/Shanghai' or schedule['at'] != '09:00'
            or type(schedule['poll_seconds']) not in (int, float) or not 0.1 <= schedule['poll_seconds'] <= 30):
        raise ValueError('daily service schedule invalid')
    for key, lower, upper in (('cycle_seconds', 60, 86400), ('retry_seconds', 1, 3600)):
        number = value[key]
        if type(number) not in (int, float) or not math.isfinite(number) or not lower <= number <= upper:
            raise ValueError('daily service budget invalid')
    inputs = value['inputs']
    fields = {'connections', 'public_facts', 'cache_from', 'max_rows', 'source_kind'}
    if (type(inputs) is not dict or not fields <= set(inputs) or set(inputs) - fields - {'cache_seed','price_cache_seed','previous_requests','previous_inputs','supplement_facts','stock_cross_section'}
            or set(inputs['connections']) != {'batch', 'hpr'}
            or type(inputs['max_rows']) is not int or not 40 <= inputs['max_rows'] <= 2000
            or inputs['source_kind'] not in ('actual-qmt', 'sdk-synthetic')):
        raise ValueError('daily service inputs invalid')
    if 'supplement_facts' in inputs:
        from integrations.guanheng.market_supplement_capture import validate_plan
        validate_plan(inputs['supplement_facts'])
    if 'stock_cross_section' in inputs:
        from integrations.guanheng.stock_cross_section import validate_policy
        validate_policy(inputs['stock_cross_section'])
    previous=inputs.get('previous_requests',[])
    if (type(previous)is not list or len(previous)>366 or len(set(previous))!=len(previous)
            or any(type(path)is not str or not Path(path).is_absolute()for path in previous)):
        raise ValueError('daily service prior request references invalid')
    previous_inputs=inputs.get('previous_inputs',[])
    if (type(previous_inputs)is not list or len(previous_inputs)>366
            or any(type(item)is not dict or set(item)!={'path','sha256'}
                   or type(item['path'])is not str or not Path(item['path']).is_absolute()
                   or type(item['sha256'])is not str or re.fullmatch(r'[0-9a-f]{64}',item['sha256'])is None
                   for item in previous_inputs)
            or len({item['path']for item in previous_inputs})!=len(previous_inputs)):
        raise ValueError('daily service prior input references invalid')
    datetime.strptime(inputs['cache_from'], '%Y%m%d')
    public = inputs['public_facts']
    public_fields = {'source', 'allowed_hosts', 'seconds', 'max_requests', 'max_bytes', 'response_bytes', 'timeout_seconds'}
    if (type(public) is not dict or not public_fields <= set(public)
            or set(public) - public_fields - {'baostock_daily_timeout_seconds'}
            or type(public['allowed_hosts']) is not list):
        raise ValueError('daily service public facts invalid')
    for key, lower, upper in (('seconds', 30, 600), ('max_requests', 1, 512), ('max_bytes', 1, 1073741824),
                              ('response_bytes', 1, 16777216), ('timeout_seconds', 1, 30)):
        number = public[key]
        if type(number) not in (int, float) or not math.isfinite(number) or not lower <= number <= upper:
            raise ValueError('daily service source budget invalid')
    if 'baostock_daily_timeout_seconds' in public:
        timeout = public['baostock_daily_timeout_seconds']
        if type(timeout) not in (int, float) or not 0 < timeout <= 60:
            raise ValueError('daily service BaoStock daily request budget invalid')
    if not isinstance(value['template'], dict) or value['template'].get('schema') != 'guanheng.daily-data-update.v1':
        raise ValueError('daily service update template invalid')
    scope=value.get('price_scope')
    if scope is not None:
        if (type(scope)is not dict or not {'baseline_reference','reference_connection','scope','authorized_from','maximum_history_rows'}<=set(scope)
                or set(scope)-{'baseline_reference','reference_connection','scope','authorized_from','maximum_history_rows','index_fallback','strategy_history','unit_evidence'}
                or scope.get('index_fallback')not in(None,'official-publishers')
                or type(scope['maximum_history_rows'])is not int or not 2000<=scope['maximum_history_rows']<=1000000):
            raise ValueError('daily service price scope invalid')
        datetime.strptime(scope['authorized_from'],'%Y%m%d')
        if scope.get('unit_evidence')is not None:
            from .daily_data_inputs import validate_unit_evidence_descriptor
            validate_unit_evidence_descriptor(scope['unit_evidence'])
        if scope.get('strategy_history')is not None:
            from .daily_strategy_history import validate_strategy_history
            validate_strategy_history(scope['strategy_history'])
    return value


def pending_observation_repair(repository, index, day, now):
    """只接当前活动任务和日更覆盖范围。从 INDEX 重发同一发布回执。"""
    from guanheng_app.observation.contracts import ObservationError
    try:
        job = repository.data_repair()
        if not job or job.get('state') != 'running' or not job.get('wt_request'):
            return None
        job_id = job['id']
        if str(UUID(job_id)) != job_id:
            return None
        if job.get('wt_receipt', {}).get('state') in ('published', 'failed'):
            return None
        requested = job['wt_request']
        age = (now - datetime.fromisoformat(requested['requested_at'])).total_seconds()
        if not 0 <= age < 86400:
            return None
        for target, entry in index.items():
            repair = entry.get('observation_repair', {})
            if repair.get('id') == job_id and repair.get('state') in ('published', 'failed'):
                repository.record_wt_repair_receipt(job_id, repair['state'], observation_date=target,
                                                    current_sha256=repair.get('current_sha256'))
                return None
            if repair.get('id') == job_id and repair.get('state') == 'running':
                return job_id, target
        if (type(requested.get('dates')) is not list or not 1 <= len(requested['dates']) <= 35
                or any(type(value) is not str or datetime.fromisoformat(value).date().isoformat() != value
                       or value > day for value in requested['dates'])):
            return None
        return job_id, day
    except ObservationError as error:
        if error.code not in ('catalog_unavailable', 'write_outcome_unknown'):
            raise
        return None
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def report_observation_repair(repository, repair, day):
    """观察目录暂不可写时由下次轮询沿 INDEX 原回执继续。"""
    from guanheng_app.observation.contracts import ObservationError
    try:
        repository.record_wt_repair_receipt(repair['id'], repair['state'], observation_date=day,
                                            current_sha256=repair.get('current_sha256'))
    except ObservationError as error:
        if error.code not in ('catalog_unavailable', 'write_outcome_unknown'):
            raise


def serve(configuration, directory, control_id, *, once=False, as_of=None, clock=None):
    """本进程唯一线程拥有输入、更新和所有Reader；stop.json只请求本控制代关闭。

    外层Job负责启动/树退出/管道回收；closed.json仅表示本入口已退出owner上下文。
    数据根INDEX及阶段任务跨代保留，重新启动沿原REQUEST/slot/当前版本恢复。
    """
    if str(UUID(control_id)) != control_id:
        raise ValueError('daily service control id invalid')
    directory = Path(directory).absolute()
    if directory.name != control_id:
        raise ValueError('daily service control directory differs')
    config = validate_configuration(_load(configuration))
    observation_repository = None
    if config.get('observation_repair_root'):
        from guanheng_app.observation.storage import SnapshotRepository
        observation_repository = SnapshotRepository(config['observation_repair_root'])
    # 本代单请求传输截止只控制重试耗时，原数据源、输入槽与输出身份沿既有配置固定。
    daily_timeout = config['inputs']['public_facts'].pop('baostock_daily_timeout_seconds', None)
    public_request_options = {} if daily_timeout is None else {'baostock_daily_timeout_seconds': daily_timeout}
    root = Path(config['directory'])
    directory.mkdir(parents=False, exist_ok=False)
    close_deadline = None

    def stopped():
        nonlocal close_deadline
        path = directory / 'stop.json'
        if not path.exists():
            return False
        stop = strict_json(read_fixed(path, maximum=4096))
        if (type(stop) is not dict or set(stop) != {'schema', 'control_id', 'deadline'}
                or stop['schema'] != 'guanheng.daily-data-stop.v1' or stop['control_id'] != control_id
                or type(stop['deadline']) not in (int, float) or not math.isfinite(stop['deadline'])):
            raise ValueError('daily service stop identity invalid')
        close_deadline = stop['deadline']
        return True

    error = None
    try:
        with GenerationPublisher(config['template']['publication_directory']) as publisher, ExitStack() as input_resources:
            root.mkdir(parents=False, exist_ok=True)
            original = root / 'CONFIGURATION.json'
            if original.exists():
                if strict_json(read_fixed(original, maximum=16777216)) != config:
                    raise ValueError('daily service configuration changed')
            else:
                _save(original, config)
            index_path = root / 'INDEX.json'
            index = strict_json(read_fixed(index_path, maximum=1048576)) if index_path.exists() else {}
            successful = [day for day, row in index.items() if row.get('state') == 'published']
            status = dict(
                schema='guanheng.daily-data-status.v1',  # 持续数据入口的状态合同。
                control_id=control_id,  # 本轮控制UUID，旧stop保持独立。
                pid=os.getpid(),  # 实际owner进程PID，区别launcher与旧进程。
                configuration_sha256=configuration['sha256'],  # 本代固定配置原字节身份。
                state='waiting',  # waiting/updating/update_failed/stopping入口阶段。
                active_date=None,  # 正在处理的市场日期YYYY-MM-DD；空表示当前无轮次。
                last_success=max(successful) if successful else None)  # 持久INDEX确认的最近成功市场日，首次为空。
            _save(directory / 'ready.json', status)
            retry_at = 0
            next_input_observation = 0
            input_recovery_failed = False
            read_state = dict(consumed=set(),  # 本进程已准入的已消费原槽；重启沿原件重新核。
                              pending=set(),  # 原读取仍未知/未确认消费的槽，保持原INDEX归属。
                              checked={},  # 轮询顺序，避免旧未知槽长期阻挡其他已返回结果。
                              slots={},  # 原槽到原连接的发现缓存，最多100000项。
                              roots=set(),  # 跨日后完整扫描过的封存根，当前日后续回读仍可发现。
                              discovery={},  # 未完成目录迭代及其开始观察的目标日，退出租约前关闭。
                              discovered=set())  # 已完整发现过的根；用于区分待发现与已确认无新槽。
            input_resources.callback(close_input_discovery, read_state)
            while not stopped():
                now = datetime.now(timezone.utc) if clock is None else clock()
                calendar = _load(config['template']['calendar'])
                day = as_of if as_of is not None else target_date(calendar, now)
                observation_id = None
                if observation_repository is not None:
                    pending = pending_observation_repair(observation_repository, index, day, now)
                    if pending:
                        observation_id, requested_day = pending
                        # 先续接已绑定日期。当前版本若已越过，禁止旧日任务使 CURRENT 倒退。
                        current = read_generation(publisher.current_file)[0] if requested_day < day and publisher.current_file.exists() else None
                        if current and current['observation_date'] > requested_day:
                            previous = index[requested_day]
                            receipt = previous['observation_repair']
                            journal = Path(previous['request']).parent / 'work' / 'STATE.json'
                            saved = strict_json(read_fixed(journal, maximum=16777216)) if journal.exists() else {}
                            if saved.get('status') == 'published' and type(saved.get('current_sha256')) is str:
                                receipt.update(state='published', current_sha256=saved['current_sha256'])
                            else:
                                receipt['state'] = 'failed'
                            _save(index_path, index)
                            report_observation_repair(observation_repository, receipt, requested_day)
                            observation_id = None
                        else:
                            day = requested_day
                observed_inputs = False
                try:
                    registered = registered_requests(index)  # 创建输入和已有REQUEST恢复共用同一原件损坏准入。
                    if time.monotonic() >= next_input_observation:
                        # INDEX只保存派生接续标志；升级后的旧false从不可变结果重建，复用原重试节拍。
                        entry=index.get(day,{})
                        if entry.get('price_result')is not None:
                            from integrations.guanheng.daily_price_continuation import requires_price_continuation
                            if stopped():raise InterruptedError('daily reference continuation stopped')
                            required=requires_price_continuation(_load(entry['price_result']))
                            if stopped():raise InterruptedError('daily reference continuation stopped')
                            if entry.get('price_continuation_required')!=required:
                                entry['price_continuation_required']=required
                                _save(index_path,index)
                        status['input_reads'] = observe_input_reads(index, read_state, target_day=day,
                            deadline=time.monotonic()+5, cancelled=stopped,
                            prior_requests=config['inputs'].get('previous_requests',()),
                            prior_inputs=config['inputs'].get('previous_inputs',()))  # 只核既有v8/v9身份，不补发旧页或旧批次。
                        input_recovery_failed = False
                        if 'input_recovery_error_type' in status:
                            status['state'] = 'waiting'
                        status.pop('input_recovery_error_type', None)
                        next_input_observation = time.monotonic()+config['retry_seconds']
                        observed_inputs = True
                except InterruptedError:
                    break
                except Exception as failure:
                    input_recovery_failed = True
                    status['state'] = 'update_failed'
                    status['input_recovery_error_type'] = type(failure).__name__  # 原件损坏等明确阻断，未吞成成功。
                    observed_inputs = True
                if observed_inputs:
                    _save(directory/'status.json', status)
                entry = index.get(day, {})
                # 09:00约束新日期首次建任务；已登记任务跨零点或重启后沿原身份立即续接。
                scheduled = once or bool(entry) or observation_id or (now.astimezone(ZONE).hour, now.astimezone(ZONE).minute) >= (9, 0)
                continuation=entry.get('continuation_required',False)
                price_continuation=entry.get('price_continuation_required',False)
                local_now=now.astimezone(ZONE)
                supplement_refresh=('supplement_facts' in config['inputs']
                    and entry.get('state')=='published' and entry.get('supplement_complete') is False
                    and (local_now.hour,local_now.minute)>=(9,0)
                    and entry.get('supplement_attempt_date')!=local_now.date().isoformat())
                section_refresh=('stock_cross_section' in config['inputs']
                    and entry.get('state')=='published' and entry.get('stock_cross_section_complete') is not True
                    and (local_now.hour,local_now.minute)>=(9,0)
                    and entry.get('stock_cross_section_attempt_date')!=local_now.date().isoformat())
                if type(continuation)is not bool or type(price_continuation)is not bool:
                    raise ValueError('daily service continuation flag invalid')
                continuation=continuation or price_continuation or supplement_refresh or section_refresh or observation_id
                if scheduled and not input_recovery_failed and (entry.get('state') != 'published'or continuation) and time.monotonic() >= retry_at:
                    if day not in index and len(index) >= 366:
                        raise ValueError('daily service retained task capacity')
                    if entry.get('state')=='published'and continuation:
                        revision=entry.get('revision',0)+1
                        if revision>366:raise ValueError('daily service continuation capacity')
                        history=[*entry.get('history_requests',[]),entry['request']]
                        entry=dict(
                            **{key:value for key,value in entry.items()if key.startswith('price_') or key=='observation_repair'},
                            request=str(root/day/('r%03d' % revision)/'REQUEST.json'),  # 单owner按日递增修订根；缩短Windows路径，原槽/内容摘要保持。
                            state='preparing',  # 先登记路径；崩溃后沿同路径和原输入槽恢复。
                            history_requests=history,  # 原同日修订引用，未丢弃旧请求或原HPR责任。
                            revision=revision)  # 本市场日零基后继修订号，上限366。
                    request_file=Path(entry.get('request')or root/day/'REQUEST.json')
                    work=request_file.parent
                    if not work.resolve().is_relative_to((root/day).resolve()):
                        raise ValueError('daily service task path outside day root')
                    work.mkdir(parents=True,exist_ok=True)
                    entry.update(request=str(request_file),state='preparing')
                    if 'supplement_facts' in config['inputs']:
                        # 09:00前只续原任务，不提前消耗本自然日一次partial刷新资格。
                        entry['supplement_attempt_date']=(local_now.date() if (local_now.hour,local_now.minute)>=(9,0)
                            else local_now.date()-timedelta(days=1)).isoformat()  # 原INDEX持久来源刷新自然日，上海时区。
                    if 'stock_cross_section' in config['inputs']:
                        entry['stock_cross_section_attempt_date'] = local_now.date().isoformat()
                    if observation_id:
                        entry['observation_repair'] = dict(
                            id=observation_id,  # 观衡本轮补齐任务身份。
                            state='running',  # 本轮日更已持久登记，尚未发布。
                        )
                    index[day]=entry;_save(index_path,index)
                    if observation_id:
                        report_observation_repair(observation_repository, entry['observation_repair'], day)
                    deadline = time.monotonic() + config['cycle_seconds']
                    status.update(state='updating', active_date=day)
                    _save(directory / 'status.json', status)
                    try:
                        transaction=work/'work'/'STATE.json'
                        parent_fixed=(transaction.exists()and'parent'in strict_json(
                            read_fixed(transaction,maximum=16777216))['stages'])  # 已提交完整事务拥有原父CURRENT，先沿原责任完成CAS。
                        if config.get('price_scope')is not None and publisher.current_file.exists()and not parent_fixed:
                            # 价格与公共辅助事实共用owner/租约，先更新所有已知证券价格；旧事实时间保持原值。
                            from integrations.guanheng.daily_price_refresh import price_refresh
                            price_entry=index[day]
                            # 完整REQUEST已固定父CURRENT时先完成该事务；后继完整修订再推进独立价格，保持单一CAS链。
                            if (not request_file.exists()and price_entry.get('price_state')=='published'
                                    and price_entry.get('price_continuation_required',False)):
                                price_entry['price_history_requests']=[*price_entry.get('price_history_requests',[]),price_entry['price_request']]
                                price_entry['price_revision']=price_entry.get('price_revision',0)+1
                                price_entry.pop('price_request')
                            if 'price_request'not in price_entry:
                                revision=price_entry.get('price_revision',0)
                                price_entry['price_request']=str(root/day/'price-first'/('r%03d'%revision)/'REQUEST.json')
                            price_entry['price_state']='preparing';_save(index_path,index)
                            prior_prices=[p for d,row in index.items()for p in
                                [*row.get('price_history_requests',[]),*([row['price_request']]if row.get('price_request')else[])]
                                if p!=price_entry['price_request']and Path(p).is_file()]
                            price_result=price_refresh(config,day,Path(price_entry['price_request']).parent,
                                publisher=publisher,deadline=deadline,cancelled=stopped,
                                previous_requests=[*registered,*prior_prices])
                            price_entry.update(price_state='published',price_current_sha256=price_result['current_sha256'],
                                price_result=price_result['price_result'],price_continuation_required=price_result['continuation_required'])
                            status.update(last_price_success=day,price_state='published',
                                          auxiliary_observation_date=price_result['auxiliary_observation_date'])
                            _save(index_path,index);_save(directory/'status.json',status)
                        if not request_file.exists():
                            previous=list(config['inputs'].get('previous_requests',[]))
                            previous.extend(path for path in registered if Path(path)!=request_file)
                            previous=list(dict.fromkeys(previous))
                            prepared = prepare_update(config, day, work / 'inputs', deadline=deadline,
                                cancelled=stopped, previous_requests=previous,
                                prior_price_requests=[p for row in index.values()for p in
                                    [*row.get('price_history_requests',[]),*([row['price_request']]if row.get('price_request')else[])]
                                    if Path(p).is_file()], **public_request_options)
                            request = _load(prepared)
                            _save(request_file, request)
                        index[day].update(state='updating')  # 保留原修订链，未声称原生或发布完成。
                        _save(index_path, index)
                        request = strict_json(read_fixed(request_file, maximum=16777216))
                        section = None
                        if 'stock_cross_section' in config['inputs']:
                            from integrations.guanheng.day_facts import DayFactsStore
                            day_facts = DayFactsStore(request['daily_facts'])
                            try:
                                section = (day_facts.query(day, '0'*64) or {}).get('stock_cross_section', {})
                            finally:
                                day_facts.close()
                        result = run_update(request, work / 'work',
                            deadline=deadline, cancelled=stopped, publisher=publisher)
                        index[day].update(
                            state='published',  # 已确认指针成功采用，而非仅接收任务。
                            current_sha256=result['current_sha256'],  # 本日实际采用的指针身份；后继版本独立保存。
                            continuation_required=result.get('continuation_required',False)or index[day].get('price_continuation_required',False))  # 股票/独立价格原责任共同决定接续。
                        if 'supplement_facts' in config['inputs']:
                            index[day]['supplement_complete']=result['supplement_complete']  # partial成功仍允许次自然日再补，不在同日空转。
                        if section is not None:
                            index[day]['stock_cross_section_complete'] = 'provider' in section
                            status['stock_cross_section'] = section.get('provider', section.get('reason', 'not_archived'))
                        if observation_id:
                            entry['observation_repair'].update(state='published', current_sha256=result['current_sha256'])
                        if index[day]['continuation_required']:retry_at=time.monotonic()+config['retry_seconds']
                        status.update(state='waiting', active_date=None, last_success=day)
                    except InterruptedError:
                        status.update(state='stopping')
                    except Exception as failure:
                        status.update(state='update_failed', error_type=type(failure).__name__,error_code=getattr(failure,'code',None))
                        index[day].update(
                            state='failed',  # 当前轮次失败，原CURRENT与已成功阶段保留。
                            error_type=type(failure).__name__)  # 固定异常类型，不持久化来源原文或秘密。
                        retry_at = time.monotonic() + config['retry_seconds']
                    _save(index_path, index)
                    if observation_id:
                        report_observation_repair(observation_repository, entry['observation_repair'], day)
                    _save(directory / 'status.json', status)
                    if once:
                        if status['state'] == 'update_failed':
                            raise RuntimeError('daily service one cycle failed')
                        break
                elif once:
                    if input_recovery_failed:
                        raise RuntimeError('daily retained input recovery failed')
                    break
                # 来源/原生调用在本线程；轮询等待有界，原停止文件最多30秒内核查。
                time.sleep(config['schedule']['poll_seconds'])
    except BaseException as failure:
        error = type(failure).__name__
        raise
    finally:
        late = close_deadline is not None and time.monotonic() >= close_deadline
        _save(directory / ('closed.json' if error is None and not late else 'failure.json'), dict(
            schema='guanheng.daily-data-closed.v1',  # 进程入口关闭事实；物理Job关闭沿父收据。
            control_id=control_id,  # 本轮控制UUID，旧停止请求不能影响新代。
            pid=os.getpid(),  # 实际数据进程身份，不以launcher PID代替。
            owner_closed=True,  # 所有输入/更新上下文已退出，排他锁已释放。
            error_type=error,  # 固定异常类型，成功为None；无凭据或来源正文。
            close_deadline_exceeded=late))  # 是否超过调用者原关闭截止。


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--control-directory', required=True)
    parser.add_argument('--control-id', required=True)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--as-of')
    args = parser.parse_args()
    if args.as_of is not None:
        if not args.once or datetime.fromisoformat(args.as_of).date().isoformat() != args.as_of:
            parser.error('--as-of requires --once and YYYY-MM-DD')
    serve(dict(path=str(Path(args.config).absolute()), sha256=args.config_sha256),
          args.control_directory, args.control_id, once=args.once, as_of=args.as_of)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(2)
