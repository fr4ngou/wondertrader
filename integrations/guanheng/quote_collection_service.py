"""独立受管采集子服务：直接WinSHM→原生DataKit，控制文件仅在QMT外使用。"""
from __future__ import annotations

# 原生发行包包含同一源码闭包；-I启动不依赖工作目录或PYTHONPATH。
import sys
from pathlib import Path
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_RELEASE_ROOT = _PACKAGE_ROOT.parent
for _root in (_PACKAGE_ROOT, _RELEASE_ROOT/'connectors/qmt_shm/agent', _RELEASE_ROOT/'connectors/qmt_shm/host'):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

import argparse
import base64
import hashlib
import json
import math
import os
import re
import stat
import threading
import time
from uuid import UUID, uuid4
from guanheng.quote_collection import QuoteCollection
from guanheng.collection_status import replace_status

# 配置/启动失败进入新的服务收尾阶段；外层原启动/停止D仍有最终Job终止权。
# 正常控制停止只使用父进程发来的原绝对D，不使用此回退预算。
_FAILED_SERVICE_CLOSE_SECONDS = 5.0
_ACTIVE_SERVICE = None


class _ServiceResources:
    """进程内持有整个未收束实例，Writer存活期间目录锁始终存活。"""
    def __init__(self):
        self.collection = None
        self.ownership = None


def _need(value):
    if not value:
        raise ValueError('invalid quote collection service input')


def _sha(value):
    _need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None)
    return value


def _path(value):
    _need(type(value) is str and 0 < len(value) <= 8192 and '\x00' not in value)
    path = Path(value)
    _need(path.is_absolute() and '..' not in path.parts)
    return path


def _inspect(path, directory=False):
    for item in reversed((path, *path.parents)):
        info = item.lstat()
        _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400)
        _need(stat.S_ISDIR(info.st_mode) if item != path or directory else stat.S_ISREG(info.st_mode))
    return info


