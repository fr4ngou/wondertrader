"""唯一Host域线程拥有collector、原Journal提交及失败资源收口。"""
import math
from pathlib import Path
import threading

from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.trade_clock import deadline_seconds
from .bound import unb64
from .bulk_contracts import (validate_bulk_request, bulk_identity, bulk_source_session,
                             make_bulk_result)
from .bulk_history_files import BulkHistoryFiles


class BulkFileDomain:
    """由域回调首次构造；所有文件和资源方法只允许该线程调用。"""
    def __init__(self, runtime, binding):
        self._owner=threading.get_ident()
        self.runtime=runtime
        self.binding=decode(canonical(binding))
        self.settings=runtime.bulk_settings
        self.collector=None
        self.first_error=None
        self.request=None
        self._request_bytes=None
        self._deadline=None
        self._committed=False

    def _owned(self):
        if threading.get_ident()!=self._owner:
            raise RuntimeError('bulk files require original domain owner')

    def _check(self):
        local=self.runtime.bulk_mono()
        shared=self.runtime.bulk_clock.seconds()
        if (type(local) not in (int,float) or not math.isfinite(local)
                or type(shared) not in (int,float) or not math.isfinite(shared)):
            raise ValueError('bulk_clock_unavailable')
        if local>=self._deadline or shared>=deadline_seconds(self.request['deadline_ms']):
            raise TimeoutError('original bulk deadline elapsed')
        return local

    def _start(self, request, deadline):
        value=validate_bulk_request(request,self.runtime.journal.admission_profile,
                                    max_result_bytes=self.runtime.journal.max_result_bytes)
        raw=canonical(value)
        if self.request is not None and raw!=self._request_bytes:
            if not self._committed:
                raise RuntimeError('prior bulk range still owns its domain')
            self._release_resources()
            self.collector=None
            self.request=None
            self.first_error=None
        if self.request is None:
            if type(deadline) not in (int,float) or not math.isfinite(deadline):
                raise ValueError('bulk domain requires original deadline')
            self.request,self._request_bytes=value,raw
            self._deadline=deadline
            self._committed=False
        else:
            self._deadline=min(self._deadline,deadline)
        self._check()
        if self.collector is None:
            identity=bulk_identity(self.request,self.binding)
            relative=identity['range_id']+'--'+identity['snapshot_id']
            self.collector=BulkHistoryFiles(Path(self.settings['output_root'])/relative,
                bulk_source_session(self.binding),self.settings['source_profile'],identity,
                self.settings['file_limits'],self._deadline,self._check)

    def accept(self, payload):
        """耐久中间页返回小收据；最终页原事务提交成功后才给最终收据。"""
        self._owned()
        raw=delivery=None
        try:
            self._start(payload['request'],payload['deadline'])
            delivery=payload['delivery']
            identity=bulk_identity(self.request,self.binding)
            if (type(delivery) is not dict or set(delivery)!=set(
                    'schema request_id identity page_index page_sha256 body'.split())
                    or delivery['schema']!='qmt.history-bulk-delivery.v1'
                    or delivery['request_id']!=self.request['request_id']
                    or delivery['identity']!=identity):
                raise ValueError('invalid bulk page delivery')
            raw=unb64(delivery['body'],self.settings['file_limits']['max_page_bytes'])
            receipt=self.collector.accept(raw,delivery['page_sha256'])
            raw=None
            if receipt['page_index']!=delivery['page_index'] or not receipt['durable']:
                raise ValueError('bulk durable receipt differs')
            self._check()
            if receipt['final']:
                status=self.collector.status()
                data=dict(schema='qmt.history-bulk-artifact.v1',identity=identity,
                    source_session=bulk_source_session(self.binding),source_profile=self.settings['source_profile'],
                    artifact_root_id=self.settings['artifact_root_id'],
                    relative_root=identity['range_id']+'--'+identity['snapshot_id'],
                    manifest_path=receipt['manifest_path'],manifest_sha256=receipt['manifest_sha256'],
                    rows=status['rows_committed'],pages=status['pages_committed'],
                    bytes=status['bytes_committed'],importable=receipt['importable'])
                result=make_bulk_result(self.request['request_id'],data=data,
                                       max_result_bytes=self.runtime.journal.max_result_bytes)
                self._check()
                self.runtime.journal.finish_bound(self.request['request_id'],result,self.binding,
                                                   deadline=self._deadline)
                self._committed=True
            self._check()
            return dict(page_index=receipt['page_index'],page_sha256=receipt['page_sha256'],
                        final=receipt['final'],durable=True,terminal_committed=self._committed)
        except BaseException as error:
            if self.first_error is None:
                self.first_error=error
            raise
        finally:
            raw=delivery=payload=None

    def _release_resources(self):
        """只按实际原资源owner关闭；未知引用留在本对象供原进程收口。"""
        self._owned()
        seen=set()
        failures=[]
        for holder in (self.collector,self.first_error):
            if holder is None:
                continue
            for name in ('retained_resources','retained_stream'):
                resource=getattr(holder,name,None)
                if resource is None or id(resource) in seen:
                    continue
                seen.add(id(resource))
                try:
                    resource.close()
                    if getattr(resource,'closed',False) is not True:
                        raise RuntimeError('bulk resource release remains unconfirmed')
                except BaseException as error:
                    failures.append(error)
        if failures:
            raise RuntimeError('retain bulk domain resource owner') from failures[0]

    def close(self, deadline, requests):
        """GET核实际终态后才中断dispatch；资源释放与业务D分属原调用者预算。"""
        self._owned()
        pending={item['request_id']:item for item in requests}
        if self.request is not None:
            pending[self.request['request_id']]=self.request
        first=None
        for rid,request in pending.items():
            try:
                value=self.runtime.journal.get_bound(rid,deadline=deadline)
                if value is not None and value['state']=='executing':
                    self.runtime.journal.interrupt_bound(rid,request['operation_id'],deadline=deadline)
            except BaseException as error:
                if first is None: first=error
        try:
            self._release_resources()
        except BaseException as error:
            if first is None: first=error
        if first is not None:
            if self.first_error is None: self.first_error=first
            raise first
        return {'closed':True}
