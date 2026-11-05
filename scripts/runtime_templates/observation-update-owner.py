"""Local maintenance commands for the installed, original observation supervisor.

This command exits after maintenance; it does not own a scheduling loop or kill
processes. The installed supervisor retains the original child/Job lifecycle.
"""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid

BASE = Path(__file__).resolve().parent
MARKET_ENVIRONMENT_KEYS = frozenset((
    'GUANHENG_MARKET_URL', 'GUANHENG_MARKET_TOKEN',
    'GUANHENG_MARKET_CONNECT_IP', 'GUANHENG_MARKET_TIMEOUT_SECONDS',
    'NO_PROXY',  # 仅该独立更新角色的显式直连主机名单，其他来源继续继承原代理。
))


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def read(path, maximum=16384):
    with path.open('rb') as stream:
        raw=stream.read(maximum+1)
    require(len(raw)<=maximum,'control_input_capacity')
    value=json.loads(raw,parse_constant=lambda _:require(False,'control_nonfinite_number'))
    require(type(value) is dict,'control_object_required')
    return value


def launch_environment(prepared, profile):
    """独立更新角色只加载显式绑定的行情凭据，保持账户及执行环境隔离。

    profile可选market_environment={path,sha256}，绑定外部私有JSON，最多16KiB。
    缺省保留原清理行为。验证在创建运行身份前完成；停止和状态不依赖凭据。
    返回新环境，不修改调用进程环境，不把凭据写入控制收据或日志。
    """
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith('GUANHENG_')}
    binding = prepared['profiles'][profile].get('market_environment')
    if binding is None:
        return environment
    require(type(binding) is dict and set(binding) == {'path', 'sha256'}, 'market_environment_binding')
    require(type(binding['path']) is str and Path(binding['path']).is_absolute(), 'market_environment_path')
    require(type(binding['sha256']) is str and len(binding['sha256']) == 64, 'market_environment_digest')
    try:
        with Path(binding['path']).open('rb') as stream:
            raw = stream.read(16385)
    except OSError:
        raise RuntimeError('market_environment_unavailable') from None
    require(len(raw) <= 16384 and hashlib.sha256(raw).hexdigest() == binding['sha256'],
            'market_environment_identity')
    try:
        values = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RuntimeError('market_environment_invalid') from None
    require(type(values) is dict and set(values) <= MARKET_ENVIRONMENT_KEYS
            and all(type(value) is str and '\x00' not in value for value in values.values()),
            'market_environment_fields')
    require(all(values.get(key, '').strip() for key in ('GUANHENG_MARKET_URL', 'GUANHENG_MARKET_TOKEN')),
            'market_environment_connection_required')
    environment.update(values)
    return environment


def identity(value):
    require(type(value) is str,'control_uuid_type')
    require(str(uuid.UUID(value))==value,'control_uuid_invalid')
    return value


def positive_integer(value):
    require(type(value) is int and value>0,'control_integer_invalid')


def instance_record(value, prepared, profile):
    required={'schema','profile','control_id','control_directory','deployment_sha256'}
    optional={'pid','process_creation_time','supervisor_pid','supervisor_creation_time','child_creation_time','supervisor_exit_code'}
    require(required<=value.keys() and value.keys()<=required|optional,'instance_fields_invalid')
    require(value['schema']=='oar.observation-supervisor-instance.v1' and value['profile']==profile,'instance_schema_or_profile')
    control_id=identity(value['control_id'])
    require(value['control_directory']==str(BASE/'supervisors'/control_id),'instance_directory_invalid')
    require(value['deployment_sha256']==prepared['profiles'][profile]['deployment_sha256'],'instance_configuration_mismatch')
    for pair in (('pid','process_creation_time'),('supervisor_pid','supervisor_creation_time')):
        require(all(key in value for key in pair) or all(key not in value for key in pair),'instance_identity_pair')
        for key in pair:
            if key in value:positive_integer(value[key])
    if 'child_creation_time' in value and value['child_creation_time'] is not None:positive_integer(value['child_creation_time'])
    if 'supervisor_exit_code' in value:require(type(value['supervisor_exit_code']) is int and 0<=value['supervisor_exit_code']<2**32,'instance_exit_code_invalid')
    return {key:value[key] for key in required|optional if key in value}


