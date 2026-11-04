"""WT统一日线数据持续更新入口；父WT Job拥有SDK/DLL阻塞时的最终物理回收。"""
from pathlib import Path
import sys

_RELEASE_ROOT = Path(__file__).resolve().parents[2]
if str(_RELEASE_ROOT) not in sys.path:
    sys.path.insert(0, str(_RELEASE_ROOT))

import argparse
from datetime import datetime, timedelta, timezone
import math
import os
import time
from uuid import UUID,uuid4

from integrations.guanheng.daily_data_update import run_update, _save, _load
from integrations.guanheng.daily_data_inputs import prepare_update
from integrations.guanheng.market_generation import GenerationPublisher, read_fixed
from integrations.guanheng_market_client import strict_json

ZONE = timezone(timedelta(hours=8))


def target_date(calendar, now):
    """每日窗口固定处理本地昨日及此前最近交易日；显式--as-of另行选择日期。"""
    from guanheng_app.observation.calendars import official_calendar
    rows, _ = official_calendar(calendar)
    local = now.astimezone(ZONE)
    cutoff = local.date() - timedelta(days=1)
    if not calendar['coverage_start'] <= cutoff.isoformat() <= calendar['coverage_end']:
        raise ValueError('daily service outside calendar coverage')
    days = [row['date'] for row in rows if row['is_open'] == 1 and row['date'] <= cutoff.isoformat()]
    if not days:
        raise ValueError('daily service closed day unavailable')
    return max(days)


