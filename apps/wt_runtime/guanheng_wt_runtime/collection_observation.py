"""采集状态的有限公开投影；本地文件读取唯一实现在独立SDK，实例身份由父owner提供。"""
from datetime import datetime, timezone
import math

from guanheng_market_client.runtime_status import (
    CollectionStatusPending, read_status_snapshot,
)
from .managed_local_process import _inspect

# 子服务协议允许最多60秒发布一次；额外5秒仅为采样/墙钟容差。
MAX_SNAPSHOT_AGE_SECONDS = 65.0
MAX_FUTURE_SECONDS = 5.0
COUNTERS = ('callbacks', 'received_ticks', 'accepted_ticks', 'rejected_ticks',
            'queue_depth', 'sent_ticks', 'latest_symbols', 'missing_symbols', 'overflows')
PHASES = frozenset(('new', 'starting', 'running', 'stop_requested', 'closing_receiver',
                    'closing_native', 'closed', 'failed'))
FAILURE_STAGES = frozenset(('configuration', 'writer_ownership', 'native_start',
                          'ready_publish', 'collection', 'status_publish', 'close_unconfirmed'))
ERRORS = {
    'receiver_configuration_failed': '行情接收配置失败', 'archive_configuration_failed': '归档配置失败',
    'native_initialization_failed': '原生采集初始化失败', 'archive_capability_required': '原生归档能力缺失',
    'native_counts_failed': '原生计数读取失败', 'start_cancelled': '采集启动已取消',
    'receiver_start_failed': '行情接收启动失败', 'consumer_failed': '行情消费失败',
    'native_push_failed': '行情提交到原生采集失败', 'native_writer_failed': '原生行情写入失败',
    'receiver_close_failed': '接收资源关闭失败', 'native_close_deadline': '原生关闭预算已耗尽',
    'native_close_failed': '原生采集关闭失败',
}
REASONS = {
    'unconfigured': '当前应用未配置行情采集进程',
    'waiting': '采集进程尚未提供本轮状态，请稍后重新读取',
    'pending': '状态文件正由采集进程发布，请重新读取',
    'unavailable': '本轮采集状态读取失败，请维护人员核对当前实例收据',
    'invalid': '采集状态格式或实例身份核验失败，本次隐藏其行情值',
    'stale': '本实例状态发布已超过65秒，本次隐藏其行情值；请核对采集进程',
    'future': '状态发布时间超前本机时钟超过5秒，请核对本机时钟',
    'deadline': '本次状态读取预算已耗尽，请重新读取',
    'identity_changed': '读取期间采集实例身份变化，请重新读取',
    'invalid_configuration': '采集部署配置未通过校验',
}


def empty_observation(code):
    """缺失值保留null；原始异常、私有路径、状态正文不进入公开模型。"""
    return dict(available=False, status=code, reason=REASONS.get(code, REASONS['unavailable']),
        source='QMT 全推 → 共享内存 → WT 原生 DataKit',
        latest_source_time_ms=None, received_at=None, published_at=None, status_file_updated_at=None,
        snapshot_age_seconds=None, active=None, connected=None, generation=None, phase=None,
        received_ticks=None, pushed_ticks=None, processed_ticks=None, native_subscribed=None,
        coverage=None, missing_symbols=None, queue_depth=None, overflows=None,
        receiver_heartbeats=None, error=None, failure=None)


def _need(value):
    if not value:
        raise ValueError('invalid collection observation')


def _count(value):
    _need(type(value) is int and 0 <= value <= 9007199254740991)
    return value


def _epoch(value, *, nullable=False):
    if nullable and value is None:
        return None
    _need(type(value) in (int, float) and 0 < value < 253402300800 and math.isfinite(value))
    return float(value)


def _iso(seconds):
    return None if seconds is None else datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def _identity(value, identity, schema):
    control_id, pid, digest = identity
    _need(value.get('schema') == schema and value.get('control_id') == control_id
          and type(value.get('pid')) is int and value['pid'] == pid
          and value.get('configuration_sha256') == digest)


def _failure(directory, identity, check):
    """同实例失败收据只公开有限诊断；诊断读取失败不遮蔽主快照。"""
    try:
        check()
        value = read_status_snapshot(directory/'failure.json', 4096).value
        check()
        _identity(value, identity, 'qmt.quote-collector-failure.v1')
        stage = value.get('stage')
        _need(type(stage) is str and stage in FAILURE_STAGES)
        kind = value.get('exception_kind')
        kind = kind if kind in ('PermissionError', 'FileNotFoundError', 'TimeoutError',
            'ValueError', 'RuntimeError', 'OSError', 'MemoryError', 'other') else None
        winerror = value.get('winerror')
        return dict(stage=stage, exception_kind=kind,
            winerror=winerror if type(winerror) is int and 0 <= winerror <= 65535 else None)
    except (OSError, ValueError, TimeoutError, TypeError):
        return None


