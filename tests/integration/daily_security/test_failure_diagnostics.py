"""真实数据入口的写盘失败与首错保留；原生Reader/发布租约为显式替身。"""
from contextlib import nullcontext
import errno
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

import pytest

from integrations.guanheng import daily_data_service as daily
from integrations.guanheng import source_market_service as market


@pytest.fixture
def source_control_root():
    # 原SMP私有目录合同要求E盘；使用任务工作树的自有临时根，保留真实文件准入。
    root = Path(__file__).resolve().parents[3] / 'build'
    root.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='data-failure-', dir=root) as directory:
        yield Path(directory)


@pytest.mark.parametrize('receipt_fails', [False, True])
def test_market_keeps_system_error_and_cleanup_context(source_control_root, monkeypatch, receipt_fails):
    tmp_path = source_control_root
    control = str(uuid4())
    directory = tmp_path / control
    secret = 'PRIVATE_ACCOUNT_TOKEN_AND_PATH'
    original = OSError(errno.ENOSPC, secret, secret)
    monkeypatch.setenv('TEST_DATA_TOKEN', secret)
    monkeypatch.setattr(market, '_configuration', lambda *_: (
        dict(token_env='TEST_DATA_TOKEN', listen=dict(host='127.0.0.1', port=18100), socket_timeout=1), {}))
    native_calls = []
    def failed_native(_source):
        native_calls.append(True)
        raise original
    monkeypatch.setattr(market, 'create_native_source_market', failed_native)
    write = market.write_private_new
    def publish(path, raw):
        if receipt_fails and Path(path).name.startswith('failure.json-'):
            raise PermissionError(errno.EACCES, secret)
        return write(path, raw)
    monkeypatch.setattr(market, 'write_private_new', publish)
    assert market.serve(tmp_path/'config.json', 'a'*64, directory, control) == 2
    assert native_calls == [True]
    raw = (directory/'diagnostic.json').read_text(encoding='utf-8')
    assert secret not in raw and str(directory) not in raw
    diagnostic = json.loads(raw)
    assert diagnostic['control_id'] == control
    assert diagnostic['failure']['phase'] == 'native_start'
    assert diagnostic['failure']['errno'] == errno.ENOSPC
    assert any(row['file'] == 'source_market_service.py' for row in diagnostic['failure']['frames'])
    cleanup = diagnostic['cleanup_errors']
    assert [row['errno'] for row in cleanup] == ([errno.EACCES] if receipt_fails else [])


@pytest.mark.parametrize('phase,code', [('http_start', errno.EADDRINUSE), ('ready_publish', errno.ENOSPC)])
def test_market_initialization_phase_is_preserved(source_control_root, monkeypatch, phase, code):
    control = str(uuid4())
    directory = source_control_root/control
    class Native:
        closed = False
        def close(self):self.closed = True
    native = Native()
    class Server:
        server_port = 18100
        def __init__(self, *_args, **_kwargs):
            if phase == 'http_start':raise OSError(code, 'private bind detail')
        def server_close(self):native.close()
    monkeypatch.setenv('TEST_DATA_TOKEN', 'private-token')
    monkeypatch.setattr(market, '_configuration', lambda *_: (
        dict(token_env='TEST_DATA_TOKEN', listen=dict(host='127.0.0.1', port=18100), socket_timeout=1), {}))
    monkeypatch.setattr(market, 'create_native_source_market', lambda _source: native)
    monkeypatch.setattr(market, 'MarketHTTPServer', Server)
    write = market.write_private_new
    def publish(path, raw):
        if phase == 'ready_publish' and Path(path).name.startswith('ready.json-'):
            raise OSError(code, 'private ready write detail')
        return write(path, raw)
    monkeypatch.setattr(market, 'write_private_new', publish)
    assert market.serve(source_control_root/'config.json', 'a'*64, directory, control) == 2
    value = json.loads((directory/'diagnostic.json').read_bytes())
    assert (value['failure']['phase'], value['failure']['errno']) == (phase, code)
    assert native.closed


def test_normal_market_stop_has_no_diagnostic(source_control_root, monkeypatch):
    control = str(uuid4())
    directory = source_control_root/control
    closed = []
    class Server:
        server_port = 18100
        def __init__(self, *_args, **_kwargs):pass
        def handle_request(self):
            (directory/'stop.json').write_text(json.dumps(dict(schema='guanheng.source-market-stop.v1',
                control_id=control, deadline=time.monotonic()+5)), encoding='utf-8')
        def server_close(self):closed.append(True)
    monkeypatch.setenv('TEST_DATA_TOKEN', 'private-token')
    monkeypatch.setattr(market, '_configuration', lambda *_: (
        dict(token_env='TEST_DATA_TOKEN', listen=dict(host='127.0.0.1', port=18100), socket_timeout=1), {}))
    monkeypatch.setattr(market, 'create_native_source_market', lambda _source: object())
    monkeypatch.setattr(market, 'MarketHTTPServer', Server)
    assert market.serve(source_control_root/'config.json', 'a'*64, directory, control) == 0
    assert closed == [True]
    assert not (directory/'diagnostic.json').exists()
    assert json.loads((directory/'closed.json').read_bytes())['native_closed'] is True