def receipt_record(value, state, prepared, profile, name, *, child=None):
    common={'schema','control_id','pid','configuration_sha256'}
    if child is None:
        additional={'child_control_id','child_pid'} if name=='ready' else {'scheduler_closed','monitor_joined','startup_joined','publication_deadline','error_code'}
        schema='guanheng.observation-supervisor-'+name+'.v1'
        expected_id=state['control_id'];expected_sha=state['deployment_sha256']
    else:
        additional={'scheduler_ready'} if name=='ready' else {'status','scheduler_closed','monitor_joined','error_code'} if name=='closed' else {'error_code'}
        schema='guanheng.observation-'+name+'.v1'
        expected_id=child['child_control_id'];expected_sha=prepared['profiles'][profile]['service_sha256']
    require(set(value)==common|additional,'receipt_fields_invalid')
    require(value['schema']==schema and identity(value['control_id'])==expected_id,'receipt_schema_or_identity')
    require(value['configuration_sha256']==expected_sha,'receipt_configuration_mismatch')
    positive_integer(value['pid'])
    if child is not None:require(value['pid']==child['child_pid'],'child_pid_mismatch')
    for key in ('scheduler_ready','scheduler_closed','monitor_joined','startup_joined'):
        if key in value:require(type(value[key]) is bool,'receipt_boolean_invalid')
    if 'child_pid' in value:
        positive_integer(value['child_pid']);identity(value['child_control_id'])
    if 'publication_deadline' in value:
        import math
        deadline=value['publication_deadline']
        require(type(deadline) in (int,float) and math.isfinite(deadline) and deadline>0,'receipt_deadline_invalid')
    if 'status' in value:require(value['status']=='stopped','receipt_status_invalid')
    if 'error_code' in value:
        code=value['error_code']
        require(code is None or type(code) is str and len(code)<=100 and code.replace('_','').isalnum(),'receipt_error_invalid')
        value=dict(value,error_code=None if code is None else 'owner_reported_failure')
    return {key:value[key] for key in common|additional}


def write(path, value):
    temporary = path.with_name(path.name + '.' + str(uuid.uuid4()) + '.tmp')
    with temporary.open('xb') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True).encode())
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class ProcessHandle:
    """Hold the matching process object across stop to retain its actual OS exit."""
    def __init__(self,pid):
        self.pid=pid;self.handle=None
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        self.kernel.OpenProcess.restype=wintypes.HANDLE
        self.kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
        self.kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]

    def __enter__(self):
        self.handle=self.kernel.OpenProcess(0x1000,False,self.pid)
        if not self.handle and ctypes.get_last_error()!=87:
            raise OSError(ctypes.get_last_error(),'process_identity_unavailable')
        return self

    def snapshot(self):
        if not self.handle:return None
        times = [wintypes.FILETIME() for _ in range(4)]
        code = wintypes.DWORD()
        if not self.kernel.GetProcessTimes(self.handle, *[ctypes.byref(x) for x in times]):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.kernel.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return dict(creation_time=(times[0].dwHighDateTime << 32)|times[0].dwLowDateTime,exit_code=code.value)

    def __exit__(self,*_):
        if self.handle:self.kernel.CloseHandle(self.handle)


def process_identity(pid):
    with ProcessHandle(pid) as process:
        state=process.snapshot()
        return state['creation_time'] if state and state['exit_code']==259 else None


def parent_pid(pid):
    class BasicInformation(ctypes.Structure):
        _fields_ = [('reserved1', ctypes.c_void_p), ('peb', ctypes.c_void_p),
                    ('reserved2', ctypes.c_void_p * 2), ('pid', ctypes.c_size_t), ('parent', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    query = ctypes.WinDLL('ntdll').NtQueryInformationProcess
    query.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.c_void_p]
    query.restype = wintypes.LONG
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        basic = BasicInformation()
        if query(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic), None) != 0:
            raise RuntimeError('supervisor ancestry unavailable; retain original launch identity')
        return basic.parent
    finally:
        kernel.CloseHandle(handle)


