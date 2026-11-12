"""安装后的独立WT入口；只管理本控制身份的组件和运行收据。"""
from __future__ import annotations

import argparse
import json
import os
import signal
import time
from uuid import UUID, uuid4

from guanheng_market_client.runtime_status import replace_status

from .managed_local_process import _inspect, _json, _path, _read, _require, _sha
from .runtime import Runtime, RuntimeConfig
from .runtime_diagnostics import FailureDiagnostic
from .snapshot_publisher import SnapshotPublisher


def _publish(directory, name, value, *, replace=False):
    """正文完整关闭后再发布；status用原共享读取/原子替换协议。"""
    temporary = directory / ('.' + name + '.' + str(uuid4()))
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False,
                     sort_keys=True, separators=(',', ':')).encode('ascii')
    with temporary.open('xb') as stream:
        stream.write(raw)
    if replace:
        replace_status(temporary, directory / name)
    else:
        temporary.rename(directory / name)


class _InstanceLease:
    """同控制根下同instance_id只有一个owner；OS锁随异常退出自动释放。"""
    def __init__(self, root, instance_id):
        self.path, self.stream = root / (instance_id + '.lock'), None

    def __enter__(self):
        import msvcrt
        self.stream = self.path.open('a+b')
        try:
            _inspect(self.path)
            self.stream.seek(0)
            if self.stream.read(1) == b'':
                self.stream.write(b'0')
                self.stream.flush()
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except BaseException:
            self.stream.close()
            self.stream = None
            raise
        return self

    def __exit__(self, *unused):
        import msvcrt
        try:
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.stream.close()
            self.stream = None


def run(config, configuration_sha256, directory, control_id):
    """持续运行直到原stop收据/系统信号；不设来源配对60秒窗口。

    运行长期存在，各组件自己的业务请求及关闭仍有独立预算。发生故障时退出，
    不自动重启或重新提交金融命令；原未知责任留在原组件持久状态中。
    """
    _sha(configuration_sha256)
    _require(str(UUID(control_id)) == control_id)
    directory = _path(str(directory), e_drive=True)
    _inspect(directory.parent, directory=True)
    runtime = None
    identity = {'control_id': control_id, 'instance_id': config.instance_id,
                'pid': os.getpid(), 'configuration_sha256': configuration_sha256}
    previous_handlers, stopped, failed = {}, False, None
    with _InstanceLease(directory.parent, config.instance_id):
        directory.mkdir()
        with FailureDiagnostic(directory, identity, _publish) as diagnostic:
            try:
                snapshots = SnapshotPublisher(directory, replace=replace_status)
                runtime = Runtime(config)
                diagnostic.phase = 'signal_register'
                for sig in (signal.SIGINT, signal.SIGTERM):
                    previous_handlers[sig] = signal.signal(sig, lambda *unused: runtime.request_close())
                diagnostic.phase = 'runtime_start'
                if not runtime.start(time.monotonic() + config.startup_seconds):
                    raise RuntimeError('WT component startup failed')
                diagnostic.phase = 'initial_status_snapshot'
                snapshot = runtime.status()
                diagnostic.phase = 'initial_status_publish'
                snapshots.publish({**snapshot, **identity})
                diagnostic.phase = 'ready_publish'
                _publish(directory, 'ready.json', {'schema': 'guanheng.wt-runtime-ready.v1', **identity})
                diagnostic.phase = 'stop_poll'
                while not runtime.wait_close_request(0):
                    diagnostic.phase = 'loop_status_snapshot'
                    snapshot = runtime.status()
                    diagnostic.phase = 'loop_status_publish'
                    snapshots.publish({**snapshot, **identity})
                    diagnostic.phase = 'stop_read'
                    try:
                        stop = _json(_read(directory / 'stop.json', 4096))
                    except FileNotFoundError:
                        stop = None
                    if stop is not None:
                        diagnostic.phase = 'stop_validate'
                        expected = {'schema': 'guanheng.wt-runtime-stop.v1', 'control_id': control_id,
                                    'instance_id': config.instance_id,
                                    'configuration_sha256': configuration_sha256}
                        _require(stop == expected)
                        diagnostic.phase = 'close_request'
                        runtime.request_close()
                    else:
                        diagnostic.phase = 'component_check'
                        if not runtime.check():
                            failed = 'component_runtime'
                            diagnostic.phase = 'close_request'
                            runtime.request_close()
                    diagnostic.phase = 'cycle_wait'
                    runtime.wait_close_request(.2)
                    diagnostic.phase = 'stop_poll'
            except Exception as error:
                failed = failed or 'runtime_failure'
                diagnostic.capture(error)
            finally:
                if runtime is not None:
                    diagnostic.phase = 'runtime_close'
                    stopped = runtime.close(config.stop_seconds)
                    diagnostic.phase = 'final_status_snapshot'
                    snapshot = runtime.status()
                    diagnostic.phase = 'final_status_publish'
                    snapshots.publish({**snapshot, **identity})
                diagnostic.phase = 'signal_restore'
                for sig, handler in previous_handlers.items():
                    signal.signal(sig, handler)
                # closed只在所有原owner实际退出、Job/管道/线程确认后发布；故障不伪装成功。
                success = stopped and failed is None
                name = 'closed.json' if success else 'failure.json'
                diagnostic.phase = 'receipt_publish'
                _publish(directory, name, {'schema': 'guanheng.wt-runtime-' + ('closed' if success else 'failure') + '.v1',
                    **identity, 'components_closed': stopped, 'error_code': failed,
                    'status': 'stopped' if success else 'faulted'})
    return 0 if success else 2


