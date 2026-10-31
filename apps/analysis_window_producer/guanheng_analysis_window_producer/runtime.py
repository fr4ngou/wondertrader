"""WT 持有的持续 QNA 发布 owner；观衡及执行消费者只读原子窗口文件。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
from uuid import uuid4

from integrations.guanheng import qmt_native_adjustment as qna
from .source import (AnalysisSnapshotProvider, BoundAnalysisClient,
    SourcePending, SourceUnavailable, write_json, utc_now)
from .pipeline import load, need, validate_snapshot
from guanheng_wt_runtime.thread_owner import ThreadOwner


class NativeRefreshJob:
    """单轮原生工作进程树；监督线程独占 Job，关闭方只设置取消信号。

    两个有界 reader 持续排空管道；整树退出、双 EOF 和标准 join 完成后释放句柄。
    超期会终止本 Job，仍保留真实退出与回收状态，失败不会发布候选。
    """

    def __init__(self, python, cwd):
        self.python, self.cwd = str(Path(python).resolve(strict=True)), str(Path(cwd).resolve(strict=True))
        self.cancel = threading.Event()
        self.receipt = None
        self._job, self._readers = None, []
        self._receipt_path = None

    def run(self, request_path, *, deadline, closing_deadline):
        from guanheng_wt_runtime.strategy_job import ProcessJob
        job = self._job = ProcessJob()
        self._receipt_path = request_path.with_suffix('.JOB.json')
        eof, sizes, buffers = [False, False], [0, 0], [bytearray(), bytearray()]
        failed, forced, exit_code = [], False, None

        def drain(index, stream):
            try:
                while True:
                    block = stream.read(4096)
                    if not block:
                        eof[index] = True
                        return
                    sizes[index] += len(block)
                    buffers[index].extend(block[:max(0, 1048576-len(buffers[index]))])
                    if sizes[index] > 1048576:
                        failed.append('native_output_capacity')
            except BaseException:
                failed.append('native_pipe_read')

        def end():
            close = closing_deadline()
            return min(deadline, close) if close is not None else deadline

        failure = None
        try:
            job.start((self.python, '-B', '-m', 'guanheng_analysis_window_producer.pipeline',
                '--native-request', str(request_path)), self.cwd, deadline=end())
            for index, pipe in enumerate((job.stdout, job.stderr)):
                reader = ThreadOwner(target=drain, args=(index, pipe), name='qna-native-pipe', daemon=True)
                self._readers.append(reader)
                reader.start()
            while job.poll() is None:
                if self.cancel.is_set() or time.monotonic() >= end() or failed:
                    forced = True
                    job.close_job()
                    break
                self.cancel.wait(min(.02, max(0, end()-time.monotonic())))
            exit_code = job.wait(max(0., end()-time.monotonic()))
        except BaseException as error:
            failure = error
            # 创建成功后抛错也保留原 Job 归属，沿同一个截止回收部分创建资源。
            try:
                forced = True
                job.close_job()
                job.wait(max(0., end()-time.monotonic()))
            except BaseException:
                pass
        finally:
            joined = [reader.join_until(end()) for reader in self._readers]
            reaped = False
            try:
                if all(joined) and job.active_processes() == 0:
                    job.close_reaped()
                    reaped = True
            except BaseException:
                pass
            self.receipt = dict(schema='guanheng.qna-native-job.v1', exit_code=exit_code, forced=forced,
                tree_zero=reaped, pipe_eof=eof, readers_joined=all(joined), resources_closed=reaped,
                output_bytes=sizes, output_limit=bool(failed))
            for index, suffix in enumerate(('stdout', 'stderr')):
                request_path.with_suffix('.'+suffix).write_bytes(buffers[index])
            write_json(self._receipt_path, self.receipt)
        if failure is not None:
            raise RuntimeError('analysis_native_job_failed') from failure
        need(exit_code == 0 and not forced and not failed and reaped and len(joined) == 2 and all(eof),
            'analysis_native_job_failed')

    def reap(self, deadline):
        """监督线程 join 后，关闭方沿原 Job 续核超期后的物理资源。"""
        if self._job is None or self.receipt and self.receipt['resources_closed']:
            return True
        try:
            self._job.close_job()
            self._job.wait(max(0., deadline-time.monotonic()))
            if not all(reader.join_until(deadline) for reader in self._readers):
                return False
            self._job.close_reaped()
            self.receipt.update(tree_zero=True, readers_joined=True, resources_closed=True)
            write_json(self._receipt_path, self.receipt)
            return True
        except BaseException:
            return False


class AnalysisWindowProducer:
    """常驻单轮串行刷新；start 只启动 owner，published 表示完整业务已成功。

    来源暂缺/过旧保留成功文件；Pending capture 沿原目录续核。每轮绝对截止与
    常驻寿命分开，显式 request_close 首次设定关闭截止，之后只能收紧。
    """

    def __init__(self, provider, *, directory, publication, artifacts, python=sys.executable,
                 worker_cwd=None, interval_seconds=60., refresh_seconds=120., max_age_seconds=600.,
                 start_date='2021-11-01', max_rows_per_symbol=4096, source_identity=None):
        self.provider = provider
        self.directory, self.publication = Path(directory).absolute(), Path(publication).absolute()
        need(self.directory != self.publication and all(type(v) in (int, float) and math.isfinite(v)
            for v in (interval_seconds, refresh_seconds, max_age_seconds)) and 0 < interval_seconds <= 86400
            and 1 <= refresh_seconds <= 600 and 1 <= max_age_seconds <= 604800
            and type(max_rows_per_symbol) is int and 100 <= max_rows_per_symbol <= 4096,
            'analysis_producer_configuration')
        datetime.strptime(start_date, '%Y-%m-%d')
        self.artifacts = deepcopy(artifacts)
        need(set(artifacts) == {'helper', 'reader', 'probe'}, 'analysis_native_artifacts')
        for value in artifacts.values():
            qna.Artifact(**value).verify()
        self.python = python
        self.worker_cwd = worker_cwd or str(Path(__file__).resolve().parents[3])
        # 外部 provider 的稳定身份由调用者声明；秘密值不属于持久身份，连接绑定其引用。
        need(type(source_identity) is dict and bool(source_identity), 'analysis_source_identity')
        path_identity = lambda value: os.path.normcase(str(Path(value).resolve(strict=True)))
        self._configuration = dict(schema='guanheng.qna-producer-configuration.v1', normalization_version=1,
            source=deepcopy(source_identity), directory=os.path.normcase(str(self.directory.resolve())),
            publication=os.path.normcase(str(self.publication.resolve())),
            artifacts={name: dict(path=path_identity(value['path']), sha256=value['sha256'])
                for name, value in self.artifacts.items()}, python=path_identity(python),
            worker_cwd=path_identity(self.worker_cwd), interval_seconds=float(interval_seconds),
            refresh_seconds=float(refresh_seconds), max_age_seconds=float(max_age_seconds),
            start_date=start_date, max_rows_per_symbol=max_rows_per_symbol)
        need(len(qna.canonical(self._configuration)) <= 32768, 'analysis_configuration_capacity')
        self.interval, self.refresh_seconds, self.max_age = interval_seconds, refresh_seconds, max_age_seconds
        self.start_date, self.max_rows = start_date, max_rows_per_symbol
        self._lock, self._stop, self._wake = threading.RLock(), threading.Event(), threading.Event()
        self._thread = None
        self._runner = None
        self._deadline = None
        self._lease = None
        self._lease_acquired = False
        self._resume_attempt = None
        self._state = dict(schema='guanheng.qna-producer-status.v1', phase='constructed',
            error=None, published_count=0, last_success=None, current_capture_id=None, closed=False)

    def _save_state(self, **changes):
        with self._lock:
            need(self._lease_acquired, 'analysis_publisher_lease')
            self._state.update(changes)
            write_json(self.directory/'STATUS.json', self._state)

    def status(self):
        with self._lock:
            return deepcopy(self._state)

    def start(self, *, deadline):
        with self._lock:
            need(self._thread is None and not self._stop.is_set() and time.monotonic() < deadline,
                'analysis_producer_start')
            self.directory.mkdir(parents=True, exist_ok=True)
            # 原 WT OS 租约在进程退出时由系统释放；OWNER 是留证文件，不承担锁语义。
            from guanheng_wt_runtime.__main__ import _InstanceLease
            lease = self._lease = _InstanceLease(self.directory, 'analysis-window')
            try:
                lease.__enter__()
                self._lease_acquired = True
                self._bind_configuration()
                self.publication.parent.mkdir(parents=True, exist_ok=True)
                self._restore()
                self._record_generation()
                self._save_state(phase='waiting_source', error=None, closed=False)
                owner = self._thread = ThreadOwner(target=self._run, name='qna-window-producer', daemon=True)
                owner.start()
            except BaseException:
                # start 可能在线程已创建后异常；潜在线程仍归原 owner，租约交 close 续核。
                if self._thread is None or not self._thread.pending:
                    self._release_lease()
                raise

    def _release_lease(self):
        if self._lease_acquired:
            self._lease.__exit__(None, None, None)
            self._lease_acquired = False
        self._lease = None

    def _bind_configuration(self):
        """原根配置是恢复权威；在任何业务状态/请求写入及来源调用前核对。

        旧根没有身份时无法证明原连接和发布目标，保留旧证据供原版本处理。
        受控环境中的秘密值可以轮换；持久身份只保存公开连接声明和秘密引用。
        """
        path = self.directory/'CONFIGURATION.json'
        expected = dict(configuration=self._configuration,
            configuration_sha256=hashlib.sha256(qna.canonical(self._configuration)).hexdigest())
        if path.exists():
            need(load(path, 65536) == expected, 'analysis_configuration_conflict')
            return
        need(all(member.name == 'analysis-window.lock' for member in self.directory.iterdir()),
            'analysis_configuration_conflict')
        write_json(path, expected)

    def _restore(self):
        path = self.directory/'STATUS.json'
        if not path.exists():
            return
        previous = load(path, 65536)
        need(previous.get('schema') == self._state['schema'], 'analysis_previous_status')
        success = previous.get('last_success')
        if success is not None and self.publication.exists():
            need(type(success) is dict and success['publication_sha256'] == qna.file_sha(self.publication),
                'analysis_previous_publication_identity')
            self._state.update(last_success=deepcopy(success), published_count=previous['published_count'])
        capture_id = previous.get('current_capture_id')
        if capture_id is None or success is not None and success.get('capture_id') == capture_id:
            return
        from uuid import UUID
        need(type(capture_id) is str and str(UUID(capture_id)) == capture_id, 'analysis_previous_capture')
        attempt = self.directory/('r-'+capture_id[:12])
        request = load(attempt/'REQUEST.json')
        need(request == dict(schema='guanheng.qna-capture-request.v1', capture_id=capture_id,
            symbols=list(qna.SYMBOLS), start_date=self.start_date, max_rows_per_symbol=self.max_rows),
            'analysis_resume_configuration')
        self._resume_attempt = attempt
        self._state['current_capture_id'] = capture_id

    def _record_generation(self):
        marker, status = self.directory/'OWNER.json', self.directory/'STATUS.json'
        archive = self.directory/'owner-records'
        archive.mkdir(exist_ok=True)
        if marker.exists():
            from uuid import UUID
            old = load(marker, 4096)
            identity = old['control_id']
            need(type(identity) is str and str(UUID(identity)) == identity, 'analysis_previous_owner')
            for source, suffix in ((marker, '.json'), (status, '.status.json')):
                if source.exists():
                    target = archive/(identity+suffix)
                    raw = source.read_bytes()
                    if target.exists():
                        need(target.read_bytes() == raw, 'analysis_owner_archive_identity')
                    else:
                        with target.open('xb') as stream:
                            need(stream.write(raw) == len(raw), 'analysis_owner_archive_write')
        write_json(marker, dict(control_id=str(uuid4()), created_at=utc_now().isoformat(), pid=os.getpid()))

    def refresh(self):
        """请求尽快刷新，繁忙时合并通知；不会并发调用 SDK 或创建第二轮 Native。"""
        self._wake.set()

    def _closing_deadline(self):
        with self._lock:
            return self._deadline

    def _effective(self, deadline):
        close = self._closing_deadline()
        return min(deadline, close) if close is not None else deadline

    def _check(self, deadline):
        if self._stop.is_set() or time.monotonic() >= self._effective(deadline):
            raise SourcePending('analysis_refresh_interrupted')

    def _run(self):
        attempt = self._resume_attempt
        try:
            while not self._stop.is_set():
                deadline = time.monotonic()+self.refresh_seconds
                if attempt is None:
                    capture_id = str(uuid4())
                    attempt = self.directory/('r-'+capture_id[:12])
                    attempt.mkdir()
                    write_json(attempt/'REQUEST.json', dict(schema='guanheng.qna-capture-request.v1',
                        capture_id=capture_id, symbols=list(qna.SYMBOLS), start_date=self.start_date,
                        max_rows_per_symbol=self.max_rows))
                request = load(attempt/'REQUEST.json')
                try:
                    self._save_state(phase='reading_source', error=None, current_capture_id=request['capture_id'])
                    snapshot_path = Path(self.provider.capture(request, attempt/'source', deadline=self._effective(deadline)))
                    self._check(deadline)
                    snapshot = load(snapshot_path)
                    identity = validate_snapshot(snapshot, request['capture_id'], max_age_seconds=self.max_age)
                    work = attempt/('n-'+uuid4().hex[:8])
                    work.mkdir()
                    native_request = dict(work=str(work), snapshot=str(snapshot_path), capture_id=request['capture_id'],
                        max_age_seconds=self.max_age, artifacts=self.artifacts, deadline=self._effective(deadline))
                    write_json(work/'JOB-REQUEST.json', native_request)
                    runner = NativeRefreshJob(self.python, self.worker_cwd)
                    with self._lock:
                        self._runner = runner
                        if self._stop.is_set():
                            runner.cancel.set()
                    self._save_state(phase='native_refresh')
                    try:
                        runner.run(work/'JOB-REQUEST.json', deadline=deadline, closing_deadline=self._closing_deadline)
                    except BaseException:
                        if self._stop.is_set():
                            raise SourcePending('analysis_refresh_interrupted') from None
                        raise
                    self._check(deadline)
                    result = load(work/'RESULT.json')
                    candidate_path = work/'CANDIDATE.json'
                    need(result['passed'] is True and result['candidate_sha256'] == qna.file_sha(candidate_path),
                        'analysis_candidate_identity')
                    # 来源年龄再次校验；计算完成时间不延长任何旧来源的可用期。
                    validate_snapshot(snapshot, request['capture_id'], max_age_seconds=self.max_age)
                    candidate = load(candidate_path, 32*1024*1024)
                    candidate['analysis']['known_at'] = identity['source_received_at']
                    candidate['current_view']['received_at'] = identity['source_received_at']
                    need(len(qna.canonical(candidate)) <= 32*1024*1024, 'analysis_publication_capacity')
                    self._check(deadline)
                    # 与 request_close 串行准入；关闭获得锁后不会再发布新窗口。
                    with self._lock:
                        self._check(deadline)
                        try:
                            write_json(self.publication, candidate)
                        except OSError as error:
                            if getattr(error, 'winerror', None) in (32, 33):
                                raise SourcePending('analysis_publication_busy') from None
                            raise
                        success = dict(**identity, capture_id=request['capture_id'], generated_at=result['generated_at'],
                            published_at=utc_now().isoformat(), source_revision=candidate['analysis']['source_revision'],
                            factor_revision=candidate['analysis']['factor_revision'], publication_sha256=qna.file_sha(self.publication),
                            candidate_sha256=result['candidate_sha256'], native_output_sha256=result['native_output_sha256'],
                            import_rows=result['import_rows'], work=str(work))
                        write_json(work/'PUBLICATION.json', success)
                        self._save_state(phase='published', error=None, last_success=success,
                            published_count=self._state['published_count']+1)
                    attempt = None
                except SourcePending:
                    self._save_state(phase='waiting_source', error='source_pending')
                except SourceUnavailable as error:
                    # 已确认缺源后下一轮重新查询；旧窗口及旧时钟原样保持。
                    reason = str(error)
                    if reason not in {'analysis_daily_missing', 'analysis_common_dates_missing',
                            'analysis_source_stale', 'analysis_source_terminal_failure'}:
                        reason = 'source_unavailable'
                    self._save_state(phase='waiting_source', error=reason)
                    attempt = None
                finally:
                    with self._lock:
                        if self._runner is not None and self._runner.receipt and self._runner.receipt['resources_closed']:
                            self._runner = None
                if not self._stop.is_set():
                    self._wake.wait(self.interval)
                    self._wake.clear()
        except BaseException:
            self._save_state(phase='failed', error='analysis_refresh_failed')
        finally:
            if self.status()['phase'] != 'failed':
                self._save_state(phase='stopped')

    def request_close(self, *, deadline):
        with self._lock:
            need(type(deadline) in (int, float) and math.isfinite(deadline), 'analysis_close_deadline')
            self._deadline = deadline if self._deadline is None else min(deadline, self._deadline)
            self._stop.set()
            self._wake.set()
            close_source = getattr(self.provider, 'request_close', None)
            if close_source is not None:
                close_source(deadline=self._deadline)
            if self._runner is not None:
                self._runner.cancel.set()

    def close(self, seconds=10.):
        """沿首个关闭截止 join；无法证明回收时保留 owner，并如实返回 False。"""
        self.request_close(deadline=time.monotonic()+max(0., seconds))
        owner = self._thread
        joined = owner is None or owner.join_until(self._closing_deadline())
        if joined and self._runner is not None:
            self._runner.reap(self._closing_deadline())
        with self._lock:
            resources = self._runner is None or bool(self._runner.receipt and self._runner.receipt['resources_closed'])
            closed = joined and resources
            if self._lease_acquired:
                self._save_state(closed=closed)
                if closed:
                    self._release_lease()
            else:
                self._state['closed'] = closed
            return closed


def create_producer(configuration):
    """WRI 后继装配接缝；连接由 WT 部署提供，构造阶段不建立来源连接。"""
    need(type(configuration) is dict and set(configuration)-{'history_preparation'} == {'source_connection', 'source', 'producer'},
        'analysis_deployment_configuration')
    identity=dict(source_connection=deepcopy(configuration['source_connection']),source=deepcopy(configuration['source']))
    preparation=None
    if 'history_preparation' in configuration:
        from .preparation import DailyHistoryPreparation
        preparation=DailyHistoryPreparation(configuration['history_preparation'],
            checkpoint=Path(configuration['producer']['directory'])/'PREPARATION.json')
        # 权威身份使用与运行一致的已校验浮点值；JSON 的 1 与 1.0 表达同一刷新间隔。
        identity['history_preparation']=dict(connection=deepcopy(configuration['history_preparation']['connection']),
            refresh_interval_seconds=preparation.interval)
    provider=AnalysisSnapshotProvider(BoundAnalysisClient(configuration['source_connection']),configuration['source'],
        preparation=preparation)
    return AnalysisWindowProducer(provider,**configuration['producer'],source_identity=identity)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--configuration', type=Path, required=True)
    args = parser.parse_args()
    config = load(args.configuration)
    owner = create_producer(config)
    owner.start(deadline=time.monotonic()+30.)
    try:
        while owner.status()['phase'] not in ('failed', 'stopped'):
            if (owner.directory/'STOP.json').exists():
                break
            time.sleep(.1)
    finally:
        closed = owner.close(10.)
    return 0 if closed and owner.status()['phase'] != 'failed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
