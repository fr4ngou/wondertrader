"""定日已封存QAB包接缝；原来源验证与交易日日历继续唯一拥有各自规则。"""
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from ..managed_local_process import _open_read
from .calendars import last_open_day
from .source_fetch import SourceFailure
from .storage import SnapshotRepository, digest, encode, replace_readable_file
from .t2108_source import decode, history as fixed_history

SCHEMA='guanheng.observation-qas-ready.v1'


def _need(value,code='t2108_ready_schema'):
    if not value:raise SourceFailure(code)


def observation_day(calendar,start,end,*,check=lambda:None):
    """按原官方年历求end的最近闭合交易日；覆盖缺口不推断为休市。"""
    _need(type(calendar) is dict and calendar.get('kind')=='official-exchange-calendar/v1',
        't2108_calendar_required')
    day=last_open_day(calendar,end,check=check)
    _need(start<=day,'t2108_calendar_outside_coverage')
    return day


def _root(directory):
    _need(isinstance(directory,(str,Path)) and Path(directory).is_absolute(),'t2108_ready_path')
    return Path(directory).resolve(strict=True)


def _inside(root,path):
    target=path.resolve(strict=True)
    _need(target.is_relative_to(root),'t2108_ready_path')
    return target


def _packet(root,path):
    target=_inside(root,path);area=root/'packets'
    _need(target.is_relative_to(area) and target.parent!=area,'t2108_ready_path')
    return target


def _control(root,path):
    """控制路径保持原目录身份，拒绝指向封存区或其他日期的目录别名。"""
    try:target=path.resolve(strict=False)
    except (OSError,RuntimeError):raise SourceFailure('t2108_ready_path') from None
    _need(target==path and target.is_relative_to(root) and not target.is_relative_to(root/'packets'),
        't2108_ready_path')
    return path


def _marker(fetch,root,day):
    path=_inside(root,_control(root,root/day/'CURRENT.json'))
    fetch.budget.remaining()
    with _open_read(path) as stream:body=stream.read(fetch.budget.response_bytes+1)
    _need(len(body)<=fetch.budget.response_bytes,'t2108_source_capacity')
    fetch.budget.consume(len(body));identity=fetch.objects.put(body)
    fetch.records.append(dict(kind='qmt_analysis_ready',sha256=identity,media_type='application/json'))
    value=decode(body)
    _need(type(value) is dict and set(value)=={'schema','observation_date','input'}
        and value['schema']==SCHEMA and value['observation_date']==day)
    item=value['input']
    _need(type(item) is dict and set(item)=={'path','sha256'} and type(item['path']) is str)
    _need(not Path(item['path']).is_absolute(),'t2108_ready_path')
    manifest=_packet(root,root/item['path'])
    return manifest,item['sha256']


def history(fetch,source,start,end,*,calendar=None):
    """固定包沿原合同；目录模式只消费目标交易日标记，不回退到旧日期。"""
    if 'input_directory' not in source:return fixed_history(fetch,source,start,end)
    try:
        day=observation_day(calendar,start,end,check=fetch.budget.remaining);root=_root(source['input_directory'])
        manifest,identity=_marker(fetch,root,day)
        fixed={key:value for key,value in source.items() if key!='input_directory'}
        fixed.update(input_manifest=str(manifest),input_sha256=identity)
        # 原history把包日期同时约束为day，保留全部原SHA、slot、闭合与股票池校验。
        return fixed_history(fetch,fixed,day,day)
    except FileNotFoundError:raise SourceFailure('t2108_ready_not_available') from None
    except (OSError,ValueError,KeyError,TypeError):raise SourceFailure('t2108_ready_schema') from None


def publish_ready(fetch,directory,manifest,identity,*,calendar,start,end):
    """来源owner发布根内已封存包；只写原件对象和定日标记，不改变业务current。

    fetch持有调用者原截止、响应/总字节额度及内容对象库，不使用网络方法。
    原Windows collection_lease排他持有整次准入；原件在标记切换后继续不可变。
    结果未知时保留原标记及输入SHA，调用者沿同一输入核查/重试。
    """
    result=None;commit_attempted=False
    try:
        fetch.budget.remaining()
        root=_root(directory)
        _need(isinstance(manifest,(str,Path)) and Path(manifest).is_absolute(),'t2108_ready_path')
        path=_packet(root,Path(manifest))
        day=observation_day(calendar,start,end,check=fetch.budget.remaining)
        marker=_control(root,root/day/'CURRENT.json')
        lease_root=_control(root,root/'.publisher')
        payload=encode(dict(schema=SCHEMA,observation_date=day,
            input=dict(path=path.relative_to(root).as_posix(),sha256=identity)))
        _need(len(payload)<=fetch.budget.response_bytes,'t2108_source_capacity')
        lease_root.mkdir(exist_ok=True)
        _control(root,lease_root)
        with SnapshotRepository(lease_root).collection_lease() as acquired:
            if not acquired:result=dict(status='another_owner_running',observation_date=day)
            else:
                fixed_history(fetch,dict(input_manifest=str(path),input_sha256=identity),day,day)
                fetch.budget.remaining()
                marker.parent.mkdir(exist_ok=True)
                _control(root,marker.parent)
                previous=None
                if marker.exists():
                    current=_inside(root,marker)
                    # 读者允许删除共享，发布者可原子切换；本句柄继续读完整旧版本。
                    with _open_read(current) as stream:previous=stream.read(len(payload)+1)
                    fetch.budget.consume(len(previous))
                if previous==payload:status='already_published'
                else:
                    temporary=marker.with_name('CURRENT.'+str(uuid4())+'.tmp')
                    try:
                        with temporary.open('xb') as stream:
                            _need(stream.write(payload)==len(payload),'t2108_ready_write')
                            stream.flush();os.fsync(stream.fileno())
                        fetch.budget.remaining();commit_attempted=True;replace_readable_file(temporary,marker)
                    finally:
                        if temporary.exists():temporary.unlink()
                    status='published'
                result=dict(status=status,observation_date=day,input_sha256=identity,marker_sha256=digest(payload))
        # 重复发布与新发布共用lease释放后的终态检查，原D覆盖全部文件和租约操作。
        try:fetch.budget.remaining()
        except SourceFailure:
            if result['status'] in ('published','already_published'):
                raise SourceFailure('t2108_ready_publication_unknown') from None
            raise
        return result
    except (OSError,sqlite3.Error,ValueError,KeyError,TypeError):
        if commit_attempted or result and result['status']=='already_published':
            raise SourceFailure('t2108_ready_publication_unknown') from None
        raise SourceFailure('t2108_ready_schema') from None
