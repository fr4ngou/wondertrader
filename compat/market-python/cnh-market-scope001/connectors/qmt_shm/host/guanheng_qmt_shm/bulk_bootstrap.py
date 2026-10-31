"""显式bulk受管工厂；冻结部署值，复用原常驻服务和构造资源槽。"""
from pathlib import Path
import stat
import time
from uuid import UUID
from guanheng_qmt_shm_agent.bulk_capabilities import profile_descriptor
from guanheng_qmt_shm_agent.bulk_configuration import validate_bulk_configuration
from guanheng_qmt_shm_agent.protocol import canonical, decode
from .bootstrap import _snapshot_credentials, _validate_launch_configuration
from .bulk_clock import WindowsBulkUptimeClock
from .bulk_contracts import validate_bulk_source_profile
from .bulk_journal import BulkBoundReadJournal
from .read_service import ReconnectingReadService


def bulk_agent_settings(config,secret):
    """完整v5配置只作纯准入，不创建Agent或SDK。"""
    entries=config['operation_profiles']
    if type(entries) is not dict or not entries:
        raise ValueError('ordinary operation descriptors required')
    timeouts=[value.get('execution_timeout_ms') if type(value) is dict else None for value in entries.values()]
    if any(type(value) is not int for value in timeouts):
        raise ValueError('explicit execution policy required')
    return dict(route=config['route'],secret=secret,allowed_operations=config['read_operations'],
        execution_timeout_ms=max(timeouts),max_frame=config['max_frame'],max_pending=1,
        max_result_bytes=config['max_result_bytes'],connect_seconds=config['connect_seconds'],
        io_seconds=config['io_seconds'],transport=config['transport'],control_profile=config['control_profile'],
        read_profile_version=config['read_profile_version'],operation_profiles=entries,bulk_profile=config['bulk_profile'])


def validate_bulk_settings(value,profile,*,max_result_bytes):
    """部署父目录必须预先存在；逐层拒绝重解析点，BF继续绑定实际文件身份。"""
    if type(value) is not dict or set(value)!={'artifact_root_id','output_root','source_profile','file_limits'}:
        raise ValueError('bulk file settings differ')
    value=decode(canonical(value))
    root_id=value['artifact_root_id']
    if type(root_id) is not str or str(UUID(root_id))!=root_id:
        raise ValueError('canonical artifact root identity required')
    value['source_profile']=validate_bulk_source_profile(value['source_profile'])
    root=value['output_root']
    if type(root) is not str:
        raise ValueError('absolute existing output root required')
    path=Path(root)
    if not path.is_absolute() or path.drive.upper()!='E:' or '..' in path.parts:
        raise ValueError('absolute existing output root required')
    for current in tuple(reversed(path.parents))+(path,):
        info=current.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('ordinary existing output parent required')
    limits=value['file_limits']
    keys={'max_pages','max_page_rows','max_page_bytes','max_csv_bytes','max_total_rows','max_total_bytes','max_manifest_bytes'}
    if type(limits) is not dict or set(limits)!=keys or any(type(n) is not int or n<=0 for n in limits.values()):
        raise ValueError('bulk file limits differ')
    source=profile_descriptor(profile,max_result_bytes=max_result_bytes)['limits']
    if (limits['max_pages']>source['max_pages']
            or limits['max_page_rows']>min(source['max_page_rows'],limits['max_total_rows'])
            or limits['max_total_rows']>source['max_rows']
            or limits['max_page_bytes']>source['max_page_bytes']
            or any(limits[key]>2097152 for key in ('max_page_bytes','max_csv_bytes','max_manifest_bytes'))
            or limits['max_total_bytes']>(limits['max_pages']+1)*2097152):
        raise ValueError('bulk joint file budget differs')
    return value


def validate_launch(config,*,credentials):
    return _validate_launch_configuration(config,credentials=credentials,trading=False,bulk=True)


class ReconnectingBulkReadService(ReconnectingReadService):
    """仅此显式门面允许HTTP创建bulk请求DTO；生命周期仍归原父类。"""
    bulk_requests_enabled=True


def _build_runtime(config,policies,public,credentials,*,clock,monotonic,wait_for_agent=False,failed_owners=None):
    if failed_owners is not None and (type(failed_owners) is not list or len(failed_owners)!=1 or failed_owners[0] is not None):
        raise ValueError('construction owner requires one empty reserved slot')
    profile=validate_bulk_configuration(bulk_agent_settings(config,credentials['ipc_secret'])).profile
    journal=BulkBoundReadJournal(Path(config['journal_path']),config['route'],max_records=config['max_records'],
        max_result_bytes=config['max_result_bytes'],max_request_bytes=public['max_request_bytes'],
        max_journal_bytes=config['max_journal_bytes'],read_profile=profile,clock=clock)
    if failed_owners is not None:
        failed_owners[0]=journal
    try:
        from .bulk_runtime import HostBulkReadRuntime
        runtime=HostBulkReadRuntime(journal,bulk_settings=config['bulk_settings'],bulk_clock=clock,bulk_mono=monotonic,
            secret=credentials['ipc_secret'],max_frame=config['max_frame'],policies=policies,
            transport=config['transport'],control_profile=config['control_profile'],connect_seconds=config['connect_seconds'],
            io_seconds=config['io_seconds'],max_http_inflight=config['max_http_inflight'],
            read_profile=profile,wait_for_agent=wait_for_agent)
        runtime.listen_host,runtime.listen_port=config['listen_host'],config['listen_port']
        if failed_owners is not None:
            failed_owners[0]=None
        return runtime
    except BaseException:
        try:
            journal.close()
        except BaseException:
            if failed_owners is None:
                raise
        else:
            if failed_owners is not None:
                failed_owners[0]=None
        raise


def build_read_service(config,*,credentials,reconnect_seconds,clock=None,monotonic=time.monotonic):
    """start才创建Journal/通信资源；所有代共用冻结部署及同一共享时钟。"""
    credentials=_snapshot_credentials(credentials)
    config,policies,public=validate_launch(config,credentials=credentials)
    clock=WindowsBulkUptimeClock() if clock is None else clock
    if not callable(getattr(clock,'seconds',None)) or not callable(monotonic):
        raise ValueError('trusted bulk clocks required')
    configuration_bytes=canonical(config)
    profile=validate_bulk_configuration(bulk_agent_settings(config,credentials['ipc_secret'])).profile
    construction_owners=[None]
    def factory(candidate,*,credentials):
        if canonical(candidate)!=configuration_bytes:
            raise ValueError('bulk service configuration changed')
        return _build_runtime(candidate,policies,public,credentials,clock=clock,monotonic=monotonic,
            wait_for_agent=True,failed_owners=construction_owners)
    return ReconnectingBulkReadService(factory,configuration=config,credentials=credentials,profile=profile,
        reconnect_seconds=reconnect_seconds,construction_owners=construction_owners)


def create_app(config,*,credentials,reconnect_seconds,clock=None,monotonic=time.monotonic):
    """受管启动入口；调用原签名HTTP应用与原lifespan关闭链。"""
    credentials=_snapshot_credentials(credentials)
    service=build_read_service(config,credentials=credentials,reconnect_seconds=reconnect_seconds,
        clock=clock,monotonic=monotonic)
    from .app import create_app as create_signed_app
    return create_signed_app(service,http_keys=credentials['http_keys'])
