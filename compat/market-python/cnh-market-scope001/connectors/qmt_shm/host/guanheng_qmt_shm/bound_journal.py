"""同一通信Journal的来源关联列；没有第二套账户或交易事实。

调用顺序固定为runtime ready锁→本事务锁；本模块从不回调runtime。
状态提交先于派发，结果与原channel身份同事务保存后才允许ACK。
"""
from __future__ import annotations
from contextlib import contextmanager
import time
import math
import sqlite3
from guanheng_qmt_shm_agent.protocol import canonical, decode, identity
from .bound import binding, digest, b64, validate_response, SCHEMA, MAX_METADATA_BYTES
from .contracts import BoundGatewayOperationRequest, GatewayOperationResult
from .journal import HostReadJournal, JournalConflict, JournalFull
from guanheng_qmt_shm_agent.read_capabilities import (validate_read_request, validate_read_profile,
    validate_read_result_projection)


class BoundReadJournal(HostReadJournal):
    def __setattr__(self, name, value):
        if name in {'path','route','max_records','max_result_bytes','max_request_bytes','max_journal_bytes','_read_profile_bytes','binding_control_version'} and hasattr(self,name):
            raise AttributeError('Journal admission configuration is frozen for this owner')
        object.__setattr__(self,name,value)

    @property
    def route(self):
        return decode(self._route_bytes)

    @route.setter
    def route(self, value):
        self._route_bytes=canonical(identity(value))

    @contextmanager
    def _transaction(self, deadline=None):
        remaining=None if deadline is None else max(0,deadline-time.monotonic())
        acquired=self._lock.acquire() if remaining is None else self._lock.acquire(timeout=remaining)
        if not acquired:
            raise TimeoutError('Journal transaction busy; retain its owner')
        db=None
        try:
            if self._owner.closed:
                raise RuntimeError('Journal owner is closed')
            if deadline is not None and time.monotonic()>=deadline:
                raise TimeoutError('Journal transaction deadline elapsed')
            timeout=1 if deadline is None else min(1,max(0,deadline-time.monotonic()))
            db=sqlite3.connect(self.path,timeout=timeout)
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            self._finish_deadline(deadline)
            db.commit()
            # COMMIT返回后超时保留实际落盘结果；调用方保留owner且不发送源ACK。
            self._finish_deadline(deadline)
        except BaseException:
            if db is not None:db.rollback()
            raise
        finally:
            if db is not None:db.close()
            self._lock.release()
        # 编码返回也须等待连接真实关闭；失败路径保留原异常，不以新超时覆盖。
        self._finish_deadline(deadline)

    def __init__(self, path, route, *, max_records, max_result_bytes, max_request_bytes, max_journal_bytes, read_profile=None):
        if (type(max_request_bytes) is not int or not 1<=max_request_bytes<=65536
                or type(max_result_bytes) is not int or not 1024<=max_result_bytes<=2097152
                or type(max_records) is not int or not 1<=max_records<=1000000):
            raise ValueError('invalid explicit Journal joint budget')
        unit=max_request_bytes+max_result_bytes+MAX_METADATA_BYTES
        if type(max_journal_bytes) is not int or not unit <= max_journal_bytes <= max_records*unit:
            raise ValueError('explicit logical Journal byte budget is invalid')
        profile = ({'read_operations':['market.full_tick'],'execution_timeout_ms':30000} if read_profile is None
            else validate_read_profile(read_profile,max_result_bytes=max_result_bytes))
        self._read_profile_bytes=canonical(profile)
        # 验证器来自已准入的owner配置，不能由来路B自行选择版本。
        self.binding_control_version=profile.get('control_profile',{}).get('schema_version','1.0')
        self.max_request_bytes=max_request_bytes
        self.max_journal_bytes=max_journal_bytes
        super().__init__(path,route,max_records=max_records,max_result_bytes=max_result_bytes)
        try:
            with self._transaction() as db:
                extra={'admitted_binding':'BLOB','dispatch_binding':'BLOB','result_binding':'BLOB',
                    'reserved_bytes':'INTEGER'}
                original={'seq','request_id','operation_id','request_sha256','body','state','expires_at',
                    'queued_at','started_at','result'}
                columns={row[1] for row in db.execute('PRAGMA table_info(read_operations)')}
                if columns-original-set(extra):
                    raise JournalConflict('unknown communication Journal columns')
                for name,kind in extra.items():
                    if name not in columns:
                        db.execute('ALTER TABLE read_operations ADD COLUMN '+name+' '+kind)
                # Legacy records remain auditable and unqualified. Their maximum
                # result/metadata reservation also consumes the same logical cap.
                db.execute('UPDATE read_operations SET reserved_bytes=length(body)+?+? WHERE reserved_bytes IS NULL',
                    (max_result_bytes,MAX_METADATA_BYTES))
                if self._used(db)>max_journal_bytes:
                    raise JournalFull('retained communication facts exceed logical byte budget')
        except BaseException:
            self.close()
            raise

    @property
    def admission_profile(self):
        return decode(self._read_profile_bytes)

    def _validated_binding(self, value):
        return binding(value,control_version=self.binding_control_version)

    @staticmethod
    def _used(db):
        return db.execute('SELECT COALESCE(SUM(reserved_bytes),0) FROM read_operations').fetchone()[0]

    def submit(self, *args, **kwargs):
        raise JournalConflict('this owner requires bound admission')

    def claim(self):
        raise JournalConflict('this owner requires actual channel identity')

    def finish(self, *args, **kwargs):
        raise JournalConflict('this owner requires received channel identity')

    def close(self, deadline=None):
        if deadline is None:
            return super().close()
        if type(deadline) not in (int,float) or not math.isfinite(deadline):
            raise ValueError('close requires absolute monotonic deadline')
        if not self._lock.acquire(timeout=max(0,deadline-time.monotonic())):
            raise TimeoutError('Journal transaction busy; retain its owner')
        try:
            if not self._owner.closed:
                self._owner.close()
        finally:
            self._lock.release()

    def _validate_bound_request(self, raw_request):
        """默认准入保留原profile与DTO；扩展owner仅覆盖自己拥有的操作。"""
        validate_read_request(raw_request,self.admission_profile,max_result_bytes=self.max_result_bytes)
        return BoundGatewayOperationRequest.model_validate(raw_request)

    def _admit_new_bound(self, raw_request, queue_timeout_ms):
        """只在同事务查重之后生成首次UTC排队投影。"""
        return time.time()+queue_timeout_ms/1000

    def _queued_bound_failure(self, raw_request):
        """完整来源匹配之后可核业务时效；默认沿原UTC期限。"""
        return None

    def _normalize_bound_result(self, result):
        return GatewayOperationResult.model_validate(result).model_dump(mode='json')

    def _validate_bound_projection(self, request, result, actual_binding):
        return validate_read_result_projection(request, result)

    def _validate_bound_response(self, value, request):
        return validate_response(value,max_result_bytes=self.max_result_bytes,
            control_version=self.binding_control_version,request=request)

    def submit_bound(self, body, admitted_binding, *, queue_timeout_ms, deadline=None):
        self._finish_deadline(deadline)
        if not isinstance(body,bytes) or len(body)>self.max_request_bytes:
            raise ValueError('original request bytes required')
        if type(queue_timeout_ms) is not int or not 1 <= queue_timeout_ms <= 300000:
            raise ValueError('invalid persisted queue timeout')
        admitted=self._validated_binding(admitted_binding)
        if admitted['route']!=self.route:
            raise JournalConflict('request route differs')
        encoded=canonical(admitted)
        raw_request=decode(body)
        request=self._validate_bound_request(raw_request)
        semantic=digest(canonical({'operation_id':request.operation_id,'arguments':request.arguments}))
        rid=str(request.request_id)
        reservation=len(body)+self.max_result_bytes+MAX_METADATA_BYTES
        with self._transaction(deadline) as db:
            existing=db.execute('SELECT body,admitted_binding FROM read_operations WHERE request_id=?',(rid,)).fetchone()
            if existing is not None:
                if existing[1] is None or bytes(existing[0])!=body or bytes(existing[1])!=encoded:
                    raise JournalConflict('bound request identity already has different bytes or source')
                return rid
            if (db.execute('SELECT COUNT(*) FROM read_operations').fetchone()[0]>=self.max_records
                    or self._used(db)+reservation>self.max_journal_bytes):
                raise JournalFull('communication Journal admission capacity exhausted')
            expires=self._admit_new_bound(raw_request,queue_timeout_ms)
            self._finish_deadline(deadline)
            db.execute('''INSERT INTO read_operations
                (request_id,operation_id,request_sha256,body,state,expires_at,queued_at,admitted_binding,reserved_bytes)
                VALUES(?,?,?,?,'queued',?,?,?,?)''',
                (rid,request.operation_id,semantic,body,expires,time.time(),encoded,reservation))
        return rid

    def claim_bound(self, actual_binding, *, deadline=None):
        self._finish_deadline(deadline)
        actual=canonical(self._validated_binding(actual_binding))
        with self._transaction(deadline) as db:
            while True:
                self._finish_deadline(deadline)
                row=db.execute('''SELECT request_id,operation_id,body,expires_at,admitted_binding
                    FROM read_operations WHERE state='queued' ORDER BY seq LIMIT 1''').fetchone()
                if row is None:
                    return None
                rid,operation,body,expires,admitted=row
                remaining=int((expires-time.time())*1000)
                if admitted is None or bytes(admitted)!=actual:
                    self._finish(db,rid,self._interrupted_result(rid,operation,'source_binding_changed'))
                    continue
                failure=self._queued_bound_failure(decode(bytes(body)))
                if failure is not None:
                    self._finish(db,rid,self._interrupted_result(rid,operation,failure))
                    continue
                if remaining<=0:
                    self._finish(db,rid,self._interrupted_result(rid,operation,'queue_timeout'))
                    continue
                db.execute("UPDATE read_operations SET state='dispatching',started_at=?,dispatch_binding=? WHERE request_id=?",
                    (time.time(),actual,rid))
                return rid,bytes(body),remaining,expires

    @staticmethod
    def _finish_deadline(deadline):
        if deadline is not None:
            if type(deadline) not in (int, float) or not math.isfinite(deadline):
                raise ValueError('result persistence requires an absolute monotonic deadline')
            if time.monotonic() >= deadline:
                raise TimeoutError('original read result persistence deadline elapsed')

    def finish_bound(self, rid, result, received_binding, *, deadline=None):
        """原结果持久I/O截止从入队前冻结；None保留已有直接调用接口。"""
        self._finish_deadline(deadline)
        actual=canonical(self._validated_binding(received_binding))
        raw=canonical(result)
        normalized=self._normalize_bound_result(result)
        if canonical(normalized)!=raw or len(raw)>self.max_result_bytes:
            raise JournalConflict('native terminal wire differs from complete bounded result')
        unsigned=dict(result)
        expected=unsigned.pop('result_sha256',None)
        if digest(canonical(unsigned))!=expected:
            raise JournalConflict('native terminal content identity differs')
        self._finish_deadline(deadline)
        with self._transaction(deadline) as db:
            self._finish_deadline(deadline)
            row=db.execute('SELECT operation_id,state,dispatch_binding,body FROM read_operations WHERE request_id=?',(rid,)).fetchone()
            if (row is None or row[1]!='dispatching' or row[2] is None or bytes(row[2])!=actual
                    or result['request_id']!=rid or result['operation_id']!=row[0]):
                raise JournalConflict('native result differs from its dispatched channel')
            self._validate_bound_projection(decode(bytes(row[3])), result, decode(actual))
            self._finish_deadline(deadline)
            # raw is saved once. HTTP retrieval base64-wraps these exact bytes.
            db.execute("UPDATE read_operations SET state='terminal',result=?,result_binding=? WHERE request_id=?",
                (raw,actual,rid))
            self._bound_result_saved(db, rid, decode(bytes(row[3])), result, deadline)
            self._finish_deadline(deadline)

    def _bound_result_saved(self, db, rid, request, result, deadline):
        """同一通信事务的扩展点；默认只读owner没有委托关联。"""
        pass

    def interrupt_bound(self, rid, operation, *, deadline=None):
        with self._transaction(deadline) as db:
            row=db.execute('SELECT operation_id,state FROM read_operations WHERE request_id=?',(rid,)).fetchone()
            if row is None or row[0]!=operation or row[1]!='dispatching':
                raise JournalConflict('interruption differs from active dispatch')
            self._finish(db,rid,self._interrupted_result(rid,operation,'operation_interrupted'))

    def get_bound(self, rid, *, deadline=None):
        self._finish_deadline(deadline)
        with self._transaction(deadline) as db:
            row=db.execute('''SELECT operation_id,request_sha256,body,state,result,
                admitted_binding,dispatch_binding,result_binding FROM read_operations WHERE request_id=?''',(rid,)).fetchone()
            if row is None:
                return None
            operation,semantic,body,state,result,admitted,dispatched,received=row
            raw=bytes(result) if result is not None else None
            value={'schema_version':SCHEMA,'request_id':rid,'operation_id':operation,'request_sha256':semantic,
                'request_body_sha256':digest(bytes(body)) if body is not None else None,
                'binding_status':'recorded' if admitted is not None else 'legacy_unqualified',
                'admitted_binding':decode(bytes(admitted)) if admitted is not None else None,
                'dispatch_binding':decode(bytes(dispatched)) if dispatched is not None else None,
                'result_binding':decode(bytes(received)) if received is not None else None,
                'state':'executing' if state=='dispatching' else state,
                'result_body_b64':b64(raw) if raw is not None else None,
                'result_body_sha256':digest(raw) if raw is not None else None}
            return self._validate_bound_response(value,decode(bytes(body)))
