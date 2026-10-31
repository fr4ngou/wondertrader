"""NAP原帧的只读边界；账户金融投影继续归原account_projection。"""
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
from time import monotonic,sleep
from uuid import UUID

from guanheng_market_client.runtime_status import (CollectionStatusPending,read_status_snapshot,
    _open_status_file,_check as check_file,_identity)
from .managed_local_process import _inspect
from .account_scan import decode_json,_completion,FRAME_BYTES
from .account_projection import require,integer,text,validate_observation,project_account,unavailable_account
from .contracts.account import AccountClose,AccountOverviewV4,AccountPublication
from .wt_runtime_observation import read_runtime_snapshot

PUBLICATION_BYTES=FRAME_BYTES+65536
_FIELDS={'schema','control_id','config_sha256','pid','revision','updated_at','state','error_code',
         'last_success_at','binding','scan_id','observation','completion','close','attempt'}
_RESOURCES={'member_before_resume','tree_reaped','stdout_eof','stderr_eof','readers_joined','resources_closed'}


def check(deadline):
    if monotonic()>=deadline:raise TimeoutError('账户发布读取超过本次时间')


def stamp(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z',value))
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(result<=datetime.now(timezone.utc))
    return result


@dataclass(frozen=True,repr=False)
class ProjectionBinding:
    account:str
    environment:str
    max_rows:int
    ipc_schema:str
    inspection_version:int
    source:str
    read_profile_version:str

    @classmethod
    def from_value(cls,value):
        require(type(value) is dict and set(value)==set(cls.__dataclass_fields__))
        result=cls(**value)
        require(text(result.account,63) and len(result.account.encode('utf8'))<=63
                and result.environment in ('simulation','live') and integer(result.max_rows,1,4096)
                and type(result.inspection_version) is int
                and (result.ipc_schema,result.inspection_version,result.source,result.read_profile_version)==
                ('guanheng.account-scan.v2',3,'qmt_shm_bound','qmt.read-profile.v3'))
        return result


def read_publication(path,deadline):
    """复用锁定SDK0.15的同句柄共享删除原语，按NAP大帧合同有界读取。

    SDK普通status的64KiB合同保持；本边界以20MiB+64KiB准入NAP正文，
    同句柄前后stat保持旧完整快照，不把新路径身份与旧句柄混比。
    """
    _inspect(path.parent,directory=True);check(deadline)
    with _open_status_file(path) as stream:
        before=os.fstat(stream.fileno());check_file(before,PUBLICATION_BYTES)
        raw=stream.read(PUBLICATION_BYTES+1);check(deadline)
        after=os.fstat(stream.fileno());check_file(after,PUBLICATION_BYTES)
        require(len(raw)==before.st_size and _identity(before)==_identity(after))
    value=decode_json(raw);check(deadline)
    return value


def _close(value,scan_id,completion,*,successful):
    fields=set(AccountClose.model_fields)|{'resources'}
    require(type(value) is dict and set(value)==fields and type(value['resources']) is dict)
    resources=value['resources'];require(set(resources)==_RESOURCES and all(type(v) is bool for v in resources.values()))
    require(integer(value['queued']) and (value['exit_code'] is None
        or integer(value['exit_code'],-2**31,2**32-1)) and text(value['error_code'],128))
    close=AccountClose.model_validate({key:v for key,v in value.items() if key!='resources'},strict=True)
    if completion is not None:_completion(completion,scan_id,schema='guanheng.account-scan.v2')
    if successful:
        require(completion is not None and completion['closed'] and completion['joined']
                and not completion['worker_live'] and completion['queued']==0 and completion['error_code']=='ok'
                and close.status=='complete' and close.closed and close.joined and not close.worker_live
                and close.queued==0 and close.exit_code==0 and close.error_code=='ok' and all(resources.values()))
    return close


def project_publication(value,runtime_state,deadline):
    require(type(value) is dict and set(value)==_FIELDS and value['schema']=='guanheng.account-observation.v1')
    require(integer(value['revision'],1) and value['state'] in ('waiting','refreshing','ready','degraded','stopped')
            and (value['error_code'] is None or text(value['error_code'],128)))
    require((value['state']=='degraded')==(value['error_code'] is not None))
    updated=stamp(value['updated_at']);binding=ProjectionBinding.from_value(value['binding'])
    successful=value['observation'] is not None
    if successful:
        require(type(value['scan_id']) is str and str(UUID(value['scan_id']))==value['scan_id']
                and stamp(value['last_success_at'])<=updated)
        close=_close(value['close'],value['scan_id'],value['completion'],successful=True)
        observation=validate_observation(value['observation'],value['scan_id'],binding)
        base=project_account(value['scan_id'],observation,close,schema_version='2.0')
        require(base.status=='complete')
        require(all(datetime.fromisoformat(group.execution_finished_at.replace('Z','+00:00'))
            <=stamp(value['last_success_at']) for group in base.groups.values()))
    else:
        require(all(value[key] is None for key in ('scan_id','completion','close','last_success_at')))
        base=unavailable_account('尚未取得WT发布的完整账户结果，四类数据保持未知',schema_version='2.0')
    attempt=value['attempt']
    if attempt is not None:
        require(type(attempt) is dict and set(attempt)=={'scan_id','completion','close'}
                and type(attempt['scan_id']) is str and str(UUID(attempt['scan_id']))==attempt['scan_id'])
        _close(attempt['close'],attempt['scan_id'],attempt['completion'],successful=False)
    require(value['state']!='ready' or successful)
    if value['state']=='waiting':require(not successful and attempt is None)
    if value['state']=='ready':
        require(attempt=={key:value[key] for key in ('scan_id','completion','close')})
    reason={'waiting':'WT账户发布入口已就绪，正在等待首轮结果。',
        'refreshing':'WT正在更新账户；下方保留上次成功结果和原查询时间。' if successful else 'WT正在进行首轮账户读取，四类结果尚未取得。',
        'ready':'WT已发布四类账户结果，各批查询时间独立，仅供只读查看。',
        'degraded':'WT本轮账户更新失败；下方保留上次成功结果和原查询时间。' if successful else 'WT本轮账户读取失败，四类数据保持未知。',
        'stopped':'WT账户发布已停止；下方为最后成功结果和原查询时间。' if successful else 'WT账户发布已停止，尚未取得成功结果。'}[value['state']]
    body=base.model_dump(mode='python');body.update(schema_version='4.0',reason=reason,
        publication=AccountPublication(scope_id=None,state=value['state'],revision=value['revision'],updated_at=value['updated_at'],
            last_success_at=value['last_success_at'],runtime_state=runtime_state))
    check(deadline);return AccountOverviewV4.model_validate(body)


def _reference(runtime):
    """前后根快照共用同一严格准入，JSON等值不能放宽身份类型。"""
    component=runtime['components'].get('account_observation');reference=component.get('account_observation') if component else None
    if reference is None:return None
    require(type(reference) is dict and set(reference)=={'schema','control_id','config_sha256','pid','path','ready_path'}
            and reference['schema']=='guanheng.account-observation-reference.v1')
    control,digest,pid=reference['control_id'],reference['config_sha256'],reference['pid']
    require(type(control) is str and str(UUID(control))==control and type(digest) is str
            and re.fullmatch('[a-f0-9]{64}',digest) and type(pid) is int and 0<pid<2**32
            and type(component.get('pid')) is int and component['pid']==pid==runtime['pid'])
    require(type(reference['path']) is str and type(reference['ready_path']) is str)
    path,ready=Path(reference['path']),Path(reference['ready_path'])
    require(path.is_absolute() and ready.is_absolute() and path.name=='observation.json' and ready.name=='ready.json'
            and path.parent==ready.parent and path.parent.name==control)
    return reference


def _observe_published_account(configuration,deadline):
    if configuration is None:
        base=unavailable_account('尚未配置WT账户发布读取连接',schema_version='2.0').model_dump()
        return AccountOverviewV4.model_validate(base|dict(schema_version='4.0',publication=AccountPublication(
            scope_id=None,state='unconfigured',revision=0,updated_at=None,last_success_at=None,runtime_state='unconfigured')))
    before=read_runtime_snapshot(configuration,deadline).value
    reference=_reference(before)
    if reference is None:
        result=_observe_published_account(None,deadline)
        result.reason='WT尚未提供独立账户发布，四类数据保持未知'
        result.publication.runtime_state=before['state'];return result
    control,digest,pid=reference['control_id'],reference['config_sha256'],reference['pid']
    path,ready=Path(reference['path']),Path(reference['ready_path'])
    _inspect(path.parent,directory=True);check(deadline)
    identity=dict(control_id=control,config_sha256=digest,pid=pid)
    header=read_status_snapshot(ready,4096).value;check(deadline)
    require(header==dict(schema='guanheng.account-observation.ready.v1',**identity)
            and all(type(header[key]) is type(item) for key,item in identity.items()))
    value=read_publication(path,deadline)
    require(all(value.get(key)==item and type(value.get(key)) is type(item) for key,item in identity.items()))
    result=project_publication(value,before['state'],deadline)
    result.publication.scope_id=hashlib.sha256(json.dumps([configuration.control_id,configuration.instance_id,
        configuration.configuration_sha256,control,digest,pid],separators=(',',':')).encode('utf8')).hexdigest()
    after=read_runtime_snapshot(configuration,deadline).value
    require(after['pid']==before['pid'] and _reference(after)==reference)
    result.publication.runtime_state=after['state'];check(deadline);return result


def observe_published_account(configuration,deadline):
    """原读池线程只读同根文件；原子替换的pending沿本次2秒D等待。

    只有短暂未见和Windows共享冲突可以重读，协议/身份错误立即失败。
    每次重读重新核整条根身份，不拼接两次读取，也不创建运行owner。
    """
    while True:
        check(deadline)
        try:
            return _observe_published_account(configuration,deadline)
        except (FileNotFoundError,CollectionStatusPending):
            pass
        except OSError as error:
            if getattr(error,'winerror',None) not in (32,33):raise
        check(deadline)
        sleep(min(.005,max(0,deadline-monotonic())))