def validate_configuration(value):
    """有限预算及固定时区先准入；各原源配置沿所属工厂再次完整校验。"""
    required = {'schema', 'directory', 'raw_store', 'template', 'inputs', 'schedule', 'cycle_seconds', 'retry_seconds'}
    if (type(value) is not dict or not required<=set(value)or set(value)-required-{'price_scope'}
            or value['schema'] != 'guanheng.daily-data-service.v1'):
        raise ValueError('daily service configuration invalid')
    for key in ('directory', 'raw_store'):
        if type(value[key]) is not str or not Path(value[key]).is_absolute():
            raise ValueError('daily service directory invalid')
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
    if (type(inputs) is not dict or not fields <= set(inputs) or set(inputs) - fields - {'cache_seed','price_cache_seed','previous_requests'}
            or set(inputs['connections']) != {'batch', 'hpr'}
            or type(inputs['max_rows']) is not int or not 40 <= inputs['max_rows'] <= 2000
            or inputs['source_kind'] not in ('actual-qmt', 'sdk-synthetic')):
        raise ValueError('daily service inputs invalid')
    previous=inputs.get('previous_requests',[])
    if (type(previous)is not list or len(previous)>366 or len(set(previous))!=len(previous)
            or any(type(path)is not str or not Path(path).is_absolute()for path in previous)):
        raise ValueError('daily service prior request references invalid')
    datetime.strptime(inputs['cache_from'], '%Y%m%d')
    public = inputs['public_facts']
    if (type(public) is not dict or set(public) != {'source', 'allowed_hosts', 'seconds', 'max_requests',
            'max_bytes', 'response_bytes', 'timeout_seconds'} or type(public['allowed_hosts']) is not list):
        raise ValueError('daily service public facts invalid')
    for key, lower, upper in (('seconds', 30, 600), ('max_requests', 1, 512), ('max_bytes', 1, 1073741824),
                              ('response_bytes', 1, 16777216), ('timeout_seconds', 1, 30)):
        number = public[key]
        if type(number) not in (int, float) or not math.isfinite(number) or not lower <= number <= upper:
            raise ValueError('daily service source budget invalid')
    if not isinstance(value['template'], dict) or value['template'].get('schema') != 'guanheng.daily-data-update.v1':
        raise ValueError('daily service update template invalid')
    scope=value.get('price_scope')
    if scope is not None:
        if (type(scope)is not dict or set(scope)!={'baseline_reference','reference_connection','scope','authorized_from','maximum_history_rows'}
                or type(scope['maximum_history_rows'])is not int or not 2000<=scope['maximum_history_rows']<=1000000):
            raise ValueError('daily service price scope invalid')
        datetime.strptime(scope['authorized_from'],'%Y%m%d')
    return value


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
        with GenerationPublisher(config['template']['publication_directory']) as publisher:
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
            while not stopped():
                now = datetime.now(timezone.utc) if clock is None else clock()
                calendar = _load(config['template']['calendar'])
                day = as_of if as_of is not None else target_date(calendar, now)
                scheduled = once or (now.astimezone(ZONE).hour, now.astimezone(ZONE).minute) >= (9, 0)
                entry = index.get(day, {})
                continuation=entry.get('continuation_required',False)
                if type(continuation)is not bool:raise ValueError('daily service continuation flag invalid')
                if scheduled and (entry.get('state') != 'published'or continuation) and time.monotonic() >= retry_at:
                    if day not in index and len(index) >= 366:
                        raise ValueError('daily service retained task capacity')
                    if entry.get('state')=='published'and continuation:
                        revision=entry.get('revision',0)+1
                        if revision>366:raise ValueError('daily service continuation capacity')
                        history=[*entry.get('history_requests',[]),entry['request']]
                        entry=dict(
                            request=str(root/day/'continuations'/str(uuid4())/'REQUEST.json'),  # 新修订写独立根，旧成功任务保持。
                            state='preparing',  # 先登记路径；崩溃后沿同路径和原输入槽恢复。
                            history_requests=history,  # 原同日修订引用，未丢弃旧请求或原HPR责任。
                            revision=revision)  # 本市场日零基后继修订号，上限366。
                    request_file=Path(entry.get('request')or root/day/'REQUEST.json')
                    work=request_file.parent
                    if not work.resolve().is_relative_to((root/day).resolve()):
                        raise ValueError('daily service task path outside day root')
                    work.mkdir(parents=True,exist_ok=True)
                    entry.update(request=str(request_file),state='preparing')
                    index[day]=entry;_save(index_path,index)
                    deadline = time.monotonic() + config['cycle_seconds']
                    status.update(state='updating', active_date=day)
                    _save(directory / 'status.json', status)
                    try:
                        if not request_file.exists():
                            previous=list(config['inputs'].get('previous_requests',[]))
                            for _,row in sorted(index.items()):
                                previous.extend(row.get('history_requests',[]))
                                if row.get('request')is not None and Path(row['request'])!=request_file:
                                    previous.append(row['request'])
                            previous=list(dict.fromkeys(previous))
                            prepared = prepare_update(config, day, work / 'inputs', deadline=deadline,
                                cancelled=stopped, previous_requests=previous)
                            request = _load(prepared)
                            _save(request_file, request)
                        index[day].update(state='updating')  # 保留原修订链，未声称原生或发布完成。
                        _save(index_path, index)
                        result = run_update(strict_json(read_fixed(request_file, maximum=16777216)), work / 'work',
                            deadline=deadline, cancelled=stopped, publisher=publisher)
                        index[day].update(
                            state='published',  # 已确认指针成功采用，而非仅接收任务。
                            current_sha256=result['current_sha256'],  # 本日实际采用的指针身份；后继版本独立保存。
                            continuation_required=result.get('continuation_required',False))  # 价格原责任仍待核且目标缺失时，同日接续。
                        if index[day]['continuation_required']:retry_at=time.monotonic()+config['retry_seconds']
                        status.update(state='waiting', active_date=None, last_success=day)
                    except InterruptedError:
                        status.update(state='stopping')
                    except Exception as failure:
                        status.update(state='update_failed', error_type=type(failure).__name__)
                        index[day].update(
                            state='failed',  # 当前轮次失败，原CURRENT与已成功阶段保留。
                            error_type=type(failure).__name__)  # 固定异常类型，不持久化来源原文或秘密。
                        retry_at = time.monotonic() + config['retry_seconds']
                    _save(index_path, index)
                    _save(directory / 'status.json', status)
                    if once:
                        if status['state'] == 'update_failed':
                            raise RuntimeError('daily service one cycle failed')
                        break
                elif once:
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