def _read(path, maximum, expected=None):
    before = _inspect(path)
    _need(0 < before.st_size <= maximum)
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        _need((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
              (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns))
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    final = _inspect(path)
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    _need(len(raw) == before.st_size and identity(after) == identity(opened) == identity(final))
    if expected is not None:
        _need(hashlib.sha256(raw).hexdigest() == _sha(expected))
    return raw


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _need(key not in result)
            result[key] = value
        return result
    def invalid(_value):
        raise ValueError('nonfinite collection input')
    value = json.loads(raw.decode('utf8'), object_pairs_hook=unique, parse_constant=invalid)
    _need(type(value) is dict)
    return value


def _fields(value, names):
    _need(type(value) is dict and set(value) == set(names.split()))


def _configuration(path, expected):
    value = _json(_read(path, 65536, expected))
    _fields(value, 'schema connection native archive_session status_interval_seconds')
    _need(value['schema'] == 'qmt.quote-collector.v1')
    connection, native = value['connection'], value['native']
    _need(type(connection) is dict and set(connection) in (
        {'path', 'sha256', 'secret_env'},
        {'path', 'sha256', 'secret_env', 'secret_encoding'}))
    _fields(native, 'configuration configuration_sha256 directory session_library_sha256')
    _need(type(connection['secret_env']) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', connection['secret_env']))
    settings = _json(_read(_path(connection['path']), 2097152, connection['sha256']))
    _need('secret' not in settings)
    # 唯一的秘密注入发生在子进程；argv、状态和控制收据均不含秘密。
    encoding = connection.get('secret_encoding', 'utf8')
    _need(encoding in ('utf8', 'base64'))
    encoded_secret = os.environ[connection['secret_env']]
    settings['secret'] = (base64.b64decode(encoded_secret.encode('ascii'), validate=True)
                          if encoding == 'base64' else encoded_secret.encode('utf8'))
    from guanheng_qmt_shm_agent.quote_stream_contract import validate_settings
    settings = validate_settings(settings)
    config_path = _path(native['configuration'])
    native_raw = _read(config_path, 2097152, native['configuration_sha256'])
    config = _json(native_raw)
    writer = config.get('writer')
    _need(type(writer) is dict and writer.get('module') == 'WtDataStorageLifecycle')
    # 薄宿主工作目录由托管器决定，基础资料和数据根必须显式绝对定位。
    root = _path(writer.get('path'))
    files = config.get('basefiles')
    _need(type(files) is dict and {'session', 'commodity', 'contract'} <= set(files))
    for entry in files.values():
        _path(entry)
    if config.get('allday') is not True:
        _path(config.get('statemonitor'))
    directory = _path(native['directory']); _inspect(directory, True)
    _read(directory/'GuanhengDataKitSession.dll', 67108864, native['session_library_sha256'])
    interval = value['status_interval_seconds']
    _need(type(interval) in (int, float) and .1 <= interval <= 60 and math.isfinite(interval))
    sid = value['archive_session']
    _need(sid is None or type(sid) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,15}', sid))
    return value, settings, native_raw, directory, root


class _WriterOwnership:
    """同一受管采集入口的协作单写者锁；导入及其他Writer另按部署交接。"""
    def __init__(self, root):
        self.stream = None
        root.mkdir(parents=True, exist_ok=True)
        _inspect(root, True)
        target = root/'.qmt-collection-owner.lock'
        if target.exists():
            _inspect(target)
        stream = target.open('a+b')
        try:
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            self.stream = stream
        except BaseException:
            stream.close()
            raise
    def close(self):
        if self.stream is not None:
            # 关闭句柄释放同一byte-range lock，保留锁文件供下次实例使用。
            self.stream.close(); self.stream = None


def _stop(path, control_id):
    try:
        value = _json(_read(path/'stop.json', 4096))
    except FileNotFoundError:
        return None
    _fields(value, 'schema control_id deadline')
    _need(value['schema'] == 'qmt.quote-collector-stop.v1' and value['control_id'] == control_id)
    deadline = value['deadline']
    _need(type(deadline) in (int, float) and math.isfinite(deadline))
    return float(deadline)


def serve(configuration, configuration_sha256, control_directory, control_id):
    """管理线程独占collection；没有默认业务寿命，停止由原父控制D驱动。"""
    global _ACTIVE_SERVICE
    _need(str(UUID(control_id)) == control_id and control_directory.name == control_id)
    _sha(configuration_sha256)
    from guanheng_qmt_shm.private_files import create_private_directory, write_private_new
    # 全局强引用覆盖失败返回至父Job最终收口的窗口，避免仍有Writer时释放目录锁。
    _need(_ACTIVE_SERVICE is None)
    resources = _ServiceResources()
    _ACTIVE_SERVICE = resources
    collection = ownership = None
    directory_created = False
    stop_deadline = None
    stage, error = 'configuration', None
    failure_kind, failure_winerror = None, None
    def remember_failure(code, exception):
        nonlocal error, failure_kind, failure_winerror
        if error is None:
            error = code
            kind = type(exception).__name__
            failure_kind = kind if kind in ('PermissionError', 'FileNotFoundError', 'TimeoutError',
                'ValueError', 'RuntimeError', 'OSError', 'MemoryError') else 'other'
            winerror = getattr(exception, 'winerror', None)
            failure_winerror = winerror if type(winerror) is int and 0 <= winerror <= 65535 else None
    def publish(name, value, replace=False):
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
        _need(0 < len(raw) <= 65536)
        # ready/closed也先写完并关闭私有临时文件，名称出现即代表完整收据。
        # 直接创建最终名字会让父读取方观察到零字节或独占写句柄。
        temporary = control_directory/(name + '-' + str(uuid4()) + '.tmp')
        write_private_new(temporary, raw)
        if replace:
            replace_status(temporary, control_directory/name)
        else:
            os.rename(temporary, control_directory/name)
    try:
        value, settings, native_raw, native_directory, data_root = _configuration(configuration, configuration_sha256)
        create_private_directory(control_directory); directory_created = True
        # Native读取本实例已验证的字节副本，部署文件随后被替换不会改变Writer模式/根。
        config_path = control_directory/'native-input.json'
        write_private_new(config_path, native_raw)
        stage = 'writer_ownership'
        ownership = _WriterOwnership(data_root)
        resources.ownership = ownership
        stage = 'native_start'
        collection = QuoteCollection(settings, config_path, native_directory, value['archive_session'])
        resources.collection = collection
        collection.start()
        stage = 'ready_publish'
        publish('ready.json', dict(schema='qmt.quote-collector-ready.v1', control_id=control_id,
                pid=os.getpid(), configuration_sha256=configuration_sha256, listener_ready=True))
        stage = 'collection'
        next_status = 0.
        while True:
            stop_deadline = _stop(control_directory, control_id)
            if stop_deadline is not None:
                break
            collection.check_health()
            snapshot = collection.status()
            if (snapshot['error'] is not None or snapshot['receiver_failure'] == 'consumer_failed'
                    or snapshot['receiver_cleanup_failure'] is not None):
                raise RuntimeError('collection stopped on source consumer failure')
            now = time.monotonic()
            if now >= next_status:
                stage = 'status_publish'
                publish('status.json', dict(schema='qmt.quote-collector-status.v1', control_id=control_id,
                        pid=os.getpid(), configuration_sha256=configuration_sha256,
                        observed_wall_time=time.time(), collection=snapshot), True)
                stage = 'collection'
                next_status = now + value['status_interval_seconds']
            time.sleep(.05)
    except BaseException as exception:
        remember_failure(stage, exception)
    finally:
        # 正常停止不另起预算；失败收尾保持强引用，外层Job拥有最终原截止。
        if collection is not None:
            deadline = stop_deadline if stop_deadline is not None else time.monotonic() + _FAILED_SERVICE_CLOSE_SECONDS
            try:
                collection.close(deadline)
                if not collection.closed_complete or time.monotonic() >= deadline:
                    error = error or 'close_unconfirmed'
                if collection.status()['error'] is not None:
                    error = error or 'collection'
            except BaseException as exception:
                remember_failure('close_unconfirmed', exception)
        if ownership is not None and (collection is None or collection.closed_complete):
            ownership.close()
            resources.ownership = None
        if collection is None or collection.closed_complete:
            _ACTIVE_SERVICE = None
        if directory_created and error is not None:
            try:
                publish('failure.json', dict(schema='qmt.quote-collector-failure.v1',
                    control_id=control_id, pid=os.getpid(), configuration_sha256=configuration_sha256,
                    stage=error, exception_kind=failure_kind, winerror=failure_winerror,
                    components_closed=collection is None or collection.closed_complete))
            except BaseException:
                pass  # 原业务/资源失败保持；诊断写入失败不能替换其返回结果。
        if directory_created and error is None and collection is not None and collection.closed_complete:
            publish('closed.json', dict(schema='qmt.quote-collector-closed.v1', control_id=control_id,
                    pid=os.getpid(), configuration_sha256=configuration_sha256, status='stopped',
                    receiver_closed=True, native_closed=True, error_code=None))
    return 0 if error is None else 2


def main():
    parser = argparse.ArgumentParser(description='Managed native QMT quote collection')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--control-directory', type=Path, required=True)
    parser.add_argument('--control-id', required=True)
    args = parser.parse_args()
    return serve(_path(str(args.config)), args.config_sha256,
                 _path(str(args.control_directory)), args.control_id)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # 供应商/配置异常仅保留在本owner；stderr不输出私有路径和原始异常文本。
        raise SystemExit('quote collection service failed') from None
