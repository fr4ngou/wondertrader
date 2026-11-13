"""旧分钟窗口退出lookback后，原请求先交接完整终态，禁止新派发。"""
from pathlib import Path
from contextlib import nullcontext
from collections import deque
import tempfile
import threading
import time
import unittest

from guanheng_qmt_shm_agent.protocol import canonical,decode
from guanheng_qmt_shm_agent.results import finalize_result
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.read_capabilities import build_read_profile,HISTORY
from guanheng_qmt_shm.read_retention_journal import RetainedReadJournal
from guanheng_qmt_shm import bound
from types import SimpleNamespace
from integrations.guanheng.source_history_reads import HistoryReadOperations
from integrations.guanheng.source_history_preparation import SourcePreparingMarket,SourcePending
from integrations.guanheng.source_history_repository import PreparedHistoryRepository
from tests.integration.qmt_shm_trading.test_trade_capabilities import CONTROL,read_entries
from guanheng_qmt_shm.read_retention_client import RetainedReadClient,RetainedReadPending
from integrations.guanheng.source_history_transport import BoundHistorySource
from integrations.guanheng.collection_maintenance import MinuteCollectionMaintenance


class RetainedResumeTests(unittest.TestCase):
    def test_new_transport_port_keeps_the_original_producer_binding(self):
        original = {'base_url': 'http://127.0.0.1:50885', 'key_id': 'fixture',
                    'secret_env': 'FIXTURE_SECRET', 'timeout': 1}
        environment = {'FIXTURE_SECRET': 's' * 32}
        old = BoundHistorySource(original, environ=environment)
        new = BoundHistorySource(original, environ=environment, transport_port=18149)
        self.assertEqual((old.host, old.port), ('127.0.0.1', 50885))
        self.assertEqual((new.host, new.port), ('127.0.0.1', 18149))
        self.assertEqual((new.key_id, new.secret), (old.key_id, old.secret))
        self.assertEqual(original['base_url'], 'http://127.0.0.1:50885')
        for port in (0, True, '18149', 65536):
            with self.subTest(port=port), self.assertRaises(ValueError):
                BoundHistorySource(original, environ=environment, transport_port=port)

    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        parent=Path(temporary.name);self.root=parent/'recovery';self.root.mkdir()
        clock=SimpleNamespace(seconds=lambda:1000.)
        profile=build_read_profile([HISTORY],1000,CONTROL,read_entries([HISTORY]),max_result_bytes=16384,
            read_retention=dict(schema='qmt.read-retention.v1',max_lifetime_ms=5000))
        route=dict(route_id='minute-resume',executor_id='synthetic',route_epoch=1)
        binding=host_binding(route=route,generation='c'*32,host_instance_id='a'*32,journal_generation=None,
            observation_identity=None,capability_sha256=bound.digest(canonical(profile)))
        metadata=dict(schema_version=bound.SCHEMA,binding=binding,binding_sha256=bound.digest(canonical(binding)),
            read_profile_body_b64=bound.b64(canonical(profile)),read_profile_body_sha256=bound.digest(canonical(profile)),
            profile=profile,limits=dict(max_request_bytes=4096,max_result_bytes=16384,
            max_http_request_bytes=65536,max_http_response_bytes=65536),order_ready=False)
        journal=RetainedReadJournal(parent/'retained.sqlite',route,max_records=8,max_result_bytes=16384,
            max_request_bytes=4096,max_journal_bytes=8*(4096+16384+16384),read_profile=profile,clock=clock)
        self.addCleanup(journal.close)
        fixture=SimpleNamespace(args=dict(symbol='000001.SZ',start_time='20261022093100',end_time='20261022100000',max_rows=100),
            old=metadata,active=metadata,journal=journal,calls=[],executions=0)
        def initial_exchange(method,path,body,deadline):
            fixture.calls.append((method,path))
            if path.endswith('/read-binding'):return 200,metadata
            if path.endswith('/read-retention-status'):return 200,journal.retention_status(binding['host_instance_id'])
            if '/bound-operations/'in path:
                envelope=decode(body);request=decode(bound.unb64(envelope['request_body_b64'],4096))
                rid=journal.submit_ticket(canonical(request),binding,envelope['ticket'],queue_timeout_ms=2000)
                journal.claim_bound(binding);fixture.executions+=1
                raise SourcePending('synthetic reply lost after original dispatch')
            if path.endswith('/consumed'):
                rid=path.split('/')[-2];return 200,journal.consumed(rid,decode(body),binding['host_instance_id'])
            if path.endswith('/lookup'):
                rid=path.split('/')[-2];return journal.lookup(rid,decode(body),binding['host_instance_id'])
            if method=='GET'and'/bound-results/'in path:
                result=journal.get_bound(path.rsplit('/',1)[-1]);return 202,result
            raise AssertionError('Unexpected source path')
        transport=SimpleNamespace(exchange=initial_exchange,clock=time.monotonic,rpc_budget=lambda unused:nullcontext())
        transport.plan=lambda *args:BoundHistorySource.plan(transport,*args)
        fixture.transport=transport;fixture.client=RetainedReadClient(transport,clock=clock)
        self.fixture=fixture
        args=fixture.args;code,market=args['symbol'].split('.')
        query=dict(exchange={'SH':'SSE','SZ':'SZSE'}[market],code=code,
                   **{'from':int(args['start_time'][:12]),'to':int(args['end_time'][:12])})
        self.repository=PreparedHistoryRepository(self.root,'a'*64,'qmt.source-history-preparation-receipt.v5',100,partitioned=True)
        unused,self.directory=self.repository.directory(query)
        slot=self.directory/'retained-reads'/('b'*32+'.json');slot.parent.mkdir(parents=True)
        with self.assertRaises(RetainedReadPending):
            fixture.client.read(HISTORY,args,slot,deadline=time.monotonic()+2)
        original=decode(slot.read_bytes())
        self.rid=original['request']['request_id'];self.slot=slot
        self.record=dict(original,retained_slot=str(slot))
        self.state=dict(schema=self.repository.schema,configuration_sha256=self.repository.identity,
            query=query,before=dict(pages=[self.record]),after=None,prepare=None,follow_up=None)
        self.save()
        reads=HistoryReadOperations.__new__(HistoryReadOperations)
        reads.transport=fixture.transport;reads.root=self.root;reads.client=fixture.client
        self.reads=reads
        owner=SourcePreparingMarket.__new__(SourcePreparingMarket)
        owner.owner=threading.get_ident();owner.closed=False;owner.clock=time.monotonic
        owner.c=dict(retained_reads=True,max_bytes=16777216,max_import_attempts=8)
        owner.identity=self.repository.identity;owner.receipt_schema=self.repository.schema
        owner.repository=self.repository;owner._retained_resume_paths=None;owner.reads=reads
        self.owner=owner
        original_exchange=fixture.transport.exchange
        def exchange(method,path,body,deadline):
            if path.endswith('/lookup'):
                fixture.calls.append((method,path))
                return fixture.journal.lookup(self.rid,decode(body),fixture.active['binding']['host_instance_id'])
            return original_exchange(method,path,body,deadline)
        fixture.transport.exchange=exchange
        fixture.calls.clear()

    def save(self):
        (self.directory/'receipt.json').write_bytes(canonical(self.state))

    def complete(self):
        args=self.record['request']['arguments']
        data=dict(schema_version='qmt.history-1m.v1',symbol=args['symbol'],period='1m',
            start_time=args['start_time'],end_time=args['end_time'],max_rows=args['max_rows'],rows=[],coverage='unknown',
            source_options=dict(dividend_type='none',fill_data=False,subscribe=False))
        result=finalize_result(dict(request_id=self.rid,operation_id=HISTORY,ok=True,
            data=data,completed_at='2026-10-30T00:00:00Z'),16384)
        self.fixture.journal.finish_bound(self.rid,result,self.fixture.old['binding'])

    def test_original_terminal_is_consumed_through_owner_without_new_operation(self):
        self.complete()
        result=self.owner.resume_read_responsibility(time.monotonic()+2)
        self.assertEqual(result['state'],'consumed');self.assertEqual(result['request_id'],self.rid)
        saved=decode((self.directory/'receipt.json').read_bytes())['before']['pages'][0]
        self.assertTrue(saved['consumed']);self.assertTrue(decode(self.slot.read_bytes())['consumed'])
        self.assertEqual(self.fixture.executions,1)
        self.assertEqual([path.rsplit('/',1)[-1]for _,path in self.fixture.calls],['lookup','consumed'])

    def test_unknown_original_keeps_identity_and_only_looks_up(self):
        before=self.slot.read_bytes()
        result=self.owner.resume_read_responsibility(time.monotonic()+.05)
        self.assertEqual(result['state'],'pending');self.assertEqual(result['request_id'],self.rid)
        self.assertEqual(self.slot.read_bytes(),before);self.assertEqual(self.fixture.executions,1)
        self.assertTrue(all('/bound-operations/'not in path for _,path in self.fixture.calls))

    def test_unattempted_slot_does_not_submit(self):
        value=decode(self.slot.read_bytes());value['attempted']=False;self.slot.write_bytes(canonical(value))
        result=self.owner.resume_read_responsibility(time.monotonic()+2)
        self.assertEqual(result['state'],'idle');self.assertEqual(self.fixture.calls,[])

    def test_slot_identity_mismatch_fails_before_exchange(self):
        value=decode(self.slot.read_bytes());value['request_body_sha256']='f'*64
        self.slot.write_bytes(canonical(value))
        with self.assertRaises(ValueError):self.owner.resume_read_responsibility(time.monotonic()+2)
        self.assertEqual(self.fixture.calls,[])

    def test_wrong_window_does_not_consume_another_security(self):
        self.state['before']['pages'][0]['request']['arguments']['symbol']='000002.SZ';self.save()
        with self.assertRaises(ValueError):self.owner.resume_read_responsibility(time.monotonic()+2)
        self.assertEqual(self.fixture.calls,[])

    def test_successful_saved_page_reuses_full_validated_result_without_slot_io(self):
        self.complete();self.owner.resume_read_responsibility(time.monotonic()+2)
        record=decode((self.directory/'receipt.json').read_bytes())['before']['pages'][0]
        self.fixture.calls.clear();original=self.slot.read_bytes();self.slot.unlink()
        reply=self.reads.observe(record,lambda:self.fail('unchanged success must not rewrite'),time.monotonic()+2)
        self.assertTrue(reply['ok']);self.assertEqual(self.fixture.calls,[])
        self.slot.write_bytes(original)

    def test_consumed_unknown_preparation_advances_to_readback_with_original_id(self):
        query = self.state['query'] | {'limit': 30}
        preparation = dict(request=dict(operation_id='market.history_prepare',
            arguments=dict(symbol='000001.SZ', period='1m', start_time='20261022093100', end_time='20261022100000')),
            consumed=False)
        self.state.update(prepare=preparation, published=None, empty=False)
        readbacks = []

        def observe(record, save, deadline):
            self.assertIs(record, preparation)
            raise SourcePending('retained original history observation pending')

        def saved_reply(record):
            self.assertIs(record, preparation)
            return dict(ok=False, error_code='preparation_unknown') if record['consumed'] else None

        def read(state, phase, directory, symbol, start, end, deadline):
            if phase == 'before':
                return [], None
            readbacks.append((phase, symbol))
            return [(1, 2)], 'original-binding'

        self.owner._state = lambda query: (None, self.directory, self.state)
        self.owner.follow = None
        self.owner._closed_grid = lambda query: []
        self.owner._reads = read
        self.owner._publish = lambda state, directory, symbol, rows, binding, deadline: state.update(
            published=dict(count=len(rows), binding=binding))
        self.reads.observe = observe
        self.reads.saved_reply = saved_reply
        with self.assertRaises(SourcePending):
            self.owner._window(query, time.monotonic()+2)
        self.assertEqual(readbacks, [])

        preparation.update(consumed=True)
        preparation['request']['request_id'] = self.rid
        self.owner._window(query, time.monotonic()+2)
        self.assertEqual(readbacks, [('after', '000001.SZ')])
        self.assertEqual(self.state['published'], dict(count=1, binding='original-binding'))
        self.assertEqual(preparation['request']['request_id'], self.rid)

    def test_partition_count_retains_directory_and_budget_checks(self):
        self.assertEqual(self.repository.count(), 1)
        another = self.root/'SSE.510300'
        another.mkdir()
        (another/('f'*64)).mkdir()
        self.assertEqual(self.repository.count(), 2)
        self.repository.maximum = 1
        with self.assertRaises(ValueError):
            self.repository.count()
        self.repository.maximum = 100
        (another/('e'*64)).write_bytes(b'not a window directory')
        with self.assertRaises(ValueError):
            self.repository.count()

    def maintenance(self,resume):
        worker=MinuteCollectionMaintenance.__new__(MinuteCollectionMaintenance)
        worker.owner=threading.get_ident();worker.closed=False;worker.clock=time.monotonic
        worker.wall_clock=time.time;worker.next_step=0;worker.cursor=0;worker.symbols=[]
        worker._refresh_metadata=lambda:True;worker._days=lambda now:('2026-10-22',)
        worker.dates=('2026-10-22',);worker.c=dict(interval_seconds=1,batch_size=64,retry_seconds=60)
        key=('SZSE.000001','2026-10-22');worker.jobs=deque([key]);worker.queued={key}
        worker.retry_at={};worker.prefer_retry=True;worker.prefer_retained_resume=True;worker.rows={key:dict(state='missing')}
        worker.producer=SimpleNamespace(c=dict(timeout_seconds=30),resume_read_responsibility=resume)
        return worker,key

    def test_management_loop_hands_back_before_new_source_work(self):
        worker,key=self.maintenance(lambda deadline:dict(state='consumed',request_id=self.rid,scanned_windows=1))
        worker.step(source_ready=True)
        self.assertEqual(list(worker.jobs),[key]);self.assertEqual(worker.queued,{key})
        self.assertEqual(worker.retained_read_resume['request_id'],self.rid)

    def test_source_unavailable_keeps_work_and_does_not_resume(self):
        worker,key=self.maintenance(lambda deadline:self.fail('disconnected source must not exchange'))
        worker.step(source_ready=False)
        self.assertEqual(list(worker.jobs),[key])

    def test_bad_original_is_visible_and_new_work_remains_queued(self):
        def broken(deadline):raise ValueError('synthetic original identity mismatch')
        worker,key=self.maintenance(broken)
        with self.assertRaises(ValueError):worker.step(source_ready=True)
        self.assertEqual(worker.retained_read_resume['state'],'unavailable')
        self.assertEqual(list(worker.jobs),[key])

    def test_continuous_old_responsibility_preserves_retry_and_new_window_turns(self):
        # 历史连续四步都可续核时，仍应让旧窗口重试和新窗口各实际推进一次。
        calls=[]
        def resume(deadline):
            calls.append('resume');return dict(state='pending',request_id=self.rid,scanned_windows=1)
        worker,new_key=self.maintenance(resume)
        now=[100.];worker.clock=lambda:now[0]
        retry_key=('SSE.510300','2026-10-22');worker.retry_at={retry_key:0}
        worker.rows[retry_key]=dict(state='missing')
        worker.producer.c['max_bytes']=4096
        worker.producer.base=SimpleNamespace(expected_minutes=lambda symbol,day:[202610220931])
        worker.producer.repository=SimpleNamespace(find=lambda *args,**kwargs:([],{}))
        def call(request):
            calls.append(request['request']['exchange']+'.'+request['request']['code'])
            return dict(status=dict(code='Pending'),data={})
        worker.producer.call=call
        for unused in range(4):
            worker.step(source_ready=True);now[0]+=2
        self.assertEqual(calls,['resume',retry_key[0],'resume',new_key[0]])
        self.assertNotIn(new_key,worker.queued)

    def test_query_pending_keeps_same_window_and_allows_collection_to_continue(self):
        worker, key = self.maintenance(lambda deadline: dict(state='empty'))
        now = [100.]
        worker.clock = lambda: now[0]
        worker.producer.c['max_bytes'] = 4096
        worker.producer.base = SimpleNamespace(expected_minutes=lambda symbol, day: [202610220931])
        worker.producer.repository = SimpleNamespace(find=lambda *args, **kwargs: (
            [(None, {'published': {'reconciled_day': key[1]}})], {}))
        requests = []

        def query(request):
            requests.append(request)
            if len(requests) == 1:
                raise SourcePending('retained original history observation pending')
            return dict(status=dict(code='Ok'), data={'bars': [{'minute': 202610220931}]})

        worker.producer.call = query
        worker.step(source_ready=True)
        self.assertEqual(worker.rows[key]['recovery_status'], 'source_query_pending')
        self.assertEqual(worker.retry_at, {key: 160.})
        self.assertFalse(worker.closed)
        now[0] = 161.
        worker.step(source_ready=True)
        self.assertEqual(requests[0], requests[1])
        self.assertEqual(worker.rows[key]['state'], 'recovered')

    def test_registry_deadline_keeps_same_symbol_and_date_for_retry(self):
        from integrations.guanheng.source_history_transport import SourcePending
        worker, key = self.maintenance(lambda deadline: dict(state='empty'))
        worker.clock = lambda: 100.
        worker.producer.c['max_bytes'] = 4096
        worker.producer.base = SimpleNamespace(expected_minutes=lambda symbol, day: [202610220931])
        worker.producer.call = lambda request: dict(status=dict(code='Ok'), data={'bars': [{'minute': 202610220931}]})

        def deadline(*args, **kwargs):
            raise SourcePending('source registry deadline')

        worker.producer.repository = SimpleNamespace(find=deadline)
        worker.step(source_ready=True)
        self.assertEqual(worker.rows[key]['recovery_status'], 'source_registry_pending')
        self.assertEqual(worker.retry_at, {key: 160.})
        self.assertFalse(worker.closed)


if __name__=='__main__':unittest.main()
