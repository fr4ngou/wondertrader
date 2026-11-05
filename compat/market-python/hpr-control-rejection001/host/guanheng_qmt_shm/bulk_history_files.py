# -*- coding: utf-8 -*-
"""Host单线程收集有界源值页；文件耐久资格与最终Journal提交分开。"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time
from datetime import datetime, timedelta, timezone

from guanheng_qmt_shm_agent.history_1m import HistoryError, _stamp, validated_row
from guanheng_qmt_shm_agent.windows_security import SecurityResourceError
from .private_files import create_private_directory, write_private_durable_new


CAP = 2097152
SHANGHAI = timezone(timedelta(hours=8))
CODES = ('invalid_contract', 'owner_required', 'invalid_page', 'identity_mismatch',
         'page_sequence', 'page_conflict', 'source_value_invalid', 'row_limit',
         'byte_limit', 'file_identity', 'storage_failed', 'expired', 'failed', 'sealed')


class BulkHistoryFilesError(Exception):
    """公开固定分类；私有引用保留未确认资源，交原domain所有者处理。"""
    def __init__(self, code, retained_error=None, retained_resources=None,
                 retained_stream=None, retained_cleanup_error=None):
        self.code = code if type(code) is str and code in CODES else 'storage_failed'
        self.retained_error, self.retained_resources = retained_error, retained_resources
        self.retained_stream, self.retained_cleanup_error = retained_stream, retained_cleanup_error
        Exception.__init__(self, self.code)


def require(value, code='invalid_contract'):
    if not value:
        raise BulkHistoryFilesError(code)


def digest(raw):
    try:
        return hashlib.sha256(raw).hexdigest()
    finally:
        # SHA分配失败也不让本层纯参数经存储异常栈长期持有整页CSV。
        raw = None


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def pairs(items):
    value = {}
    for key, item in items:
        require(key not in value, 'invalid_page')
        value[key] = item
    return value


def invalid_constant(unused):
    raise BulkHistoryFilesError('invalid_page')


def sha_shape(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def fields(value, names, code='invalid_contract'):
    require(type(value) is dict and set(value) == set(names.split()), code)


def text(value, maximum):
    require(type(value) is str and 0 < len(value) <= maximum and bool(value.strip())
            and not any(ord(c) < 32 or 0x7f <= ord(c) <= 0x9f or 0xd800 <= ord(c) <= 0xdfff
                        for c in value))


class BulkHistoryFiles(object):
    """原domain线程持有此对象及retained_*，失败后不再写入或假报关闭。"""
    def __init__(self, root, source_session, source_profile, identity, limits,
                 deadline, clock=time.monotonic):
        self._owner = threading.get_ident()
        self._state, self._failure_code = 'collecting', None
        self.retained_error = self.retained_resources = None
        self.retained_stream = self.retained_cleanup_error = None
        self._pages, self._rows, self._bytes, self._last, self._total = [], 0, 0, None, None
        self._manifest = None
        self._directories = []
        self._deadline, self._clock = deadline, clock
        try:
            require(type(deadline) in (int, float) and math.isfinite(deadline) and callable(clock))
            fields(source_session, 'provider instance_id session_id generation')
            require(source_session['provider'] == 'Qmt')
            for key in ('instance_id', 'session_id'): text(source_session[key], 128)
            require(type(source_session['generation']) is int and 1 <= source_session['generation'] <= 2**64-1)
            fields(source_profile, 'dataset_version source_license input_kind asset_class timezone minute_boundary adjustment factor_version value_semantics price_unit volume_unit amount_unit')
            for key in ('dataset_version', 'source_license'): text(source_profile[key], 256)
            require(source_profile['input_kind'] in ('synthetic', 'qmt_export')
                    and source_profile['asset_class'] == 'cash-equity'
                    and source_profile['timezone'] == 'Asia/Shanghai'
                    and source_profile['minute_boundary'] in ('left', 'right', 'unknown')
                    and source_profile['adjustment'] == 'none' and source_profile['factor_version'] == ''
                    and source_profile['value_semantics'] == 'source'
                    and source_profile['price_unit'] in ('CNY', 'unknown')
                    and source_profile['amount_unit'] in ('CNY', 'unknown')
                    and source_profile['volume_unit'] in ('share', 'lot', 'unknown'))
            fields(identity, 'range_id session_id snapshot_id symbol start_time end_time')
            for key in ('range_id', 'session_id', 'snapshot_id'):
                require(type(identity[key]) is str and 1 <= len(identity[key]) <= 128
                        and re.fullmatch(r'[\x21-\x7e]+', identity[key]) is not None)
            require(identity['session_id'] == source_session['session_id']
                    and type(identity['symbol']) is str
                    and re.fullmatch(r'[0-9]{6}\.(SH|SZ)', identity['symbol']) is not None)
            start, end = _stamp(identity['start_time']), _stamp(identity['end_time'])
            require(_stamp('20211101000000') <= start <= end and end.year <= 2099)
            fields(limits, 'max_pages max_page_rows max_page_bytes max_csv_bytes max_total_rows max_total_bytes max_manifest_bytes')
            require(all(type(n) is int and n > 0 for n in limits.values()))
            require(limits['max_pages'] <= 10000 and limits['max_page_rows'] <= limits['max_total_rows'] <= 1000000
                    and all(limits[k] <= CAP for k in ('max_page_bytes', 'max_csv_bytes', 'max_manifest_bytes'))
                    and limits['max_total_bytes'] <= (limits['max_pages']+1)*CAP)
            self._identity, self._limits = dict(identity), dict(limits)
            self._profile = dict(source_session)
            self._profile.update((k, v) for k, v in source_profile.items() if k != 'asset_class')
            self._start, self._end = start.timestamp()*1000, end.timestamp()*1000
            self._root = Path(root)
            require(self._root.is_absolute() and self._root.drive.upper() == 'E:'
                    and self._root.name not in ('', '.', '..') and '..' not in self._root.parts)
            self._check()
            # 先绑定现有祖先身份；resolve不代替逐层重解析点及后续身份校验。
            for path in reversed(self._root.parents):
                self._check()
                info = self._io(path.lstat)
                self._ordinary(info, True)
                self._directories.append((path, (info.st_dev, info.st_ino)))
            self._check()
            require(not self._io(self._root.exists), 'file_identity')
            for path in (self._root, self._root/'csv'):
                self._check_directories()
                made = self._io(create_private_directory, path)
                require(Path(made) == path, 'file_identity')
                self._check()
                info = self._io(path.lstat)
                self._ordinary(info, True)
                self._directories.append((path, (info.st_dev, info.st_ino)))
            self._check()
        except BaseException as error:
            raise self._latch(error) from None

    def _owner_check(self):
        require(threading.get_ident() == self._owner, 'owner_required')

    def _check(self):
        if self._failure_code is not None:
            raise self._public_error()
        now = self._clock()
        require(type(now) in (int, float) and math.isfinite(now))
        if now >= self._deadline:
            raise BulkHistoryFilesError('expired')

    def _public_error(self):
        return BulkHistoryFilesError(self._failure_code, self.retained_error, self.retained_resources,
                                     self.retained_stream, self.retained_cleanup_error)

    def _io(self, operation, *args):
        """显式IO责任边界；失败只标归属，不把纯处理异常统称资源异常。"""
        try:
            return operation(*args)
        except BaseException as error:
            self._latch(error, retain=True)
            raise
        finally:
            args = None

    def _latch(self, error, retain=False):
        if self._failure_code is None:
            if isinstance(error, BulkHistoryFilesError):
                code = error.code
            elif isinstance(error, TimeoutError) or (isinstance(error, SecurityResourceError)
                                                     and isinstance(error.original, TimeoutError)):
                code = 'expired'
            elif isinstance(error, HistoryError):
                code = 'source_value_invalid'
            else:
                code = 'storage_failed'
            resources = error.resources if isinstance(error, SecurityResourceError) else None
            # 无资源的验证异常不保留解码/字段/数值栈；实际存储责任仍保留原对象。
            retain = isinstance(error, SecurityResourceError) or (
                retain and not isinstance(error, (BulkHistoryFilesError, HistoryError)))
            self.retained_error = error if retain else None
            self.retained_resources = resources
            self._failure_code = BulkHistoryFilesError(code).code
            if not (self._state in ('sealed', 'empty') and self._failure_code == 'expired'):
                self._state = 'expired' if self._failure_code == 'expired' else 'failed'
        return self._public_error()

    def _ordinary(self, info, directory=False):
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'file_identity')
        require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), 'file_identity')
        if not directory:
            require(info.st_nlink == 1 and 0 < info.st_size <= CAP, 'file_identity')

    def _check_directories(self):
        for path, identity in self._directories:
            self._check()
            info = self._io(path.lstat)
            self._ordinary(info, True)
            require((info.st_dev, info.st_ino) == identity, 'file_identity')
        self._check()

    @staticmethod
    def _signature(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink)

    def _read(self, relative, expected_sha, expected_size, expected_identity=None):
        """只读本对象生成的固定路径，绑定路径与已打开同一文件的前后身份。"""
        raw = None
        try:
            self._check_directories()
            path = self._root/relative
            before = path.lstat()
            self._ordinary(before)
            require(before.st_size == expected_size, 'file_identity')
            if expected_identity is not None:
                require(self._signature(before) == expected_identity, 'file_identity')
            self._check()
            stream = path.open('rb')
            primary = None
            try:
                opened = os.fstat(stream.fileno())
                self._ordinary(opened)
                require(self._signature(opened) == self._signature(before), 'file_identity')
                self._check()
                raw = stream.read(expected_size+1)
                self._check()
                after_read = os.fstat(stream.fileno())
                require(self._signature(after_read) == self._signature(opened), 'file_identity')
            except BaseException as error:
                primary = error
            # 先保存业务异常，再独立关闭；关闭错误不能覆盖读取或原D首因。
            try:
                stream.close()
            except BaseException as cleanup:
                self.retained_stream = stream
                self.retained_cleanup_error = cleanup
                if primary is None:
                    primary = cleanup
            if primary is not None:
                raise primary
            self._check()
            after = path.lstat()
            self._ordinary(after)
            require(self._signature(after) == self._signature(opened) and len(raw) == expected_size
                    and digest(raw) == expected_sha, 'file_identity')
            self._check_directories()
            return self._signature(after)
        except BaseException as error:
            self._latch(error, retain=True)
            raise
        finally:
            # 保留异常可能持有的stream所有者，仅清本方法读取的数据缓冲。
            raw = None

    def _write(self, relative, raw):
        try:
            self._check_directories()
            write_private_durable_new(self._root/relative, raw, self._deadline, self._clock)
            self._check()
            return self._read(relative, digest(raw), len(raw))
        except BaseException as error:
            self._latch(error, retain=True)
            raise
        finally:
            # writer同步返回或抛错后释放本层内容；未知句柄仍由retained_resources持有。
            raw = None

    def _verify_record(self, record):
        if record['csv_path'] is not None:
            self._read(record['csv_path'], record['csv_sha256'], record['csv_bytes'], record['csv_identity'])

    def _verify_manifest(self):
        for record in self._pages:
            self._verify_record(record)
        if self._manifest is not None:
            path, sha, size, identity = self._manifest
            self._read(path, sha, size, identity)

    def accept(self, page_bytes, page_sha256):
        self._owner_check()
        failed = False
        page = rows = content = raw = manifest_raw = row = values = rendered = line = chunks = None
        try:
            self._check()
            require(type(page_bytes) is bytes and 0 < len(page_bytes) <= self._limits['max_page_bytes'], 'byte_limit')
            require(sha_shape(page_sha256) and digest(page_bytes) == page_sha256, 'invalid_page')
            try:
                page = json.loads(page_bytes.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid_constant)
            except (UnicodeError, ValueError, RecursionError):
                raise BulkHistoryFilesError('invalid_page') from None
            self._check()
            fields(page, 'schema identity page_index rows final total_rows', 'invalid_page')
            require(page['schema'] == 'qmt.history-bulk-page.v1', 'invalid_page')
            require(page['identity'] == self._identity, 'identity_mismatch')
            index, total, final, rows = page['page_index'], page['total_rows'], page['final'], page['rows']
            require(type(index) is int and 0 <= index < self._limits['max_pages']
                    and type(total) is int and 0 <= total <= self._limits['max_total_rows']
                    and type(final) is bool and type(rows) is list, 'invalid_page')
            if index < len(self._pages):
                record = self._pages[index]
                require(record['page_sha256'] == page_sha256, 'page_conflict')
                self._verify_record(record)
                if record['receipt']['final']:
                    self._verify_manifest()
                answer = dict(record['receipt'])
                self._check()
                return answer
            require(self._state == 'collecting', 'sealed')
            require(index == len(self._pages), 'page_sequence')
            require(self._total is None or total == self._total, 'invalid_page')
            require(len(rows) <= self._limits['max_page_rows'], 'row_limit')
            count = self._rows+len(rows)
            require(count <= self._limits['max_total_rows'] and (count == total if final else count < total), 'row_limit')
            empty = not rows and index == 0 and final and total == 0
            require(bool(rows) or empty, 'invalid_page')
            content = bytearray(b'timestamp,open,high,low,close,volume,amount\n')
            last = self._last
            for row in rows:
                self._check()
                require(type(row) is list and len(row) == 7 and all(type(v) in (int, float) for v in row), 'invalid_page')
                values = validated_row(row, self._start, self._end, last, self._check)
                stamp = datetime.fromtimestamp(values[0]/1000, SHANGHAI)
                rendered = [format(float(v), '.17g') for v in values[1:]]
                require(all(float(text) == float(value) for text, value in zip(rendered, values[1:])), 'source_value_invalid')
                line = (stamp.strftime('%Y-%m-%dT%H:%M:00+08:00')+','+','.join(rendered)+'\n').encode('ascii')
                require(len(content)+len(line) <= self._limits['max_csv_bytes'], 'byte_limit')
                content.extend(line)
                last = values[0]
                self._check()
            raw = None if empty else bytes(content)
            relative = None if empty else 'csv/page-{:06d}.csv'.format(index)
            csv_sha = None if empty else digest(raw)
            csv_size = 0 if empty else len(raw)
            manifest_raw = None
            if final and not empty:
                chunks = [{'path': r['csv_path'], 'sha256': r['csv_sha256']} for r in self._pages]
                chunks.append({'path': relative, 'sha256': csv_sha})
                manifest_raw = canonical({'schema_version': 2, 'profile': self._profile,
                                          'securities': [{'symbol': self._identity['symbol'], 'chunks': chunks}]})
                require(len(manifest_raw) <= self._limits['max_manifest_bytes'], 'byte_limit')
            added = csv_size+(len(manifest_raw) if manifest_raw is not None else 0)
            require(self._bytes+added <= self._limits['max_total_bytes'], 'byte_limit')
            manifest_sha = digest(manifest_raw) if manifest_raw is not None else None
            receipt = dict(page_index=index, page_sha256=page_sha256, csv_path=relative, csv_sha256=csv_sha,
                           rows=len(rows), total_rows=total, final=final, durable=True,
                           ack_eligible=not final, requires_terminal_commit=final,
                           manifest_path='qmi-manifest.json' if manifest_raw is not None else None,
                           manifest_sha256=manifest_sha, importable=final and not empty)
            answer = dict(receipt)
            record = dict(page_sha256=page_sha256, csv_path=relative, csv_sha256=csv_sha,
                          csv_bytes=csv_size, csv_identity=None, receipt=receipt)
            updated = self._pages+[record]
            updated_bytes = self._bytes+added
            if final:
                self._verify_manifest()
            self._check()
            if raw is not None:
                record['csv_identity'] = self._write(relative, raw)
            manifest = None
            if manifest_raw is not None:
                self._verify_manifest()
                self._verify_record(record)
                identity = self._write('qmi-manifest.json', manifest_raw)
                manifest = ('qmi-manifest.json', manifest_sha, len(manifest_raw), identity)
            self._check()
            self._pages, self._rows, self._bytes, self._last, self._total = updated, count, updated_bytes, last, total
            if final:
                self._manifest = manifest
                self._state = 'empty' if empty else 'sealed'
            return answer
        except BaseException as error:
            self._latch(error)
            failed = True
        finally:
            # 原异常可能保留本frame；只清本层行情数据，不擦除异常图或未知资源owner。
            page_bytes = page = rows = content = raw = manifest_raw = row = values = rendered = line = chunks = None
        if failed:
            raise self._public_error()

    def status(self):
        self._owner_check()
        if self._state == 'collecting':
            try:
                self._check()
            except BaseException as error:
                self._latch(error)
        return dict(state=self._state, failure_code=self._failure_code,
                    pages_committed=len(self._pages), rows_committed=self._rows, bytes_committed=self._bytes,
                    next_page_index=len(self._pages), identity=dict(self._identity),
                    manifest_sha256=self._manifest[1] if self._manifest is not None else None)
