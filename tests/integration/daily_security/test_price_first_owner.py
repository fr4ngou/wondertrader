"""常驻价格主链独立于公共辅助事实；原失败任务与重试回执保持。"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from integrations.guanheng.daily_data_service import serve
from guanheng_app.observation.source_fetch import SourceFailure


class PriceFirstOwnerTests(unittest.TestCase):
    def fixture(self,root,scope=True):
        data=root/'data';data.mkdir();publication=root/'publication';publication.mkdir()
        if scope:(publication/'CURRENT.json').write_text('{}')  # 价格阶段被替身接管；只声明已有基线，未将其当真实行情。
        calendar=root/'calendar.json';calendar.write_text('{}')
        config=dict(schema='guanheng.daily-data-service.v1',directory=str(data),raw_store=str(root/'raw'),
            template=dict(schema='guanheng.daily-data-update.v1',publication_directory=str(publication),
                          calendar=dict(path=str(calendar),sha256=hashlib.sha256(b'{}').hexdigest())),
            inputs=dict(connections=dict(batch={},hpr={}),public_facts=dict(source={},allowed_hosts=[],
                seconds=30,max_requests=1,max_bytes=1,response_bytes=1,timeout_seconds=1),
                cache_from='20260701',max_rows=40,source_kind='sdk-synthetic'),
            schedule=dict(timezone='Asia/Shanghai',at='09:00',poll_seconds=.1),cycle_seconds=60,retry_seconds=1)
        if scope:config['price_scope']=dict(baseline_reference={},reference_connection=None,
            scope={},authorized_from='20260701',maximum_history_rows=2000)
        path=root/'daily.json';raw=json.dumps(config).encode();path.write_bytes(raw)
        return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()),config

    def test_auxiliary_failure_keeps_prices_published_and_original_task(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);descriptor,config=self.fixture(root);calls=[]
            def prices(*args,**kwargs):
                calls.append('prices')
                return dict(current_sha256='a'*64,price_result={'path':'synthetic-price-result','sha256':'b'*64},
                            continuation_required=False,auxiliary_observation_date='2026-11-04')
            def auxiliary(*args,**kwargs):
                calls.append('auxiliary');raise SourceFailure('synthetic_aux_unavailable')
            control=str(uuid4())
            with patch('integrations.guanheng.daily_price_refresh.price_refresh',side_effect=prices),\
                 patch('integrations.guanheng.daily_data_service.prepare_update',side_effect=auxiliary):
                with self.assertRaisesRegex(RuntimeError,'one cycle failed'):
                    serve(descriptor,root/control,control,once=True,as_of='2026-11-05')
            self.assertEqual(calls,['prices','auxiliary'])
            status=json.loads((root/control/'status.json').read_bytes())
            index=json.loads((Path(config['directory'])/'INDEX.json').read_bytes())['2026-11-05']
            self.assertEqual(status['last_price_success'],'2026-11-05')
            self.assertEqual(status['auxiliary_observation_date'],'2026-11-04')
            self.assertEqual(index['price_state'],'published')
            self.assertEqual(index['state'],'failed')
            self.assertEqual(index['error_type'],'SourceFailure')
            self.assertEqual(Path(index['request']).parent,Path(config['directory'])/'2026-11-05')

    def test_baostock_daily_timeout_keeps_frozen_inputs_and_price_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor, config = self.fixture(root)
            durable = Path(config['directory'])/'CONFIGURATION.json'
            durable.write_text(json.dumps(config))
            candidate = deepcopy(config)
            candidate['inputs']['public_facts']['baostock_daily_timeout_seconds'] = 60
            body = json.dumps(candidate).encode()
            Path(descriptor['path']).write_bytes(body)
            descriptor['sha256'] = hashlib.sha256(body).hexdigest()

            def prices(actual, *_args, **_kwargs):
                self.assertEqual(actual, config)
                return dict(current_sha256='a'*64, price_result={'path':'synthetic-price-result','sha256':'b'*64},
                            continuation_required=False, auxiliary_observation_date='2026-11-04')

            def auxiliary(actual, *_args, **kwargs):
                self.assertEqual(actual, config)
                self.assertEqual(kwargs['baostock_daily_timeout_seconds'], 60)
                raise SourceFailure('synthetic_aux_unavailable')

            control = str(uuid4())
            with patch('integrations.guanheng.daily_price_refresh.price_refresh', side_effect=prices) as price, \
                    patch('integrations.guanheng.daily_data_service.prepare_update', side_effect=auxiliary) as source:
                with self.assertRaisesRegex(RuntimeError, 'one cycle failed'):
                    serve(descriptor, root/control, control, once=True, as_of='2026-11-05')
            price.assert_called_once()
            source.assert_called_once()
            self.assertEqual(json.loads(durable.read_bytes()), config)

    def test_baostock_daily_timeout_is_clamped_by_original_collection_budget(self):
        from guanheng_app.observation.baostock_source import BaostockClient
        from guanheng_app.observation.source_fetch import CollectionBudget

        client = BaostockClient.__new__(BaostockClient)
        client.timeout = 20
        client.constants = SimpleNamespace(MESSAGE_SPLIT='|', BAOSTOCK_CLIENT_VERSION='00.0.00',
                                           MESSAGE_TYPE_GETKDaily_D_AStock_REQUEST='95',
                                           BAOSTOCK_PER_PAGE_COUNT=100)
        client.budget = CollectionBudget(132, max_requests=4, max_bytes=1000, response_bytes=1000)
        observed = []
        client.socket = SimpleNamespace(settimeout=observed.append, sendall=lambda _: None, recv=lambda _: b'')
        with patch('guanheng_app.observation.source_fetch.time.monotonic', return_value=100):
            with self.assertRaisesRegex(SourceFailure, 'pb_incomplete_response'):
                client._message('00', 'login', ['anonymous'])
            self.assertEqual(observed, [20, 20])
            observed.clear()
            with self.assertRaisesRegex(SourceFailure, 'pb_incomplete_response'):
                client.table('stock_daily_batch', '2026-11-11', request_timeout=60)
            self.assertEqual(observed, [32, 32])
            observed.clear()
            with self.assertRaisesRegex(SourceFailure, 'pb_invalid_timeout'):
                client.table('stock_basic', request_timeout=60)
            self.assertEqual(observed, [])

    def test_default_without_full_price_scope_keeps_original_path(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);descriptor,_=self.fixture(root,scope=False);control=str(uuid4())
            with patch('integrations.guanheng.daily_price_refresh.price_refresh')as prices,\
                 patch('integrations.guanheng.daily_data_service.prepare_update',side_effect=SourceFailure('synthetic')):
                with self.assertRaises(RuntimeError):serve(descriptor,root/control,control,once=True,as_of='2026-11-05')
            prices.assert_not_called()

    def test_full_task_continuation_preserves_and_advances_price_responsibility(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);descriptor,config=self.fixture(root);data=Path(config['directory'])
            old=data/'2026-11-05'/'REQUEST.json';old.parent.mkdir();old.write_text('{}')
            price=old.parent/'price-first'/'r000'/'REQUEST.json';price.parent.mkdir(parents=True);price.write_text('{}')
            index={'2026-11-05':dict(request=str(old),state='published',continuation_required=True,
                price_request=str(price),price_state='published',price_revision=0,price_continuation_required=True)}
            (data/'INDEX.json').write_text(json.dumps(index));calls=[]
            def prices(*args,**kwargs):
                calls.append((args[2],kwargs['previous_requests']))
                return dict(current_sha256='a'*64,price_result={'path':'synthetic-price-result','sha256':'b'*64},
                            continuation_required=False,auxiliary_observation_date='2026-11-04')
            def prepare(*args,**kwargs):
                out=Path(args[2]);out.mkdir(parents=True);path=out/'UPDATE.json';path.write_text('{}')
                return dict(path=str(path),sha256=hashlib.sha256(b'{}').hexdigest())
            control=str(uuid4())
            with patch('integrations.guanheng.daily_price_refresh.price_refresh',side_effect=prices),\
                 patch('integrations.guanheng.daily_data_service.prepare_update',side_effect=prepare),\
                 patch('integrations.guanheng.daily_data_service.run_update',return_value=dict(current_sha256='b'*64,continuation_required=False)):
                serve(descriptor,root/control,control,once=True,as_of='2026-11-05')
            final=json.loads((data/'INDEX.json').read_bytes())['2026-11-05']
            self.assertEqual(calls[0][0],price.parent.parent/'r001')
            self.assertIn(str(price),calls[0][1])
            self.assertEqual(final['price_history_requests'],[str(price)])
            self.assertEqual(final['price_revision'],1)
            self.assertEqual(final['history_requests'],[str(old)])
            self.assertFalse(final['continuation_required'])

    def test_existing_full_transaction_keeps_its_parent_until_publication(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);descriptor,config=self.fixture(root);data=Path(config['directory'])
            old=data/'2026-11-05'/'REQUEST.json';old.parent.mkdir();old.write_text('{}')
            price=old.parent/'price-first'/'r000'/'REQUEST.json';price.parent.mkdir(parents=True);price.write_text('{}')
            index={'2026-11-05':dict(request=str(old),state='failed',
                price_request=str(price),price_state='published',price_revision=0,price_continuation_required=True)}
            state=old.parent/'work'/'STATE.json';state.parent.mkdir();state.write_text(json.dumps(dict(stages=dict(parent=dict(current_sha256='c'*64)))))
            (data/'INDEX.json').write_text(json.dumps(index));calls=[]
            def prices(*args,**kwargs):
                calls.append(args[2])
                return dict(current_sha256='a'*64,price_result={'path':'synthetic-price-result','sha256':'b'*64},
                            continuation_required=True,auxiliary_observation_date='2026-11-04')
            control=str(uuid4())
            with patch('integrations.guanheng.daily_price_refresh.price_refresh',side_effect=prices),\
                 patch('integrations.guanheng.daily_data_service.prepare_update')as prepare,\
                 patch('integrations.guanheng.daily_data_service.run_update',return_value=dict(current_sha256='b'*64,continuation_required=False)):
                serve(descriptor,root/control,control,once=True,as_of='2026-11-05')
            prepare.assert_not_called()
            final=json.loads((data/'INDEX.json').read_bytes())['2026-11-05']
            self.assertEqual(calls,[])
            self.assertEqual(final['price_revision'],0)
            self.assertEqual(final['state'],'published')
            self.assertTrue(final['continuation_required'])

    def test_retained_transaction_without_price_receipt_finishes_original_cas_first(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);descriptor,config=self.fixture(root);data=Path(config['directory'])
            old=data/'2026-11-05'/'REQUEST.json';old.parent.mkdir();old.write_text('{}')
            state=old.parent/'work'/'STATE.json';state.parent.mkdir();state.write_text(json.dumps(dict(stages=dict(parent=dict(current_sha256='c'*64)))))
            (data/'INDEX.json').write_text(json.dumps({'2026-11-05':dict(request=str(old),state='failed')}))
            control=str(uuid4())
            with patch('integrations.guanheng.daily_price_refresh.price_refresh')as prices,\
                 patch('integrations.guanheng.daily_data_service.run_update',return_value=dict(current_sha256='b'*64,continuation_required=False)):
                serve(descriptor,root/control,control,once=True,as_of='2026-11-05')
            prices.assert_not_called()
            self.assertEqual(json.loads((data/'INDEX.json').read_bytes())['2026-11-05']['state'],'published')

    def test_twelve_merged_price_revisions_keep_reader_depth_and_original_baseline(self):
        from integrations.guanheng.daily_price_update import compact_price_base
        from integrations.guanheng.market_snapshot_prepare import compose_static_archive
        from integrations.guanheng_market_client import strict_json
        reader=dict(library='synthetic-reader',sha256='a'*64)
        baseline=dict(mode='source-collected',base=dict(mode='source-catalog',stores=[],native_reader=reader))
        base=deepcopy(baseline);retired=[];depths=[]
        for revision in range(12):
            base=compact_price_base(base,retired)
            for kind in ('none','front_ratio'):
                archive=dict(path='synthetic-%02d-%s.json'%(revision,kind),sha256=hashlib.sha256(('%s:%s'%(revision,kind)).encode()).hexdigest())
                base=compose_static_archive(base,archive,reader);retired.append(archive)
            self.assertEqual(strict_json(json.dumps(base).encode()),base)
            node=base;depth=0
            while 'base'in node:depth+=1;node=node['base']
            depths.append(depth)
            self.assertEqual(compact_price_base(base,retired),baseline)
        self.assertEqual(set(depths),{3})


class ContinuousFactsRetryTests(unittest.TestCase):
    def test_old_failures_do_not_exhaust_continuous_owner_forever(self):
        from guanheng_app.observation.ashare_public import Archive
        archive=Archive.__new__(Archive);archive.now=datetime(2026,11,5,8,tzinfo=timezone.utc)
        archive.retry_seconds=60;archive.max_attempts=8;archive.retry_window_seconds=480
        rows=[dict(started_at=(archive.now-timedelta(minutes=20+i)).isoformat())for i in range(8)]
        archive.receipts=lambda *args,**kwargs:rows
        saved=[];archive.record=lambda *args,**kwargs:saved.append((args,kwargs))
        archive.attempt('ashare_capture','2026-11-05')
        self.assertEqual(len(saved),1)
        self.assertEqual(len(rows),8)
        archive.retry_window_seconds=None
        with self.assertRaises(Exception):archive.attempt('ashare_capture','2026-11-05')


if __name__=='__main__':unittest.main()