@contextlib.contextmanager
def exclusive(profile):
    with (BASE / ('control-' + profile + '.lock')).open('a+b') as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def control_status(prepared, profile):
    state_path = BASE / ('instance-' + profile + '.json')
    state = instance_record(read(state_path),prepared,profile) if state_path.exists() else None
    result = dict(profile=profile, instance=state, alive=False, launcher_alive=False, receipts={})
    if state:
        if 'pid' not in state:
            raise RuntimeError('launch identity unresolved; inspect the recorded control directory before recovery')
        launcher_alive = process_identity(state['pid']) == state['process_creation_time']
        result['launcher_alive']=launcher_alive
        result['alive'] = launcher_alive
        directory = Path(state['control_directory'])
        for name in ('ready', 'closed', 'failure'):
            path = directory / (name + '.json')
            if path.exists():
                receipt = receipt_record(read(path),state,prepared,profile,name)
                if 'supervisor_pid' not in state:
                    require(launcher_alive and parent_pid(receipt['pid']) == state['pid'],'supervisor_ancestry_invalid')
                    state['supervisor_pid'] = receipt['pid']
                    state['supervisor_creation_time'] = process_identity(receipt['pid'])
                    require(state['supervisor_creation_time'] is not None,'supervisor_identity_unknown')
                    write(state_path, state)
                    write(BASE / 'receipts' / (state['control_id'] + '.instance.json'), state)
                require(receipt['pid'] == state['supervisor_pid'],'supervisor_pid_mismatch')
                result['receipts'][name] = receipt
        if 'supervisor_pid' in state:
            result['alive'] = process_identity(state['supervisor_pid']) == state['supervisor_creation_time']
        ready = result['receipts'].get('ready')
        if ready:
            child = BASE / 'children' / ready['child_control_id']
            if 'child_creation_time' not in state:
                state['child_creation_time'] = process_identity(ready['child_pid'])
                write(state_path, state)
                write(BASE / 'receipts' / (state['control_id'] + '.instance.json'), state)
            result['child_alive'] = state['child_creation_time'] is not None and process_identity(ready['child_pid']) == state['child_creation_time']
            for name in ('ready', 'closed', 'failure'):
                path = child / (name + '.json')
                if path.exists():
                    receipt = receipt_record(read(path),state,prepared,profile,name,child=ready)
                    result['receipts']['child_' + name] = receipt
    return result


def business_status(prepared,profile):
    result={}
    root = Path(prepared['profiles'][profile]['root'])
    from guanheng_app.observation.storage import SnapshotRepository
    try:
        deadline=time.monotonic()+2
        with sqlite3.connect((root / 'catalog.sqlite3').as_uri() + '?mode=ro', uri=True, timeout=.25) as db:
            db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
            result['current'] = db.execute('SELECT version FROM current WHERE id=1').fetchone()[0]
            result['completed_windows'] = db.execute('SELECT * FROM completed_windows ORDER BY rowid DESC LIMIT 100').fetchall()
            result['attempts'] = db.execute('SELECT * FROM window_attempts ORDER BY rowid DESC LIMIT 100').fetchall()
            result['runs_count'] = db.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
            result['history_page_limit']=100
    except Exception:
        result={'business_error':'catalog_query_unavailable'}
    try:
        value=SnapshotRepository(root).scheduler_status()
        result['scheduler']={key:value.get(key) for key in ('enabled','state','phase','last_heartbeat','schedule')}
    except Exception:
        result['scheduler_error']='scheduler_query_unavailable'
    return result


def status(prepared,profile):
    return dict(control_status(prepared,profile),**business_status(prepared,profile))


def start(prepared, profile, seconds):
    before = control_status(prepared, profile)
    if before['alive'] or before['launcher_alive']:
        raise RuntimeError('recorded supervisor is already running; use status or stop')
    if before.get('child_alive'):
        raise RuntimeError('recorded child remains running; inspect its original owner before recovery')
    if before['instance'] and not ('closed' in before['receipts'] or 'failure' in before['receipts']):
        raise RuntimeError('prior exit has no terminal receipt; inspect original window/current before recovery')
    if profile == 'live' and before['instance'] is None:
        require(business_status(prepared,profile).get('current') == prepared['expected_current'],'initial_current_changed_or_unavailable')
    configured = prepared['profiles'][profile]
    for kind in ('sources', 'service', 'deployment'):
        require(hashlib.sha256(Path(configured[kind]).read_bytes()).hexdigest() == configured[kind + '_sha256'],'fixed_configuration_changed')
    environment = launch_environment(prepared, profile)
    identity = str(uuid.uuid4())
    directory = BASE / 'supervisors' / identity
    state = dict(schema='oar.observation-supervisor-instance.v1', profile=profile,
                 control_id=identity, control_directory=str(directory),
                 deployment_sha256=configured['deployment_sha256'])
    state_path = BASE / ('instance-' + profile + '.json')
    write(state_path, state)
    command = [prepared['pythonw'], '-I', '-B', '-m', 'guanheng_app.observation_supervisor',
               '--deployment', configured['deployment'], '--deployment-sha256', configured['deployment_sha256'],
               '--control-directory', str(directory), '--control-id', identity]
    if seconds is not None:
        command += ['--seconds', str(seconds)]
    with (BASE / 'receipts' / (identity + '.stdout')).open('xb') as out, (BASE / 'receipts' / (identity + '.stderr')).open('xb') as err:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                   cwd=BASE, env=environment, creationflags=subprocess.CREATE_NO_WINDOW,
                                   close_fds=True)
    state.update(pid=process.pid, process_creation_time=process_identity(process.pid))
    require(state['process_creation_time'] is not None,'startup_identity_unknown_retain_control_id')
    write(state_path, state)
    write(BASE / 'receipts' / (identity + '.instance.json'), state)
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        result = control_status(prepared, profile)
        if 'ready' in result['receipts'] or not result['alive']:
            return result
        time.sleep(.2)
    return control_status(prepared, profile)