def record_process_loss(config, configuration_sha256, directory, control_id):
    """原整树消失后的故障核查入口；取得原实例租约，只发布故障及可读状态。"""
    import hashlib
    from datetime import datetime, timezone
    from .execution_recovery import require_process_exited, record_execution_process_loss
    _sha(configuration_sha256)
    _require(str(UUID(control_id)) == control_id)
    directory = _path(str(directory), e_drive=True)
    _inspect(directory, directory=True)
    with _InstanceLease(directory.parent, config.instance_id):
        ready = _json(_read(directory / 'ready.json', 4096))
        raw = _read(directory / 'status.json', 256 * 1024)
        status = _json(raw)
        identity = dict(control_id=control_id, instance_id=config.instance_id,
                        configuration_sha256=configuration_sha256, pid=ready['pid'])
        _require(ready['schema'] == 'guanheng.wt-runtime-ready.v1'
                 and status['schema'] == 'guanheng.wt-runtime-status.v1'
                 and all(ready.get(k) == v and status.get(k) == v for k, v in identity.items())
                 and directory.name == control_id and not (directory / 'closed.json').exists())
        require_process_exited(identity['pid'])
        components = status['components']
        configured = dict(config.components)
        _require(type(components) is dict and set(components) == set(configured))
        component_pids = {}
        for name, component in components.items():
            _require(type(component) is dict)
            if configured[name].kind == 'analysis_window':
                # 窗口发布线程归 WT 进程，刷新子进程由 WT 持有的终止型 Job 回收。
                pid = component.get('pid', identity['pid'])
                _require(component.get('schema') == 'guanheng.analysis-window-process-status.v1'
                         and type(pid) is int and pid == identity['pid'])
            else:
                pid = component.get('pid')
                require_process_exited(pid)
            component_pids[name] = pid
        loss_path = directory / 'owner-loss.json'
        if loss_path.exists():
            loss = _json(_read(loss_path, 4096))
            _require(set(loss) == {'schema', *identity, 'status_sha256', 'component_pids',
                                  'observed_at', 'observer_pid', 'reason'}
                     and loss['schema'] == 'guanheng.wt-runtime-owner-loss.v1'
                     and all(loss.get(k) == v for k,v in identity.items())
                     and loss['reason'] == 'process_lost' and loss['component_pids'] == component_pids)
            _sha(loss['status_sha256'])
        failure_path = directory / 'failure.json'
        failure = None
        if failure_path.exists():
            failure = _json(_read(failure_path, 4096))
            _require(failure.get('schema') == 'guanheng.wt-runtime-failure.v1'
                     and all(failure.get(k) == v for k,v in identity.items())
                     and failure.get('status') == 'faulted' and failure.get('components_closed') is False
                     and (failure.get('error_code') != 'owner_process_lost' or loss_path.exists()))
        if 'execution' in components:
            reference = components['execution']['business_observation']
            _require(reference['schema'] == 'guanheng.execution-observation-reference.v1')
            _require(reference.get('pid') == component_pids['execution'])
            execution_control = _path(reference['path']).parent
            _require(_path(reference['ready_path']) == execution_control / 'ready.json')
            if not any(os.path.lexists(execution_control / receipt) for receipt in
                       ('closed.json', 'close-prepared.json', 'failure.json')):
                record_execution_process_loss(execution_control,
                    expected={k:reference[k] for k in ('control_id','config_sha256','pid')})
        if not loss_path.exists():
            _publish(directory, 'owner-loss.json', dict(
                schema='guanheng.wt-runtime-owner-loss.v1',  # 独立故障核查收据，不证明正常join。
                **identity,  # 原运行身份，ready/status/配置共同绑定。
                status_sha256=hashlib.sha256(raw).hexdigest(),  # 核查时原观察正文摘要。
                component_pids=component_pids,  # 已逐项核退出的原PID。
                observed_at=datetime.now(timezone.utc).isoformat(),  # 核查UTC时间。
                observer_pid=os.getpid(),  # 本次恢复核查者PID。
                reason='process_lost'))  # 固定故障，原退出原因/退出码保持未知。
        if failure is None:
            for component in components.values():
                component.update(state='faulted', ready=False, error_code='owner_process_lost')
            status.update(state='faulted', ready=False, error_code='owner_process_lost')
            SnapshotPublisher(directory, replace=replace_status).publish(status)
            _publish(directory, 'failure.json', dict(
                schema='guanheng.wt-runtime-failure.v1', **identity,
                components_closed=False,  # 原Job/线程join凭据缺失，不能声明正常关闭。
                error_code='owner_process_lost', status='faulted'))
    return 0


def main(argv=None):
    """控制入口只接受原字节配置身份和新控制目录；错误消息保持有限，不打印凭据。"""
    parser = argparse.ArgumentParser(description='WT独立运行入口')
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--control-directory', required=True)
    parser.add_argument('--control-id', required=True)
    parser.add_argument('--record-process-loss', action='store_true', help='核原整树退出并记录故障，保留关闭未知')
    args = parser.parse_args(argv)
    try:
        config = RuntimeConfig.from_path(args.config, args.config_sha256)
        if args.record_process_loss:
            return record_process_loss(config, args.config_sha256, args.control_directory, args.control_id)
        return run(config, args.config_sha256, args.control_directory, args.control_id)
    except Exception:
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