@pytest.mark.parametrize('receipt_fails', [False, True])
def test_daily_ready_write_failure_preserves_original_error(tmp_path, monkeypatch, receipt_fails):
    control = str(uuid4())
    directory = tmp_path / control
    secret = 'PRIVATE_DATA_FAILURE_DETAIL'
    original = OSError(errno.ENOSPC, secret)
    config = dict(directory=str(tmp_path/'state'), template=dict(publication_directory=str(tmp_path/'publication')),
                  inputs=dict(public_facts={}, supplement_facts=dict(targets=[])))
    monkeypatch.setattr(daily, '_load', lambda _descriptor: config)
    monkeypatch.setattr(daily, 'validate_configuration', lambda value: value)
    monkeypatch.setattr(daily, 'GenerationPublisher', lambda _path: nullcontext())
    save = daily._save
    def publish(path, value):
        if path.name == 'ready.json':
            raise original
        if receipt_fails and path.name == 'failure.json':
            raise PermissionError(errno.EACCES, secret)
        return save(path, value)
    monkeypatch.setattr(daily, '_save', publish)
    with pytest.raises(OSError) as raised:
        daily.serve(dict(path=str(tmp_path/'config.json'), sha256='a'*64), directory, control, once=True)
    assert raised.value is original
    raw = (directory/'diagnostic.json').read_text(encoding='utf-8')
    assert secret not in raw
    diagnostic = json.loads(raw)
    assert diagnostic['failure']['errno'] == errno.ENOSPC
    assert any(row['file'] == 'daily_data_service.py' for row in diagnostic['failure']['frames'])
    assert [row['errno'] for row in diagnostic['cleanup_errors']] == ([errno.EACCES] if receipt_fails else [])


def diagnostic(publish):
    from integrations.guanheng.data_process_diagnostics import DataFailureDiagnostic
    return DataFailureDiagnostic(publish, control_id=str(uuid4()), configuration_sha256='b'*64, role='daily_data')


def test_normal_diagnostic_has_no_disk_work():
    calls = []
    owner = diagnostic(lambda *args: calls.append(args))
    owner.finish()
    assert calls == []


def test_private_exception_context_and_cleanup_are_bounded_and_deduplicated():
    secret = 'PRIVATE_CUSTOM_CLASS_MESSAGE_PATH'
    records = []
    owner = diagnostic(lambda _name, value: records.append(json.loads(json.dumps(value))))
    previous = OSError(errno.EIO, secret, secret)
    for _ in range(5):
        current = type(secret, (Exception,), {})(secret)
        current.__cause__ = previous
        previous = current
    owner.capture('serving', previous)
    owner.capture('close', RuntimeError(secret))
    owner.cleanup('close', PermissionError(errno.EACCES, secret))
    owner.cleanup('close', OSError(errno.EINVAL, secret))
    owner.finish()
    owner.finish()
    assert len(records) == 2
    value = records[-1]
    assert secret not in json.dumps(value)
    assert value['failure']['exception_type'] == 'Exception'
    assert len(value['failure']['causes']) == 2
    assert [row['errno'] for row in value['cleanup_errors']] == [errno.EACCES]
    assert len(json.dumps(value).encode()) < 65536


def test_failed_first_diagnostic_is_retried_at_original_finalization():
    attempts, saved = [], []
    def publish(name, value):
        attempts.append(name)
        if len(attempts) == 1:
            raise OSError(errno.ENOSPC, 'private diagnostic write detail')
        saved.append(value)
    owner = diagnostic(publish)
    owner.capture('serving', OSError(errno.EIO, 'private original failure'))
    owner.finish()
    owner.finish()
    assert attempts == ['diagnostic.json', 'diagnostic.json']
    assert len(saved) == 1 and saved[0]['failure']['errno'] == errno.EIO


def test_daily_first_error_is_saved_before_resource_cleanup(tmp_path, monkeypatch):
    control = str(uuid4())
    directory = tmp_path/control
    config = dict(directory=str(tmp_path/'state'), template=dict(publication_directory=str(tmp_path/'publication')),
                  inputs=dict(public_facts={}, supplement_facts=dict(targets=[])))
    class Publisher:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            original = json.loads((directory/'diagnostic.json').read_bytes())
            assert original['failure']['errno'] == errno.ENOSPC
            raise PermissionError(errno.EACCES, 'private publisher cleanup')
    monkeypatch.setattr(daily, '_load', lambda _descriptor: config)
    monkeypatch.setattr(daily, 'validate_configuration', lambda value: value)
    monkeypatch.setattr(daily, 'GenerationPublisher', lambda _path: Publisher())
    save = daily._save
    def publish(path, value):
        if path.name == 'ready.json':
            raise OSError(errno.ENOSPC, 'private first write error')
        return save(path, value)
    monkeypatch.setattr(daily, '_save', publish)
    with pytest.raises(PermissionError):
        daily.serve(dict(path=str(tmp_path/'config.json'), sha256='a'*64), directory, control, once=True)
    value = json.loads((directory/'diagnostic.json').read_bytes())
    assert value['failure']['errno'] == errno.ENOSPC
    assert [(row['phase'], row['errno']) for row in value['cleanup_errors']] == [('data_resources_close', errno.EACCES)]