def read_observation(directory, identity, deadline, *, clock, wall_clock):
    """一次至多64KiB状态与4KiB失败收据；调用者读池拥有OS等待及HTTP取消。

    截止在每次读取前后检查，不重试、不扫描其他目录；当前进程状态另由父owner核实。
    数据时效只检查发布墙钟，原始报价时钟留给来源模块解释。
    """
    def check():
        if clock() >= deadline:
            raise TimeoutError('collection observation deadline')
    result = empty_observation('unavailable')
    try:
        check()
        _inspect(directory, directory=True)
        snapshot = read_status_snapshot(directory/'status.json')
        check()
        value = snapshot.value
        _identity(value, identity, 'qmt.quote-collector-status.v1')
        published = _epoch(value.get('observed_wall_time'))
        now = wall_clock()
        age = now - published
        if age > MAX_SNAPSHOT_AGE_SECONDS:
            result = empty_observation('stale')
        elif age < -MAX_FUTURE_SECONDS:
            result = empty_observation('future')
        else:
            current = value.get('collection')
            _need(type(current) is dict)
            _need(type(current.get('connected')) is bool and current.get('phase') in PHASES)
            source = current.get('latest_source_time_ms')
            if source is not None:
                _need(type(source) is int and 0 < source <= 8640000000000000)
            received = _epoch(current.get('observed_wall_time'), nullable=True)
            native = current.get('native_counts')
            _need(type(native) is dict)
            counts = {name: _count(native.get(name)) for name in ('subscribed', 'delivered', 'writer_processed')}
            heartbeat = current.get('source_heartbeat')
            _need(heartbeat is None or type(heartbeat) is dict)
            heartbeat = None if heartbeat is None else {key: _count(heartbeat.get(key)) for key in COUNTERS}
            error = current.get('error')
            _need(error is None or type(error) is str)
            error = ERRORS.get(error, '采集模块报告未分类故障') if error else None
            receiver_failure = current.get('receiver_failure')
            _need(receiver_failure in (None, 'connection_ended', 'consumer_failed', 'receiver_failed'))
            cleanup = current.get('receiver_cleanup_failure')
            _need(cleanup in (None, 'transport_close_unconfirmed'))
            if cleanup:
                error = error or '行情运输关闭尚未确认'
            if receiver_failure in ('consumer_failed', 'receiver_failed'):
                error = error or '行情接收或消费失败'
            connected = current['connected']
            result.update(available=True, status='current', reason='',
                latest_source_time_ms=source, received_at=_iso(received), published_at=_iso(published),
                status_file_updated_at=_iso(snapshot.modified_epoch_ns / 1000000000),
                snapshot_age_seconds=round(max(0., age), 3), connected=connected,
                generation=_count(current.get('generation')), phase=current['phase'],
                received_ticks=_count(current.get('received_ticks')), pushed_ticks=_count(current.get('pushed_ticks')),
                processed_ticks=counts['writer_processed'], native_subscribed=counts['subscribed'],
                coverage=None if heartbeat is None else heartbeat['latest_symbols'],
                missing_symbols=None if heartbeat is None else heartbeat['missing_symbols'],
                queue_depth=None if heartbeat is None else heartbeat['queue_depth'],
                overflows=None if heartbeat is None else heartbeat['overflows'],
                receiver_heartbeats=_count(current.get('receiver_heartbeats')), error=error)
    except FileNotFoundError:
        result = empty_observation('waiting')
    except CollectionStatusPending:
        result = empty_observation('pending')
    except TimeoutError:
        result = empty_observation('deadline')
    except (OSError, ValueError, TypeError, OverflowError):
        result = empty_observation('invalid')
    result['failure'] = _failure(directory, identity, check)
    return result


def with_process_state(result, process):
    """实际owner状态优先；停止前快照可显示为历史计数，历史连接不能升级为当前活跃。"""
    if process.get('state') != 'ready' or process.get('ready') is not True:
        result['active'] = False if process.get('state') in ('closed', 'stopping', 'faulted', 'disabled') else None
        if result['available']:
            result.update(status='historical', reason='当前采集进程已停止、停止中或失败；下方为本实例最后发布的记录', connected=False)
        return result
    if not result['available']:
        return result
    result['active'] = bool(result['connected'] and result['phase'] == 'running' and not result['error'] and not result['failure'])
    failure_reason = '采集子服务报告失败，请核对故障阶段' if result['failure'] else None
    result['reason'] = result['error'] or failure_reason or (
        '当前采集连接已建立；报价是否持续更新请查看来源与接收时间，完整分钟另验' if result['active'] else
        '当前来源已断连或尚未接入，采集进程正在等待来源；累计计数保留原记录')
    return result
