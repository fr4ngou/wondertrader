"""数据WT角色的薄启动适配；进程树、管道和关闭仍由原ManagedLocalProcess负责。"""
from dataclasses import dataclass
from pathlib import Path
import os
import time

from guanheng_wt_runtime.managed_local_process import ManagedLocalProcess, _inspect, _read, _json, _require
from guanheng_qmt_shm.private_files import create_private_directory, write_private_new
from guanheng_qmt_shm_agent.protocol import canonical
from .collection_deployment import load
from .market_generation import read_fixed


@dataclass(frozen=True)
class DataRoleConfig:
    pythonw: str  # 原独立WT角色的冻结解释器绝对路径。
    pythonw_sha256: str  # 原解释器字节身份，启动前复核。
    configuration: str  # 本次data-runtime配置绝对路径，持续状态仍在原Writer/Importer根。
    configuration_sha256: str  # 本次运行配置固定SHA。
    instance_id: str  # 原WRI实例身份，控制收据与停止命令均绑定。
    control_root: str  # 本次私有控制根，实际子代由原受管器分配UUID。
    startup_seconds: float  # 角色完整启动预算，秒。
    stop_seconds: float  # 外层关闭预算，覆盖子WRI原预算及进程/管道回收。
    max_output_bytes: int = 65536  # 原监督器合流输出额度，字节；不记录私有配置正文。


class DataRoleProcess(ManagedLocalProcess):
    """只组合原WRI命令与其四字段stop合同，继承唯一进程监督实现。"""
    _thread_name = 'minute-data-role'

    def _validate_inputs(self, deadline):
        cfg = self.config
        _inspect(Path(cfg.control_root), directory=True)
        self._verify_file(Path(cfg.pythonw), cfg.pythonw_sha256, 67108864, deadline)
        self._verify_file(Path(cfg.configuration), cfg.configuration_sha256, 1048576, deadline)
        _require(not self._directory.exists())

    def _command(self):
        cfg = self.config
        return (cfg.pythonw, '-I', '-B', '-m', 'guanheng_wt_runtime', '--config', cfg.configuration,
            '--config-sha256', cfg.configuration_sha256, '--control-directory', str(self._directory),
            '--control-id', self._control_id)

    def _receipt(self, name, deadline):
        value = _json(_read(self._directory / name, 65536, clock=self._clock, deadline=deadline))
        cfg = self.config
        _require(value['control_id'] == self._control_id and value['instance_id'] == cfg.instance_id
                 and value['configuration_sha256'] == cfg.configuration_sha256)
        ready = name == 'ready.json'
        _require(value['schema'] == 'guanheng.wt-runtime-' + ('ready' if ready else 'closed') + '.v1')
        if not ready:
            _require(value['components_closed'] is True and value['error_code'] is None
                     and value['pid'] == self._host_pid)
        return value

    def _publish_stop(self):
        if self._stop_written or self._host_pid is None:
            return
        value = dict(schema='guanheng.wt-runtime-stop.v1', control_id=self._control_id,
            instance_id=self.config.instance_id, configuration_sha256=self.config.configuration_sha256)
        target = self._directory / 'stop.json'
        if target.exists():
            _require(_json(_read(target, 4096)) == value)
        else:
            temporary = self._directory / 'minute-role-stop.tmp'
            write_private_new(temporary, canonical(value))
            os.rename(temporary, target)
        self._stop_written = True


def run_role(deployment, pythonw, pythonw_sha256, owner_root):
    """Root启动命令；同一原WRI管理整个数据角色，STOP.json请求正常停止。

    调用前Root完成原角色停止及完整Source采用；本函数不更改QMT、CURRENT或账户。
    owner_root须新建E盘目录。成功ready只表示原组件就绪，实际来源和数据另行验收。
    """
    plan = load(deployment)
    runtime = load(plan['files']['runtime'])
    root = Path(owner_root)
    _require(root.is_absolute() and root.resolve().drive.upper() == 'E:' and not root.exists())
    create_private_directory(root)
    environment = load(plan['files']['environment'])
    _require(all(type(k) is str and type(v) is str for k, v in environment.items()))
    os.environ.update(environment)
    del environment
    cfg = DataRoleConfig(pythonw, pythonw_sha256, plan['files']['runtime']['path'],
        plan['files']['runtime']['sha256'], runtime['instance_id'], str(root),
        runtime['startup_seconds'], runtime['stop_seconds'] + 30)
    process = DataRoleProcess(cfg)
    error = None
    try:
        _require(process.start(time.monotonic() + cfg.startup_seconds) is True)
        ready = dict(schema='qmt.minute-role-owner-ready.v1', pid=os.getpid(),
            control_id=process._control_id, child_control_directory=str(process._directory),
            deployment=deployment, child=process.status())
        write_private_new(root / 'OWNER-READY.json', canonical(ready))
        while True:
            if (root / 'STOP.json').exists():
                value = load_stop(root / 'STOP.json')
                _require(value == dict(schema='qmt.minute-role-stop.v1', control_id=process._control_id, pid=os.getpid()))
                break
            status = process.status()
            if status['state'] != 'ready':
                raise RuntimeError('data role stopped before requested close')
            time.sleep(.1)
    except BaseException as failure:
        error = type(failure).__name__
        raise
    finally:
        try:
            success = process.close(cfg.stop_seconds)
            closed = process.status()
            _require(success is True and closed['state'] == 'closed' and closed['error_code'] is None
                     and closed['forced'] is False and closed['pending'] is False)
            write_private_new(root / 'OWNER-CLOSED.json', canonical(dict(
                schema='qmt.minute-role-owner-closed.v1', control_id=process._control_id, pid=os.getpid(),
                components_closed=True, error_type=error, child=closed)))
        except BaseException:
            # 原受管器仍持有未确认owner；监督进程退出时原Job作最终收束。
            raise


def load_stop(path):
    from guanheng_qmt_shm_agent.protocol import decode
    return decode(read_fixed(path, maximum=4096))


def stop_role(owner_root):
    """只写所选owner的身份停止命令；正常退出证据由原监督进程发布。"""
    root = Path(owner_root)
    ready = load_stop(root / 'OWNER-READY.json')
    if (root / 'OWNER-CLOSED.json').exists():
        closed = load_stop(root / 'OWNER-CLOSED.json')
        _require(closed['control_id'] == ready['control_id'] and closed['components_closed'] is True)
        return dict(already_closed=True)
    target = root / 'STOP.json'
    value = dict(schema='qmt.minute-role-stop.v1', control_id=ready['control_id'], pid=ready['pid'])
    if target.exists():
        _require(load_stop(target) == value)
    else:
        write_private_new(target, canonical(value))
    return dict(stop_requested=True, control_id=ready['control_id'])
