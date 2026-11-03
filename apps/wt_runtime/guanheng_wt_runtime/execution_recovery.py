"""故障恢复的发行身份交接；券商查询和金融状态加载归原执行 owner。"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import time

from .managed_local_process import _inspect, _json, _read, _require, _sha


def canonical(value):
    """与原绑定和用户状态相同的规范 ASCII 编码。"""
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def require_process_exited(pid):
    """只核Windows原PID已不存在或句柄已退出；拒绝活PID、拒绝访问及未知结果。"""
    import ctypes
    from .strategy_job import ProcessJob
    _require(type(pid) is int and 0 < pid <= 0xffffffff)
    api = ProcessJob().api  # 仅声明原Win32接口，构造不分配Job或进程。
    handle = api.OpenProcess(0x100000, False, pid)
    if not handle:
        _require(ctypes.get_last_error() == 87)  # ERROR_INVALID_PARAMETER：原PID不存在。
        return
    try:
        _require(api.WaitForSingleObject(handle, 0) == 0)
    finally:
        _require(bool(api.CloseHandle(handle)))


def record_execution_process_loss(control, *, expected=None):
    """执行恢复owner核原件和物理退出，记录故障事实；关闭/退出码保持未知。"""
    from uuid import UUID
    control = Path(control)
    _require(control.is_absolute())
    _inspect(control, directory=True)
    raw = _read(control / 'ready.json', 4096)
    ready = _json(raw)
    _require(ready['schema'] == 'guanheng.execution.ready.v1'
             and str(UUID(ready['control_id'])) == control.name
             and hashlib.sha256(_read(control / 'execution.json', 256 * 1024)).hexdigest()
             == _sha(ready['config_sha256']))
    _require(not any((control / name).exists() for name in ('closed.json', 'close-prepared.json', 'failure.json')))
    require_process_exited(ready['pid'])
    identity = {name: ready[name] for name in ('control_id', 'config_sha256', 'pid')}
    if expected is not None:
        _require(type(expected) is dict and expected == identity)
    path = control / 'owner-loss.json'
    if path.exists():
        value = _json(_read(path, 4096))
        _require(all(value.get(k) == v for k, v in identity.items())
                 and value.get('schema') == 'guanheng.execution.owner-loss.v1'
                 and value.get('reason') == 'process_lost'
                 and value.get('ready_sha256') == hashlib.sha256(raw).hexdigest())
        return value
    value = dict(
        schema='guanheng.execution.owner-loss.v1',  # 原进程物理退出故障，未授正常关闭。
        **identity,  # 原control/config/PID，全部来自已校验原ready及配置字节。
        ready_sha256=hashlib.sha256(raw).hexdigest(),  # 原ready字节身份，供Native重核。
        reason='process_lost',  # 固定故障类别；退出码和原join结果仍未知。
        observed_at=datetime.now(timezone.utc).isoformat(),  # 本次核查UTC时间，不冒充来源时点。
        observer_pid=os.getpid())  # 执行核查owner的PID，与原执行PID分别保存。
    with path.open('xb') as stream:
        stream.write(canonical(value))
    return value


def _normalized(binding):
    site = Path(binding['site_root'])
    prefix = Path(binding['python']).parent.parent
    result = {}
    for name, value in binding['files']:
        path = Path(name)
        key = ('site/' + path.relative_to(site).as_posix() if path.is_relative_to(site)
               else 'venv/' + path.relative_to(prefix).as_posix() if path.is_relative_to(prefix)
               else str(path))
        _require(key not in result)
        result[key] = _sha(value)
    return result


def load_transition(native, identities=None, *, binding=None, deadline=float('inf')):
    """核固定前后代身份及原证据；返回前代代码身份，不修改原 KV。"""
    selection = native['recovery']
    _require(selection['mode'] == 'resume_reconciled')
    reference = selection['transition']
    _require(type(reference) is dict and set(reference) == {'file', 'sha256'})
    path = Path(reference['file']); _require(path.is_absolute())
    raw = _read(path, 1024 * 1024, deadline=deadline)
    _require(hashlib.sha256(raw).hexdigest() == _sha(reference['sha256']))
    value = _json(raw)
    _require(set(value) == {'schema', 'predecessor_configuration', 'predecessor_configuration_sha256',
        'predecessor_control_directory', 'predecessor_installation_sha256', 'successor_installation_sha256',
        'predecessor_python_binding_sha256', 'successor_python_code_identity', 'state_files'}
        and value['schema'] == 'guanheng.execution-recovery-transition.v1')
    previous = Path(value['predecessor_control_directory']); _inspect(previous, directory=True)
    old_raw = _read(previous / 'python-binding.json', 256 * 1024, deadline=deadline)
    _require(hashlib.sha256(old_raw).hexdigest() == _sha(value['predecessor_python_binding_sha256']))
    old = _json(old_raw)
    _require(old['schema'] == 'guanheng.cta-python-binding.v1')
    if identities is not None:
        _require(binding is not None and digest(identities) == value['successor_python_code_identity'])
        before, after = _normalized(old), _normalized(binding)
        for key in before.keys() | after.keys():
            if before.get(key) != after.get(key):
                # 发行仅交接自有运行适配；策略核/NSQ/模型与解释器身份保持原值。
                _require(key.startswith('site/guanheng_wt_runtime/')
                    or key.startswith('site/guanheng_wt_runtime-') and key.endswith('.dist-info/METADATA')
                    or key == 'venv/pyvenv.cfg')
    return value, digest(dict(old['files']))


def prior_strategy_observations(native, strategy_id, *, deadline):
    """沿已绑定的原恢复链读取原件；只提供旧观察与原摘要，不授估值/现金资格。

    消费方核当前账、数量和周期。每一跳先核原配置SHA及相同业务配置，最多16跳；
    缺原件或链冲突由调用者保留资金未知，原金融状态与恢复准入保持独立。
    """
    current, visited = native, set()
    for unused in range(16):
        _require(time.monotonic() < deadline)
        if current.get('recovery', {}).get('mode') != 'resume_reconciled':
            return
        transition, unused_identity = load_transition(current, deadline=deadline)
        previous = Path(transition['predecessor_control_directory'])
        _require(previous not in visited)
        visited.add(previous)
        path = Path(transition['predecessor_configuration'])
        _require(path == previous / 'execution.json')
        raw = _read(path, 256 * 1024, deadline=deadline)
        _require(hashlib.sha256(raw).hexdigest() == transition['predecessor_configuration_sha256'])
        prior = _json(raw)
        before, after = dict(prior), dict(current)
        before.pop('recovery', None); after.pop('recovery', None)
        _require(before == after)
        ready = _json(_read(previous / 'ready.json', 4096, deadline=deadline))
        body = _read(previous / 'strategies.json', 1024 * 1024, deadline=deadline)
        report = _json(body)
        _require(report['control_id'] == ready['control_id'] and report['pid'] == ready['pid']
            and report['config_sha256'] == ready['config_sha256'] == hashlib.sha256(raw).hexdigest())
        observation = report['strategies'].get(strategy_id)
        if type(observation) is dict:
            yield observation, dict(path=str(previous / 'strategies.json'),
                sha256=hashlib.sha256(body).hexdigest(), control_id=ready['control_id'])
        current = prior


def prepare_transition(configuration, predecessor_configuration, predecessor_control, destination, *, successor_python=None):
    """冻结发行交接材料；只读取上代状态，实际准入由持有租约的 Native 再核。"""
    from .execution_process import PythonExecutionProcessConfig
    configuration, predecessor_configuration, predecessor_control, destination = map(
        Path, (configuration, predecessor_configuration, predecessor_control, destination))
    native = _json(_read(configuration, 256 * 1024))
    old_raw = _read(predecessor_configuration, 256 * 1024)
    old = _json(old_raw)
    root = Path(native['output_directory'])
    _require(root == Path(old['output_directory']))
    current = PythonExecutionProcessConfig.load(Path(native['installation_root']).parent,
        configuration, predecessor_control.parent)
    identities = dict(current.python_files)
    if successor_python is not None:
        import sys
        interpreter = Path(successor_python)
        # 部署解释器是发行身份的一部分；材料生成CLI与无窗口owner可使用不同入口。
        _require(interpreter.parent == current.pythonw.parent and interpreter.name.lower() in ('python.exe', 'pythonw.exe'))
        identities.pop(str(current.pythonw))
        identities[str(interpreter)] = hashlib.sha256(_read(interpreter, 32 * 1024 * 1024)).hexdigest()
        base = Path(sys._base_executable)
        identities.pop(str(base))
        successor_base = base.with_name(interpreter.name)
        identities[str(successor_base)] = hashlib.sha256(_read(successor_base, 32 * 1024 * 1024)).hexdigest()
    binding = _read(predecessor_control / 'python-binding.json', 256 * 1024)
    if (root / '.cta-clean.json').exists():
        origin = _json(_read(root / '.cta-clean.json', 256 * 1024))
        old_installation = origin['installation_sha256']
    elif (predecessor_control / 'installation-identity.json').exists():
        origin = _json(_read(predecessor_control / 'installation-identity.json', 4096))
        old_installation = origin['installation_sha256']
    elif (predecessor_control / 'reconciled.json').exists():
        origin = _json(_read(predecessor_control / 'reconciled.json', 256 * 1024))
        old_installation = origin['successor_installation_sha256']
    else:
        origin = _json(_read(root / '.cta-clean.consumed.json', 256 * 1024))
        old_installation = origin['installation_sha256']
    manifest = _json(_read(current.installation / 'execution-install.json', 256 * 1024))
    files = {}
    for directory in ('stradata', 'userdata', 'portfolio'):
        folder = root / directory
        if not folder.exists():
            continue
        _inspect(folder, directory=True)
        for path in sorted(folder.iterdir()):
            _inspect(path)
            if path.suffix.lower() == '.json':
                files[path.relative_to(root).as_posix()] = hashlib.sha256(_read(path, 4 * 1024 * 1024)).hexdigest()
    _require(files and len(files) <= 1536)
    value = dict(
        schema='guanheng.execution-recovery-transition.v1',  # 固定发行交接协议；不代表上次正常退出。
        predecessor_configuration=str(predecessor_configuration),  # 前代实际Native配置的绝对路径。
        predecessor_configuration_sha256=hashlib.sha256(old_raw).hexdigest(),  # 前代原配置字节摘要。
        predecessor_control_directory=str(predecessor_control),  # 原ready/关闭或故障收据所在目录。
        predecessor_installation_sha256=old_installation,  # 原owner保存的完整安装清单摘要。
        successor_installation_sha256=digest(manifest['files']),  # 本代完整安装清单摘要。
        predecessor_python_binding_sha256=hashlib.sha256(binding).hexdigest(),  # 原Python绑定文件字节摘要。
        successor_python_code_identity=digest(identities),  # 实际部署解释器与源码集合的规范身份。
        state_files=files)  # 原金融JSON相对路径到字节摘要；仅作准入证据，不生成账本。
    raw = canonical(value)
    with destination.open('xb') as stream:
        stream.write(raw)
    return dict(file=str(destination), sha256=hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='冻结自有执行故障恢复发行交接材料；不启动或修改金融状态')
    for name in ('configuration', 'predecessor-configuration', 'predecessor-control', 'destination'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--successor-python', type=Path, required=True, help='正式owner实际使用的解释器入口')
    args = parser.parse_args()
    print(json.dumps(prepare_transition(args.configuration, args.predecessor_configuration,
        args.predecessor_control, args.destination, successor_python=args.successor_python)))
