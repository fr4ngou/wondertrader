"""已安装App的独立观察调度入口；父Job拥有阻塞调用的硬回收。"""
import argparse
from datetime import datetime,timezone
import importlib
import math
import os
from pathlib import Path
import threading
import time
from uuid import UUID,uuid4
from guanheng_app.managed_local_process import _require,_path,_sha,_read,_json,_inspect
from guanheng_app.thread_owner import ThreadOwner
from guanheng_app.observation_process import load_service_configuration
from guanheng_app.observation.collection_config import load_configuration
from guanheng_app.observation.runtime import build_reader,market_client_factory
from guanheng_app.observation.scheduler import run
from guanheng_app.observation.storage import encode
from guanheng_app.observation.contracts import ObservationError


class StopController:
    """只监视父发布的有限停止收据；信号、首D和实际join分别保留。"""
    def __init__(self,directory,identity):
        self.directory,self.identity=directory,identity
        self.event,self.done=threading.Event(),threading.Event()
        self.lock=threading.Lock();self.deadline=None;self.error=None
        self.monitor=ThreadOwner(target=self._watch,name='observation-stop-monitor',daemon=False)

    def _watch(self):
        while not self.done.wait(.05):
            try:
                value=_json(_read(self.directory/'stop.json',4096))
                _require(set(value)=={'schema','control_id','deadline'} and value['schema']=='guanheng.observation-stop.v1'
                    and value['control_id']==self.identity and type(value['deadline']) in (int,float) and math.isfinite(value['deadline']))
                with self.lock:
                    self.deadline=min(self.deadline,value['deadline']) if self.deadline is not None else value['deadline']
                self.event.set();return
            except OSError as exc:
                if isinstance(exc,FileNotFoundError) or getattr(exc,'winerror',None) in (32,33):continue
                self.error='stop_control';self.event.set();return
            except BaseException:
                self.error='stop_control';self.event.set();return

    def is_set(self):return self.event.is_set()
    def wait(self,seconds):return self.event.wait(seconds)

    def close(self):
        self.done.set()
        with self.lock:deadline=self.deadline if self.deadline is not None else time.monotonic()+2
        return self.monitor.join_until(deadline)


def _failure_metadata(error,stage):
    """仅保存有限异常身份与代码位置；正文、路径、配置和来源响应不进入诊断。"""
    chain=[];seen=set();remaining_frames=4
    def code(value):return value if type(value) is int and 0<=value<=0xffffffff else None
    while error is not None and id(error) not in seen and len(chain)<3:
        seen.add(id(error));frames=[];frame=error.__traceback__
        while frame is not None:
            module=frame.tb_frame.f_globals.get('__name__','')
            if module.startswith('guanheng_app.'):
                frames.append(dict(module=module[:96],function=frame.tb_frame.f_code.co_name[:64],line=frame.tb_lineno))
                frames=frames[-4:]
            frame=frame.tb_next
        frames=frames[-remaining_frames:] if remaining_frames else []
        remaining_frames-=len(frames)
        chain.append(dict(error_type=type(error).__name__[:64],
            errno=code(getattr(error,'errno',None)) if isinstance(error,OSError) else None,
            winerror=code(getattr(error,'winerror',None)) if isinstance(error,OSError) else None,frames=frames))
        error=error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return dict(stage=stage,observed_at=datetime.now(timezone.utc).isoformat(),exceptions=chain)


def serve(configuration,expected_sha256,directory,control_id,*,now=lambda:datetime.now(timezone.utc)):
    """主线程独占调度/采集；now仅为可注入时钟，正式CLI固定系统UTC。"""
    _require(str(UUID(control_id))==control_id and directory.name==control_id)
    _sha(expected_sha256);stop=None;created=False;error=None;joined=False;stage='configuration';diagnostic=None
    def publish(name,value):
        raw=encode(value);_require(0<len(raw)<=4096)
        temporary=directory/(name+'-'+str(uuid4())+'.tmp')
        with temporary.open('xb') as stream:
            _require(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno())
        _inspect(temporary);os.rename(temporary,directory/name)
    try:
        value=load_service_configuration(configuration,expected_sha256)
        config=load_configuration(value['sources_file'],value['sources_sha256'])
        importlib.import_module('httpx')
        if any(s['kind'] in ('baostock','ashare_public') for s in config['sources']):importlib.import_module('baostock')
        reader=build_reader(value['root'])
        # control_root由维护人员提供受保护父目录，新实例继承同一ACL；正文不含凭据。
        _inspect(directory.parent,directory=True);directory.mkdir();created=True
        stop=StopController(directory,control_id);stop.monitor.start()
        def ready():
            publish('ready.json',dict(schema='guanheng.observation-ready.v1',control_id=control_id,pid=os.getpid(),
                configuration_sha256=expected_sha256,scheduler_ready=True))
        stage='scheduler'
        run(reader,config,stop,now=now,on_ready=ready,market_client_factory=market_client_factory())
        if stop.error or stop.deadline is None:error=stop.error or 'stop_missing'
    except ObservationError as exc:
        error=exc.code;diagnostic=_failure_metadata(exc,stage)
    except BaseException as exc:
        error=stage;diagnostic=_failure_metadata(exc,stage)
    finally:
        if stop is not None:
            joined=stop.close()
            if not joined or stop.deadline is not None and time.monotonic()>=stop.deadline:error=error or 'close'
        if created:
            identity=dict(control_id=control_id,pid=os.getpid(),configuration_sha256=expected_sha256)
            if error is not None and diagnostic is None:
                diagnostic=_failure_metadata(None,'shutdown')
            if diagnostic is not None:
                try:
                    publish('diagnostic.json',dict(schema='guanheng.observation-diagnostic.v1',**identity,**diagnostic))
                except BaseException:
                    # 诊断发布失败保留原失败结果，不能把未知关闭改成成功。
                    pass
            if error is None and joined:
                publish('closed.json',dict(schema='guanheng.observation-closed.v1',status='stopped',
                    scheduler_closed=True,monitor_joined=True,error_code=None,**identity))
            else:
                publish('failure.json',dict(schema='guanheng.observation-failure.v1',error_code=error or 'close',**identity))
    return 0 if error is None and joined else 1


def main():
    parser=argparse.ArgumentParser(description='观衡独立观察调度进程')
    parser.add_argument('--config',required=True);parser.add_argument('--config-sha256',required=True)
    parser.add_argument('--control-directory',required=True);parser.add_argument('--control-id',required=True)
    args=parser.parse_args()
    return serve(args.config,args.config_sha256,_path(args.control_directory),args.control_id)


if __name__=='__main__':raise SystemExit(main())
