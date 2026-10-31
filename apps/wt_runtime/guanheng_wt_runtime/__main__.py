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
        try:
            runtime = Runtime(config)
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[sig] = signal.signal(sig, lambda *unused: runtime.request_close())
            if not runtime.start(time.monotonic() + config.startup_seconds):
                raise RuntimeError('WT component startup failed')
            _publish(directory, 'status.json', {**runtime.status(), **identity}, replace=True)
            _publish(directory, 'ready.json', {'schema': 'guanheng.wt-runtime-ready.v1', **identity})
            while not runtime.wait_close_request(0):
                _publish(directory, 'status.json', {**runtime.status(), **identity}, replace=True)
                try:
                    stop = _json(_read(directory / 'stop.json', 4096))
                except FileNotFoundError:
                    stop = None
                if stop is not None:
                    expected = {'schema': 'guanheng.wt-runtime-stop.v1', 'control_id': control_id,
                                'instance_id': config.instance_id,
                                'configuration_sha256': configuration_sha256}
                    _require(stop == expected)
                    runtime.request_close()
                elif not runtime.check():
                    failed = 'component_runtime'
                    runtime.request_close()
                runtime.wait_close_request(.2)
        except Exception:
            failed = failed or 'runtime_failure'
        finally:
            if runtime is not None:
                stopped = runtime.close(config.stop_seconds)
                _publish(directory, 'status.json', {**runtime.status(), **identity}, replace=True)
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            # closed只在所有原owner实际退出、Job/管道/线程确认后发布；故障不伪装成功。
            success = stopped and failed is None
            name = 'closed.json' if success else 'failure.json'
            _publish(directory, name, {'schema': 'guanheng.wt-runtime-' + ('closed' if success else 'failure') + '.v1',
                **identity, 'components_closed': stopped, 'error_code': failed,
                'status': 'stopped' if success else 'faulted'})
    return 0 if success else 2


def main(argv=None):
    """控制入口只接受原字节配置身份和新控制目录；错误消息保持有限，不打印凭据。"""
    parser = argparse.ArgumentParser(description='WT独立运行入口')
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--control-directory', required=True)
    parser.add_argument('--control-id', required=True)
    args = parser.parse_args(argv)
    try:
        config = RuntimeConfig.from_path(args.config, args.config_sha256)
        return run(config, args.config_sha256, args.control_directory, args.control_id)
    except Exception:
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
