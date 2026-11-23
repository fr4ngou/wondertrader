"""同一日线service从名册暂缺恢复；SDK/Native替身仅替换外部边界，原请求原件留证。"""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from integrations.guanheng import daily_data_service as service
from integrations.guanheng.daily_data_update import _save, _load, _descriptor
from integrations.guanheng.daily_price_continuation import requires_price_continuation
from integrations.guanheng.daily_price_scope import prepare_price_scope
from integrations.guanheng.market_generation import GenerationPublisher, encode, read_generation
from integrations.guanheng.source_reference_capture import UNIVERSE, DETAILS
from guanheng_qmt_shm.read_retention_client import RetainedReadPending
from daily_gap_fixture import synthetic_gap_plan


class ReferenceResumeTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parents[3]/'.tmp'
        workspace.mkdir(exist_ok=True)
        evidence = os.environ.get('GUANHENG_REFERENCE_RESUME_QA')
        if evidence:
            self.root = Path(evidence)/(self._testMethodName+'-'+uuid4().hex[:8])
            self.root.mkdir(parents=True)
        else:
            temporary = tempfile.TemporaryDirectory(dir=workspace)
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.monotonic = 100.
        self.mode = 'unavailable'
        self.price_calls = []
        self.sdk_calls = []
        self.preserved = {}
        self.control = str(uuid4())
        self.cancel_at_capability = False
        self.transport_closes = 0
        self.config = self.configuration()
        self.descriptor = self.write(self.root/'daily.json', self.config)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        _save(path, value)
        return _descriptor(path)

    def configuration(self):
        security = dict(symbol='SSE.600000', name='合成已有证券', market='SSE', security_type='stock',
            listed_on=None, expires_on=None, observed_at=None)
        baseline = self.write(self.root/'baseline-reference.json', dict(schema='guanheng.security-reference.v1',
            securities={security['symbol']:security}, provenance=dict(catalog_sha256='a'*64,
            details_sha256=None, indices_sha256=None)))
        publication = self.root/'publication'; publication.mkdir()
        calendar = self.write(self.root/'calendar.json', {})
        return dict(schema='guanheng.daily-data-service.v1', directory=str(self.root/'data'),
            raw_store=str(self.root/'raw'), template=dict(schema='guanheng.daily-data-update.v1',
            publication_directory=str(publication), calendar=calendar),
            inputs=dict(connections=dict(batch={}, hpr={}), public_facts=dict(source={}, allowed_hosts=[],
                seconds=30, max_requests=1, max_bytes=1, response_bytes=1, timeout_seconds=1),
                cache_from='20260701', max_rows=40, source_kind='sdk-synthetic'),
            schedule=dict(timezone='Asia/Shanghai', at='09:00', poll_seconds=.1), cycle_seconds=60, retry_seconds=1,
            price_scope=dict(baseline_reference=baseline, reference_connection={'synthetic':True},
                scope=dict(markets=['SH'], security_types=['stock','etf'], limit=256),
                authorized_from='20260701', maximum_history_rows=2000))

    def snapshot_config(self, output, reference, identity):
        snapshot = self.write(output/'snapshot.json', dict(snapshot_id=identity, observation_date='2026-11-05'))
        return self.write(output/'source.json', dict(mode='source-market-snapshot', snapshot=snapshot,
            security_reference=reference))

    def setup_baseline(self):
        descriptor = self.snapshot_config(self.root/'baseline', self.config['price_scope']['baseline_reference'], 'b'*64)
        with GenerationPublisher(self.config['template']['publication_directory']) as publisher:
            publisher.publish(descriptor, expected_current_sha256=None)

    def sdk_source(self, _transport, **_kwargs):
        owner = self
        mode = self.mode
        binding = dict(synthetic_generation='A')
        class Source:
            def capabilities(self, *, deadline):
                owner.assertGreater(deadline, owner.monotonic)
                if owner.cancel_at_capability:
                    owner.stop()
                return dict(state='waiting' if mode=='capability' else 'ready',
                    metadata=dict(binding=binding, profile=dict(operation_profiles={UNIVERSE:{}, DETAILS:{}})))

            def result(self, operation, slot, data, kwargs):
                owner.assertEqual(kwargs['expected_binding'], binding)
                owner.assertEqual(kwargs['deadline'], owner.monotonic+60)
                if not Path(slot).exists():
                    _save(Path(slot), dict(request_id=str(uuid4()), operation=operation, attempted=True))
                owner.sdk_calls.append((operation, str(slot), json.loads(Path(slot).read_bytes())['request_id']))
                if mode=='unavailable':
                    raise RetainedReadPending('read_original_request_unresolved')
                return dict(state='observed', result=dict(binding=binding, reply=dict(data=data)))

            def universe(self, request, slot, **kwargs):
                unsupported = mode=='unsupported'
                groups = [dict(market='SH', security_type=kind, state='unsupported' if unsupported and kind=='etf' else 'complete',
                    expected_count=None if unsupported and kind=='etf' else 1, observed_count=0 if unsupported and kind=='etf' else 1,
                    source_groups=[] if unsupported and kind=='etf' else ['synthetic-'+kind],
                    reason_code='source_unsupported' if unsupported and kind=='etf' else None) for kind in ('stock','etf')]
                symbols = [('600000.SH','stock')] if unsupported else [('600000.SH','stock'),('510300.SH','etf')]
                page = dict(schema='qmt.security-universe.v1', catalog_id='c'*64, captured_at='2026-11-04T01:00:00Z',
                    source_as_of=None, markets=request['markets'], security_types=request['security_types'],
                    state='partial' if unsupported else 'complete', total_count=None if unsupported else 2, groups=groups,
                    items=[dict(symbol=symbol, market='SH', security_type=kind, source_groups=['synthetic-'+kind])
                           for symbol,kind in symbols], next_cursor=None)
                return self.result(UNIVERSE, slot, page, kwargs)

            def details(self, request, slot, **kwargs):
                # 合法详情空值仍完成捕获，不能因此无限重新捕获名册。
                items = [dict(symbol=symbol, market='SH', status='unavailable', name=None, listed_on=None,
                    expires_on=None, trading_status='unknown', observed_at='2026-11-04T01:00:00Z',
                    field_reasons={}, raw_fields={}) for symbol in request['symbols']]
                data = dict(schema='qmt.security-details.v1', catalog_id='c'*64, captured_at='2026-11-04T01:00:00Z',
                    source_as_of=None, items=items)
                return self.result(DETAILS, slot, data, kwargs)
        return Source()

    def prices(self, configuration, day, directory, *, publisher, deadline, cancelled, previous_requests):
        self.assertIsNotNone(publisher._lock)
        self.assertEqual(deadline, self.monotonic+60)
        output = Path(directory); output.mkdir(parents=True, exist_ok=True)
        self.write(output/'REQUEST.json', dict(schema='guanheng.daily-price-refresh.v1', protected_slots=[]))
        self.write(output/'inputs'/'INPUTS.json', dict(configuration=configuration))
        current, old_sha = read_generation(publisher.current_file)
        scope = prepare_price_scope(configuration['price_scope'], day, None, current, output/'inputs'/'prices',
            deadline=deadline, cancelled=cancelled)
        value = _load(scope)
        result = self.write(output/'work'/'prices'/'RESULT.json', dict(scope=scope, inputs=None,
            securities={symbol:dict(target_readable=True, reason='available') for symbol in value['securities']}))
        descriptor = self.snapshot_config(output/'snapshot', value['reference'], scope['sha256'])
        _, identity = publisher.publish(descriptor, expected_current_sha256=old_sha)
        self.price_calls.append(dict(directory=str(output), scope=scope, result=result, at=self.monotonic,
            state=value['reference_state']['state'], expected=_load(value['universe'])['expected_counts']))
        if len(self.price_calls)==1:
            for path in output.rglob('*.json'):
                self.preserved[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        if self.mode in ('unavailable','capability'):
            self.mode = 'captured'
        return dict(current_sha256=identity, price_result=result,
            continuation_required=requires_price_continuation(_load(result)), auxiliary_observation_date='2026-11-04')

    def prepare(self, config, day, output, **kwargs):
        return self.write(Path(output)/'UPDATE.json', dict(synthetic=True))

    def update(self, request, output, *, publisher, **kwargs):
        self.write(Path(output)/'STATE.json', dict(stages=dict(parent=dict(current_sha256='d'*64))))
        return dict(current_sha256=read_generation(publisher.current_file)[1],
            continuation_required=requires_price_continuation(_load(self.price_calls[-1]['result'])))

    def stop(self):
        self.write(self.root/self.control/'stop.json', dict(schema='guanheng.daily-data-stop.v1',
            control_id=self.control, deadline=self.monotonic+5))

    def sleep(self, seconds):
        self.monotonic += seconds
        if self.monotonic>=103:
            self.stop()

    def patches(self):
        stack = ExitStack()
        stack.enter_context(patch('integrations.guanheng.market_generation.load_generation',
            return_value=type('Market',(),{'close':lambda self:None})()))
        stack.enter_context(patch('integrations.guanheng.daily_data_service.observe_input_reads',
            return_value=dict(pending=1)))  # 原未知槽保持；本场景不调用任何真实Host。
        stack.enter_context(patch('integrations.guanheng.daily_data_service.prepare_update', side_effect=self.prepare))
        stack.enter_context(patch('integrations.guanheng.daily_data_service.run_update', side_effect=self.update))
        stack.enter_context(patch('integrations.guanheng.daily_price_refresh.price_refresh', side_effect=self.prices))
        stack.enter_context(patch('integrations.guanheng.source_history_transport.BoundHistorySource',
            side_effect=lambda *_args,**_kw:type('Transport',(),{'close':lambda _:self.closed_transport()})()))
        stack.enter_context(patch('guanheng_qmt_shm.security_reference_source.SecurityReferenceSource', side_effect=self.sdk_source))
        stack.enter_context(patch('integrations.guanheng.daily_data_service.time.monotonic', side_effect=lambda:self.monotonic))
        stack.enter_context(patch('integrations.guanheng.daily_data_service.time.sleep', side_effect=self.sleep))
        return stack

    def closed_transport(self):
        self.transport_closes += 1

    def serve(self):
        service.serve(self.descriptor, self.root/self.control, self.control, as_of='2026-11-05',
            clock=lambda:datetime(2026,11,5,8,tzinfo=timezone.utc))
        return json.loads((Path(self.config['directory'])/'INDEX.json').read_bytes())['2026-11-05']

    def assert_preserved(self):
        for path, digest in self.preserved.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest, path)

    def test_same_service_unavailable_publishes_then_captures_and_stops_retrying(self):
        with self.patches():
            self.setup_baseline()
            result = self.serve()
        self.assertEqual([r['state'] for r in self.price_calls], ['reference_source_unavailable','captured'])
        self.assertGreaterEqual(self.price_calls[1]['at']-self.price_calls[0]['at'], self.config['retry_seconds'])
        self.assertEqual(self.price_calls[1]['expected'], dict(stock=1,etf=1))
        self.assertFalse(result['price_continuation_required'])
        self.assertFalse(result['continuation_required'])
        self.assertEqual(result['price_revision'],1)
        self.assertEqual(len(result['price_history_requests']),1)
        self.assertEqual(self.transport_closes,2)
        self.assert_preserved()

    def test_old_false_index_reconstructs_reference_responsibility(self):
        with self.patches():
            self.setup_baseline()
            root=Path(self.config['directory'])/'2026-11-05'
            price=root/'price-first'/'r000'
            with GenerationPublisher(self.config['template']['publication_directory']) as publisher:
                first=self.prices(self.config,'2026-11-05',price,publisher=publisher,
                    deadline=self.monotonic+60,cancelled=lambda:False,previous_requests=[])
            request=root/'REQUEST.json';self.write(request,{})
            self.write(root.parent/'INDEX.json',{'2026-11-05':dict(state='published',request=str(request),
                continuation_required=False,price_continuation_required=False,price_state='published',price_revision=0,
                price_request=str(price/'REQUEST.json'),price_result=first['price_result'])})
            old_request=_descriptor(request)
            result=self.serve()
        self.assertEqual(len(self.price_calls),2)
        self.assertEqual(self.price_calls[-1]['state'],'captured')
        self.assertEqual(result['revision'],1)
        self.assertEqual(result['history_requests'],[str(request)])
        self.assertEqual(_descriptor(request),old_request)
        self.assertFalse(result['continuation_required'])
        self.assert_preserved()

    def test_waiting_capability_recovers_on_same_service(self):
        self.mode='capability'
        with self.patches():
            self.setup_baseline();self.serve()
        self.assertEqual([r['state']for r in self.price_calls],['waiting_reference_capability','captured'])
        self.assert_preserved()

    def test_captured_unsupported_and_empty_details_do_not_spin(self):
        self.mode='unsupported'
        with self.patches():
            self.setup_baseline();result=self.serve()
        self.assertEqual(len(self.price_calls),1)
        scope=_load(self.price_calls[0]['scope'])
        self.assertEqual(scope['reference_state']['state'],'captured')
        self.assertFalse(scope['reference_state']['membership_complete'])
        self.assertEqual(scope['reference_state']['details_unavailable'],1)
        self.assertFalse(result['continuation_required'])
        self.assertFalse(result['price_continuation_required'])

    def test_cancel_during_capability_does_not_publish_or_dispatch(self):
        self.cancel_at_capability=True
        self.mode='captured'
        with self.patches():
            self.setup_baseline()
            before=_descriptor(Path(self.config['template']['publication_directory'])/'CURRENT.json')
            self.serve()
        self.assertEqual(self.sdk_calls,[])
        self.assertEqual(self.price_calls,[])
        self.assertEqual(_descriptor(Path(self.config['template']['publication_directory'])/'CURRENT.json'),before)

    def test_legacy_without_scope_keeps_existing_price_decision(self):
        self.assertFalse(requires_price_continuation(dict(inputs=None,securities={})))
        scope=self.write(self.root/'legacy-scope.json',{})
        self.assertFalse(requires_price_continuation(dict(scope=scope,inputs=None,securities={})))

    def test_pending_reference_keeps_original_plan_integrity_checks(self):
        scope=self.write(self.root/'pending-scope.json',dict(reference_state=dict(state='reference_source_unavailable')))
        plan=synthetic_gap_plan(self.root/'plan',['600000.SH'],'20261103')
        progress=dict(schema='guanheng.daily-gap-readback-progress.v1',plan_sha256='f'*64,rows=[])
        inputs=self.write(self.root/'price-inputs.json',dict(plan=plan,preparation=progress))
        with self.assertRaisesRegex(ValueError,'readback progress differs'):
            requires_price_continuation(dict(scope=scope,inputs=inputs,securities={}))

    def test_damaged_scope_does_not_turn_into_a_reference_retry(self):
        scope=self.write(self.root/'pending-scope.json',dict(reference_state=dict(state='reference_source_unavailable')))
        Path(scope['path']).write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'file changed'):
            requires_price_continuation(dict(scope=scope,inputs=None,securities={}))


if __name__=='__main__':
    unittest.main()