def stop(prepared, profile):
    deadline=time.monotonic()+22
    before = control_status(prepared, profile)
    state=before['instance']
    if not state or 'supervisor_pid' not in state:
        return dict(before,stop_deadline_met=time.monotonic()<deadline)
    existing=Path(state['control_directory'])/'stop.json'
    if existing.exists():
        value=read(existing)
        import math
        require(set(value)=={'schema','control_id','deadline'} and value['schema']=='guanheng.observation-stop.v1'
                and value['control_id']==state['control_id'],'existing_stop_identity_invalid')
        require(type(value['deadline']) in (int,float) and math.isfinite(value['deadline']) and value['deadline']>0,'existing_stop_deadline_invalid')
        deadline=min(deadline,value['deadline']+2)
    if time.monotonic()>=deadline:return dict(before,stop_deadline_met=False)
    with ProcessHandle(state['supervisor_pid']) as observer:
        observed=observer.snapshot()
        if observed is None:return dict(before,stop_deadline_met=time.monotonic()<deadline)
        require(observed['creation_time']==state['supervisor_creation_time'],'stop_process_identity_changed')
        result=_stop(prepared,profile,before,deadline) if before['alive'] else before
        observed=observer.snapshot()
        if observed and observed['exit_code']!=259:
            state=result['instance'];state['supervisor_exit_code']=observed['exit_code']
            write(BASE/('instance-'+profile+'.json'),state)
            write(BASE/'receipts'/(state['control_id']+'.instance.json'),state)
    result['stop_deadline_met']=time.monotonic()<deadline
    return result


def _stop(prepared,profile,before,deadline):
    state=before['instance']
    path = Path(state['control_directory']) / 'stop.json'
    if not path.exists():
        require(time.monotonic()<deadline-2,'stop_deadline_expired')
        value = dict(schema='guanheng.observation-stop.v1', control_id=state['control_id'], deadline=deadline-2)
        temporary = path.with_name('stop-' + str(uuid.uuid4()) + '.tmp')
        with temporary.open('xb') as stream:
            stream.write(json.dumps(value).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(temporary, path)
    while time.monotonic() < deadline:
        result = control_status(prepared, profile)
        if not result['alive'] and not result['launcher_alive'] and not result.get('child_alive'):
            return result
        time.sleep(.2)
    return control_status(prepared, profile)


def action_outcome(action,result):
    if action=='status':return 'observed'
    receipts=result['receipts']
    if 'failure' in receipts or 'child_failure' in receipts:return 'failed'
    if action=='start':
        return 'ready' if result['alive'] and result.get('child_alive') and 'ready' in receipts and receipts.get('child_ready',{}).get('scheduler_ready') is True else 'unknown'
    parent=receipts.get('closed',{});child=receipts.get('child_closed',{})
    closed=not result['alive'] and not result['launcher_alive'] and not result.get('child_alive')
    joined=all(parent.get(key) is True for key in ('scheduler_closed','monitor_joined','startup_joined')) and all(child.get(key) is True for key in ('scheduler_closed','monitor_joined'))
    code=(result.get('instance') or {}).get('supervisor_exit_code')
    if code is not None and code!=0:return 'failed'
    return 'closed' if result.get('stop_deadline_met') is True and closed and joined and code==0 and parent.get('error_code') is None and child.get('error_code') is None else 'unknown'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'status', 'stop'))
    parser.add_argument('--profile', choices=('validation', 'live'), default='live')
    parser.add_argument('--seconds', type=float)
    args = parser.parse_args()
    if args.seconds is not None and (args.action != 'start' or args.profile != 'validation' or not 45 <= args.seconds <= 3600):
        parser.error('finite seconds is supported for validation start only, within 45..3600')
    prepared = read(BASE / 'PREPARED.json')
    require(Path(prepared['runtime_root']) == BASE,'runtime_root_mismatch')
    with exclusive(args.profile):
        result = start(prepared, args.profile, args.seconds) if args.action == 'start' else stop(prepared, args.profile) if args.action == 'stop' else status(prepared, args.profile)
    outcome=action_outcome(args.action,result);result['outcome']=outcome
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if outcome in ('observed','ready','closed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
