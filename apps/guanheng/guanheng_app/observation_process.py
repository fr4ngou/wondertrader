"""独立观察调度薄适配；进程/首停止D/资源归原ManagedLocalProcess。"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import threading
import time
from .managed_local_process import ManagedLocalProcess,_require,_sha,_path,_read,_json,_inspect,_duration


def load_service_configuration(path,expected_sha256,deadline=None,*,clock=time.monotonic):
    kwargs=dict(clock=clock,deadline=deadline) if deadline is not None else {}
    raw=_read(_path(path),65536,**kwargs)
    _require(hashlib.sha256(raw).hexdigest()==_sha(expected_sha256))
    value=_json(raw)
    _require(set(value)=={'schema','root','sources_file','sources_sha256'}
        and value['schema']=='guanheng.observation-scheduler-service.v1')
    _path(value['root']);_path(value['sources_file']);_sha(value['sources_sha256'])
    return value


@dataclass(frozen=True)
class ObservationCollectionProcessConfig:
    """观察部署自身的有限合同；控制元数据盘符与来源数据根分属不同配置。"""
    pythonw: str
    pythonw_sha256: str
    entry: str
    entry_sha256: str
    configuration: str
    configuration_sha256: str
    control_root: str
    startup_seconds: float
    stop_seconds: float
    max_output_bytes: int

    def __post_init__(self):
        _path(self.pythonw);_sha(self.pythonw_sha256)
        _require(Path(self.pythonw).name.lower()=='pythonw.exe')
        _path(self.entry);_sha(self.entry_sha256)
        _path(self.configuration);_sha(self.configuration_sha256)
        _path(self.control_root)
        _duration(self.startup_seconds,120);_duration(self.stop_seconds,60)
        _require(type(self.max_output_bytes) is int and 1024<=self.max_output_bytes<=1048576)

    @classmethod
    def from_path(cls,path,expected_sha256=None):
        if path is None or path=='':
            _require(expected_sha256 in (None,''));return None
        raw=_read(_path(path),65536)
        _require(hashlib.sha256(raw).hexdigest()==_sha(expected_sha256))
        value=_json(raw)
        _require(set(value)==set(cls.__dataclass_fields__)|{'schema'}
            and value.pop('schema')=='guanheng.observation-process.v1')
        return cls(**value)


class ObservationCollectionProcess(ManagedLocalProcess):
    _status_schema='guanheng.observation-process-status.v1'
    _stop_schema='guanheng.observation-stop.v1'
    _thread_name='observation-process'

    def __init__(self,config=None,*,job_factory=None,thread_factory=threading.Thread,clock=time.monotonic):
        _require(config is None or type(config) is ObservationCollectionProcessConfig)
        super().__init__(config,job_factory=job_factory,thread_factory=thread_factory,clock=clock)

    def _validate_inputs(self,deadline):
        cfg=self.config
        _inspect(Path(cfg.control_root),directory=True)
        self._verify_file(Path(cfg.pythonw),cfg.pythonw_sha256,64*1024*1024,deadline)
        self._verify_file(Path(cfg.entry),cfg.entry_sha256,4*1024*1024,deadline)
        load_service_configuration(cfg.configuration,cfg.configuration_sha256,deadline,clock=self._clock)
        _require(not self._directory.exists());self._check(deadline)

    def _command(self):
        cfg=self.config
        return (cfg.pythonw,'-I','-B',cfg.entry,'--config',cfg.configuration,'--config-sha256',cfg.configuration_sha256,
            '--control-directory',str(self._directory),'--control-id',self._control_id)

    def _receipt(self,name,deadline):
        _inspect(self._directory,directory=True)
        value=_json(_read(self._directory/name,4096,clock=self._clock,deadline=deadline))
        ready=name=='ready.json'
        fields={'schema','control_id','pid','configuration_sha256'}
        fields |= {'scheduler_ready'} if ready else {'status','scheduler_closed','monitor_joined','error_code'}
        _require(set(value)==fields and value['schema']==('guanheng.observation-ready.v1' if ready else 'guanheng.observation-closed.v1')
            and value['control_id']==self._control_id and value['configuration_sha256']==self.config.configuration_sha256
            and type(value['pid']) is int and 0<value['pid']<2**32)
        if ready:_require(value['scheduler_ready'] is True)
        else:_require(value['pid']==self._host_pid and value['status']=='stopped' and value['scheduler_closed'] is True
            and value['monitor_joined'] is True and value['error_code'] is None)
        return value
