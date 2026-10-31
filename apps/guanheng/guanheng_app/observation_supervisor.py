"""独立观察服务维护入口；原进程owner持有Job，Web生命周期只读同根。"""
import argparse
import math
import os
from pathlib import Path
import signal
from threading import Event
import time
from uuid import UUID, uuid4

from .managed_local_process import _inspect, _path, _require, _sha
from .observation.storage import encode
from .observation_process import ObservationCollectionProcess, ObservationCollectionProcessConfig
from .observation_service import StopController
from .thread_owner import ThreadOwner


def supervise(deployment, expected_sha256, directory, control_id, *, seconds=None):
    """独占一个监督实例；有限seconds包含启动、工作和关闭，返回0才授正常关闭。

    配置、来源凭据和子进程仍归原ObservationCollectionProcess。维护stop收据
    与本机信号只请求停止；主线程沿首个截止关闭原owner并写本实例结果。
    """
    _require(str(UUID(control_id)) == control_id and directory.name == control_id)
    _sha(expected_sha256)
    _require(seconds is None or type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 604800)
    started = time.monotonic()
    total_deadline = None if seconds is None else started + seconds
    owner = stop = starter = None
    created = joined = closed = False
    startup_joined = True
    error = None
    stage = 'supervisor_configuration'
    signalled = False
    handlers = {}

    def publish(name, value, deadline):
        def within_deadline():
            if time.monotonic() >= deadline:
                raise TimeoutError('supervisor receipt deadline')
        within_deadline()
        raw = encode(value)
        _require(len(raw) <= 4096)
        temporary = directory / (name + '-' + str(uuid4()) + '.tmp')
        with temporary.open('xb') as stream:
            within_deadline()
            _require(stream.write(raw) == len(raw))
            stream.flush()
            within_deadline()
            os.fsync(stream.fileno())
        within_deadline()
        _inspect(temporary)
        os.rename(temporary, directory / name)
        within_deadline()

    def request_stop(_number, _frame):
        nonlocal signalled
        signalled = True

    try:
        configuration = ObservationCollectionProcessConfig.from_path(deployment, expected_sha256)
        _require(configuration is not None)
        _inspect(directory.parent, directory=True)
        directory.mkdir()
        created = True
        stop = StopController(directory, control_id)
        stop.monitor.start()
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, 'SIGBREAK') else [])):
            handlers[number] = signal.signal(number, request_stop)
        owner = ObservationCollectionProcess(configuration)
        stage = 'supervisor_failed'
        startup_deadline = time.monotonic() + configuration.startup_seconds
        if total_deadline is not None:
            startup_deadline = min(startup_deadline, total_deadline - configuration.stop_seconds - 2)
        _require(startup_deadline > time.monotonic())
        startup_done = Event()
        startup_result = []

        def start_owner():
            try:
                startup_result.append(owner.start(startup_deadline))
            except BaseException:
                startup_result.append(False)
            finally:
                startup_done.set()

        # 主线程持续接收首个停止请求；原owner继续独占子进程和Job。
        starter = ThreadOwner(target=start_owner, name='observation-supervisor-start')
        starter.start()
        while not startup_done.is_set() and not signalled and not stop.is_set():
            if time.monotonic() >= startup_deadline:
                break
            stop.wait(.05)
        cancelled = signalled or stop.is_set()
        if not cancelled and (not startup_done.is_set() or startup_result != [True]):
            error = 'scheduler_start'
        elif not cancelled:
            status = owner.status()
            publish('ready.json', dict(schema='guanheng.observation-supervisor-ready.v1',
                control_id=control_id, pid=os.getpid(), configuration_sha256=expected_sha256,
                child_control_id=owner._control_id, child_pid=status['pid']), startup_deadline)
            work_deadline = None if total_deadline is None else total_deadline - configuration.stop_seconds - 2
            while not signalled and not stop.is_set() and (work_deadline is None or time.monotonic() < work_deadline):
                if not owner.status()['ready']:
                    error = 'scheduler_failed'
                    break
                stop.wait(.2)
        if stop.error:
            error = stop.error
    except BaseException:
        error = error or stage
    finally:
        deadline = time.monotonic() + (owner.shutdown_seconds if owner is not None else 2)
        if total_deadline is not None:
            deadline = min(deadline, total_deadline)
        if stop is not None:
            with stop.lock:
                if stop.deadline is not None:
                    deadline = min(deadline, stop.deadline)
                stop.deadline = deadline
            stop.done.set()
        if owner is not None:
            try:
                closed = owner.close(max(0, deadline - time.monotonic()))
            except BaseException:
                error = error or 'supervisor_close'
        if starter is not None:
            startup_joined = starter.join_until(deadline)
        if stop is not None:
            try:
                joined = stop.close()
            except BaseException:
                error = error or 'supervisor_monitor'
        for number, handler in handlers.items():
            signal.signal(number, handler)
        complete = closed and joined and startup_joined and time.monotonic() < deadline and error is None
        if created:
            try:
                publish('closed.json' if complete else 'failure.json', dict(
                    schema='guanheng.observation-supervisor-closed.v1' if complete else 'guanheng.observation-supervisor-failure.v1',
                    control_id=control_id, pid=os.getpid(), configuration_sha256=expected_sha256,
                    scheduler_closed=closed, monitor_joined=joined, startup_joined=startup_joined,
                    publication_deadline=deadline,
                    error_code=None if complete else error or 'supervisor_close'), deadline)
            except BaseException:
                # 已可见的收据保留资源事实；最终发布晚到或失败均禁止成功退出。
                complete = False
    return 0 if complete else 1


def main():
    parser = argparse.ArgumentParser(description='观衡独立观察服务监督入口')
    parser.add_argument('--deployment', required=True)
    parser.add_argument('--deployment-sha256', required=True)
    parser.add_argument('--control-directory', required=True)
    parser.add_argument('--control-id', required=True)
    parser.add_argument('--seconds', type=float)
    args = parser.parse_args()
    try:
        return supervise(args.deployment, args.deployment_sha256, _path(args.control_directory), args.control_id, seconds=args.seconds)
    except (OSError, ValueError, TypeError):
        parser.error('观察服务部署或控制配置无效，请核对安装记录')


if __name__ == '__main__':
    raise SystemExit(main())
