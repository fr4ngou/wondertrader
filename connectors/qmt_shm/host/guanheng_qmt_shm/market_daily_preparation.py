"""WT外部全市场缓存工作流；下载、读取与通信事实各沿原owner。"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

from guanheng_qmt_shm_agent.history_preparation import OPERATION, returned
from guanheng_qmt_shm_agent.trade_clock import CLOCK_SCHEMA
from guanheng_qmt_shm_agent.protocol import canonical, decode
from . import bound
from .analysis_batch_source import BatchAnalysisSource, read_capture
from .read_retention_client import RetainedReadClient, RetainedReadPending, RetainedReadBindingChanged, _save


SCHEMA = 'guanheng.market-daily-preparation.v1'


def _load(path):
    return json.loads(Path(path).read_bytes())


def _original(path, value):
    if path.exists():
        if canonical(_load(path)) != canonical(value):
            raise ValueError('market_daily_workflow_identity_changed')
    else:
        _save(path, value)


class MarketDailyPreparation:
    """同步有界工作流，无定时器或新通信层；每个外部worker独占原客户端。

    调用方拥有工作流目录的单一写权限。max_preparations在提交新任务前暂停；
    已提交原任务在同一绝对截止内完成或留下原slot，executor退出后才返回。
    """
    def __init__(self, hpr_transport_factory, batch_transport, *, concurrency=4):
        if not callable(hpr_transport_factory) or type(concurrency) is not int or not 1 <= concurrency <= 16:
            raise ValueError('market_daily_external_workers')
        self.factory = hpr_transport_factory
        self.batch = BatchAnalysisSource(batch_transport, lifetime_ms=30000)
        self.concurrency = concurrency

    def run(self, request, directory, *, deadline, max_preparations=None, on_progress=None, connection_identity=None):
        """显式v2选择缓存优先；v1保持原请求、目录与回收契约，不迁移旧责任。"""
        if type(request) is dict and request.get('schema') == 'guanheng.market-daily-preparation.v2':
            from .market_daily_cache import run_cache_first
            return run_cache_first(self, request, directory, deadline=deadline,
                max_preparations=max_preparations, on_progress=on_progress,
                connection_identity=connection_identity)
        return self._run_v1(request, directory, deadline=deadline,
            max_preparations=max_preparations, on_progress=on_progress,
            connection_identity=connection_identity)

    def _run_v1(self, request, directory, *, deadline, max_preparations=None, on_progress=None, connection_identity=None):
        """同目录续接原ID；完成包可离线复用，未知请求保留完整原责任。"""
        # 绝对D先准入，NaN/Inf/bool不会创建目录、slot或进入原ID等待。
        if type(deadline) not in (int, float):
            raise ValueError('market_daily_finite_deadline')
        try:
            finite = math.isfinite(deadline)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError('market_daily_finite_deadline')
        if connection_identity is not None and type(connection_identity) is not dict:
            raise ValueError('market_daily_connection_identity')
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        if (type(request) is not dict or set(request) != {'schema','capture','preparation','source_association'}
                or request['schema'] != SCHEMA
                or set(request['preparation']) != {'start_date','end_date'}
                or type(request['source_association']) is not dict
                or max_preparations is not None and (type(max_preparations) is not int or max_preparations < 1)):
            raise ValueError('market_daily_request')
        capture = request['capture']
        symbols = capture['symbols']
        if type(symbols) is not list or not symbols or len(symbols) != len(set(symbols)):
            raise ValueError('market_daily_symbols')
        # 原始配置身份采用canonical字节；不会替换旧workflow/slot/结果的新鲜度。
        _original(directory/'REQUEST.json', request)
        connections_file = directory/'CONNECTIONS.json'
        if connection_identity is not None:
            _original(connections_file, connection_identity)
        elif connections_file.exists():
            raise ValueError('market_daily_connection_identity_required')
        completed = directory/'RESULT.json'
        if completed.exists():
            result = _load(completed)
            if hashlib.sha256((directory/'capture/manifest.json').read_bytes()).hexdigest() != result['capture_sha256']:
                raise ValueError('market_daily_completed_capture_digest')
            read_capture(directory/'capture')
            self._verify_preparations(directory, result['preparations'])
            return result
        if time.monotonic() >= deadline:
            raise RetainedReadPending('market_daily_workflow_deadline')
        first = RetainedReadClient(self.factory(), lifetime_ms=30000)
        # 首个下载前固定两端原认证。capture/BINDING仍归原BatchAnalysisSource；
        # 此处只提前准入相同原记录，续接变化在新SDK/新slot之前结束。
        binding_file = directory/'HPR-BINDING.json'
        batch_binding = directory/'capture/BINDING.json'
        metadata = self._pinned(first, binding_file, 'qmt.read-profile.v6', OPERATION, deadline)
        batch_metadata = self._pinned(self.batch.client, batch_binding, 'qmt.read-profile.v8', 'market.market_data', deadline)
        descriptor = metadata['profile']['operation_profiles'][OPERATION]
        scope = descriptor['limits']
        if scope['schema_version'] != 'qmt.history-preparation-limits.v3':
            raise ValueError('market_daily_explicit_hpr_v3_required')
        _original(binding_file, metadata)
        _original(batch_binding, batch_metadata)
        start, end = request['preparation']['start_date'], request['preparation']['end_date']
        slots = [(i, symbol, directory/'preparation'/('%06d.json' % i)) for i, symbol in enumerate(symbols)]
        existing = [item for item in slots if item[2].exists()]
        fresh = [item for item in slots if not item[2].exists()]
        selected = existing + fresh[:max_preparations] if max_preparations is not None else slots

        records = self._prepare_items(
            [(i, symbol, start, end, slot) for i, symbol, slot in selected], directory,
            metadata, scope, deadline, on_progress, len(symbols))
        if len(records) != len(symbols):
            progress = dict(schema=SCHEMA,state='paused',confirmed=len(records),total=len(symbols),
                preparations=records,SDK_coverage='unconfirmed_until_v8_readback')
            _save(directory/'PROGRESS.json',progress)
            return progress
        manifest = self.batch.capture(capture,directory/'capture',deadline=deadline,
            on_result=(lambda *unused:on_progress(dict(stage='capture'))) if on_progress else None)
        read_capture(directory/'capture')
        result = dict(schema=SCHEMA,state='completed',preparations=records,
            capture='capture/manifest.json',capture_sha256=hashlib.sha256((directory/'capture/manifest.json').read_bytes()).hexdigest(),
            securities=len(symbols),batches=len(manifest['batches']),source_kind=capture['source_kind'],
            generated_at=datetime.now(timezone.utc).isoformat(),coverage_qualified=False,
            adjustment_qualified=False,closed_basis_qualified=False)
        _save(completed,result)
        return result

    def _pinned(self, client, path, version, operation, deadline):
        with client.transport.rpc_budget(min(30., client.transport.timeout)):
            current = client._binding(min(deadline, time.monotonic()+30.))
        if current['profile']['read_profile_version'] != version:
            raise ValueError('market_daily_source_profile')
        if operation not in current['profile']['operation_profiles']:
            raise ValueError('market_daily_source_operation')
        if path.exists() and _load(path)['binding'] != current['binding']:
            raise RetainedReadBindingChanged('market_daily_source_binding_changed')
        return current


    def _prepare_items(self, items_to_prepare, directory, metadata, scope, deadline, on_progress, total, *, minimum_new_request_seconds=0):
        """同一原HPR执行器；items日期为YYYYMMDD；新槽外部余量单位秒，默认0保留v1，v2显式30。"""
        def prepare(item):
            i, symbol, start, end, slot = item
            # 原策略每100ms最多推进一项重SDK；并行外部观察沿同一节拍等待，
            # 避免四worker的20ms轮询超过原nonce窗口容量。业务/SDK截止保持。
            client = RetainedReadClient(self.factory(), lifetime_ms=30000, poll_seconds=.1, wait_for_active_capacity=True)
            def observe(action, until):
                # MDP在既定观察D内统一续核运输未解：准入前仅重复元数据GET；
                # 已有slot由Client依attempted只lookup原ID或确认原结果消费。
                # 业务未知/404/410/确定失败沿原分类返回，截止与SDK预算不重置。
                while True:
                    try:
                        return action()
                    except RetainedReadPending as error:
                        if str(error) != 'read_transport_unresolved' or time.monotonic()+client.poll_seconds >= until:
                            raise
                        time.sleep(client.poll_seconds)
            if slot.exists():
                args = _load(slot)['request']['arguments']
                if (args['symbol'], args['period'], args['start_time'], args['end_time']) != (symbol,'1d',start,end):
                    raise ValueError('market_daily_original_arguments')
            else:
                # 容量等待在原请求生成前完成，保留完整SDK/policy预算；等待本身也有界。
                capacity_deadline = min(deadline,time.monotonic()+scope['total_timeout_ms']/1000.)
                observe(lambda:client.wait_capacity(capacity_deadline),capacity_deadline)
                remaining = min(scope['total_timeout_ms'], int((deadline-time.monotonic())*1000))
                if remaining < 100:
                    raise RetainedReadPending('market_daily_workflow_deadline')
                args = dict(symbol=symbol,period='1d',start_time=start,end_time=end,
                    clock_schema=CLOCK_SCHEMA,deadline_ms=int(client.clock.seconds()*1000)+remaining)
            # 长任务允许数小时运行；每次原请求续核最多消费原scope的一次观察预算。
            # 原slot中的UUID、arguments及deadline_ms保持，超时交回原ID Pending。
            call_deadline = min(deadline,time.monotonic()+scope['total_timeout_ms']/1000.)
            while True:
                try:
                    result = observe(lambda:client.prepare(OPERATION,args,slot,deadline=call_deadline,expected_binding=metadata['binding'],minimum_new_request_seconds=minimum_new_request_seconds,new_request_observation_deadline=deadline),call_deadline)
                    break
                except RetainedReadPending as error:
                    # 并发容量预检并不预留Host条目。仅明确未受理的503允许原ID重交，
                    # 已派发/通信未知/丢结果保持原Pending；整个等待共用原call_deadline。
                    if str(error) != 'read_retention_capacity_rejected' or not slot.exists():
                        raise
                    record = _load(slot)
                    if record['attempted'] is not False or record['result'] is not None:
                        raise
                    # 明确受理前拒绝也让出同一观察节拍，避免容量GET刚空出时热循环重交。
                    time.sleep(min(client.poll_seconds,max(0,call_deadline-time.monotonic())))
                    observe(lambda:client.wait_capacity(call_deadline),call_deadline)
            if result['reply']['data'] != returned(args):
                raise ValueError('market_daily_preparation_result')
            raw = slot.read_bytes()
            return dict(index=i,symbol=symbol,slot=str(slot.relative_to(directory)).replace('\\','/'),
                sha256=hashlib.sha256(raw).hexdigest(),request_id=result['request_id'],
                received_at=result['received_at'],effect='call_returned',coverage='unknown')

        records = []
        # 有限worker只用于终端外通信，QMT SDK仍由原单策略线程串行执行。
        with ThreadPoolExecutor(max_workers=self.concurrency,thread_name_prefix='market-daily-client') as pool:
            # 只保留原concurrency个在途项；首个未解责任后不再派发数千个后继。
            # 已经提交的原任务由executor在各自原D内完成，原slot/UUID保持。
            pending = set()
            items = iter(items_to_prepare)
            def submit_next():
                item = next(items, None)
                if item is not None:
                    pending.add(pool.submit(prepare, item))
            for _ in range(self.concurrency):
                submit_next()
            try:
                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    # 先核同批所有完成项，再允许任何新准入。
                    completed_records = [future.result() for future in done]
                    for record in completed_records:
                        records.append(record)
                        if on_progress is not None:
                            on_progress(dict(stage='preparation',confirmed=len(records),total=total))
                    for _ in done:
                        submit_next()
            except BaseException:
                for future in pending:
                    future.cancel()
                raise
        records.sort(key=lambda row:row['index'])
        return records

    @staticmethod
    def _verify_preparations(directory, records):
        for record in records:
            relative = Path(record['slot'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('market_daily_slot_path')
            raw = (directory/relative).read_bytes()
            if hashlib.sha256(raw).hexdigest() != record['sha256']:
                raise ValueError('market_daily_slot_digest')
            slot = decode(raw)
            bound.validate_response(slot['result'],max_result_bytes=slot['limits']['max_result_bytes'],request=slot['request'])
            reply = decode(bound.unb64(slot['result']['result_body_b64'],slot['limits']['max_result_bytes']))
            if (slot['consumed'] is not True or slot['request']['request_id'] != record['request_id']
                    or reply['ok'] is not True or reply['data'] != returned(slot['request']['arguments'])
                    or slot['request']['arguments']['symbol'] != record['symbol']):
                raise ValueError('market_daily_slot_identity')
