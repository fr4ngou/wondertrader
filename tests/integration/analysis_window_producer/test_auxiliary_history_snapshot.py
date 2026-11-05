"""官方历史接缝根因回归；原件/时钟均为隔离样本，不调用QMT或账户。"""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from guanheng_analysis_window_producer.auxiliary_history import (load_history_snapshot,
    fill_history, MAX_BYTES)
from guanheng_analysis_window_producer.runtime import AnalysisWindowProducer
from guanheng_strategy_v1.auxiliary import AuxiliaryPublication


def publication(kind='turnover', day='2020-01-02', value=123., symbol=None):
    return dict(kind=kind,statistic_date=day,value=value,available_at=None,
        received_at='2026-01-01T00:00:00+00:00',source_sha256='1'*64,symbol=symbol)


def document():
    return dict(schema='guanheng.auxiliary-history-publications.v1',
        qualification='official_observed',historical_first_available='unknown',
        publications=[publication()],source_delivery_sha256='2'*64,
        generated_at='2026-01-01T01:00:00+00:00')


class OfficialHistory(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)

    def reference(self, value=None, raw=None):
        path=self.root/'history.json'
        path.write_bytes(raw if raw is not None else json.dumps(value or document(),allow_nan=True).encode())
        return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def owner(self, reference=None):
        artifact=self.root/'artifact.bin'
        artifact.write_bytes(b'isolated-native-reference-not-executed')
        descriptor=dict(path=str(artifact),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
        return AnalysisWindowProducer(object(),directory=self.root/'producer',
            publication=self.root/'published.json',artifacts={k:descriptor for k in ['helper','reader','probe']},
            python=sys.executable,worker_cwd=str(self.root),source_identity=dict(kind='isolated'),
            auxiliary_history_snapshot=reference)

    def test_current_complete_keys_and_revisions_win_history_only_fills_missing(self):
        value=document()
        value['publications'] += [publication('margin',value=500.),
            publication('shares',value=200.,symbol='510300.SH'),publication('shares',value=300.,symbol='510050.SH')]
        snapshot=load_history_snapshot(self.reference(value))
        received=datetime(2026,2,1,tzinfo=timezone.utc)
        current=(AuxiliaryPublication('turnover',date(2020,1,2),999.,None,received,'3'*64),
                 AuxiliaryPublication('shares',date(2020,1,2),250.,None,received,'4'*64,'510300.SH'))
        result,coverage=fill_history(current,snapshot,days={date(2020,1,2)},symbols={'510300.SH'})
        found={(p.kind,p.symbol):p for p in result}
        self.assertIs(found[('turnover',None)],current[0])
        self.assertIs(found[('shares','510300.SH')],current[1])
        self.assertEqual(found[('margin',None)].value,500.)
        self.assertNotIn(('shares','510050.SH'),found)
        self.assertEqual(coverage['imported_publications'],1)
        self.assertEqual(coverage['applicable_publications'],3)
        self.assertFalse(coverage['continuous_source_updated'])

    def test_exact_hash_rechecked_after_atomic_replacement(self):
        reference=self.reference()
        load_history_snapshot(reference)
        replacement=self.root/'replacement.json'
        replacement.write_text(json.dumps(dict(document(),source_delivery_sha256='3'*64)),encoding='utf8')
        replacement.replace(Path(reference['path']))
        with self.assertRaisesRegex(ValueError,'auxiliary_history_snapshot_identity'):
            load_history_snapshot(reference)

    def test_top_protocol_fields_and_research_rejected(self):
        mutations=[lambda v:v.update(qualification='research_only'),
            lambda v:v.update(historical_first_available='assumed'),
            lambda v:v.update(extra=True),lambda v:v.update(schema='different'),
            lambda v:v.update(source_delivery_sha256='not-a-hash'),
            lambda v:v.update(publications=[])]
        for mutate in mutations:
            value=document();mutate(value)
            with self.subTest(value=value),self.assertRaises(ValueError):
                load_history_snapshot(self.reference(value))

    def test_publication_fields_numbers_dates_clocks_and_duplicates_rejected(self):
        changes=[dict(available_at='2020-01-03T01:25:00+00:00'),dict(value=True),dict(value=0.),
            dict(value=-1.),dict(value=float('inf')),dict(value=float('nan')),dict(value=10**500),
            dict(kind='research'),dict(statistic_date='20200102'),dict(received_at='2026-01-01'),
            dict(received_at='2027-01-01T00:00:00+00:00'),dict(statistic_date='2026-01-02'),
            dict(source_sha256='X'*64),dict(symbol='510300.SH'),dict(extra='unsupported')]
        for change in changes:
            value=document();value['publications'][0].update(change)
            with self.subTest(change=str(change)[:80]),self.assertRaises(ValueError):
                load_history_snapshot(self.reference(value))
        value=document();value['publications'] *= 2
        with self.assertRaises(ValueError):
            load_history_snapshot(self.reference(value))

    def test_duplicate_json_keys_and_capacity_rejected(self):
        raw=json.dumps(document()).replace('"qualification":', '"qualification":"research_only","qualification":').encode()
        with self.assertRaisesRegex(ValueError,'duplicate_field'):
            load_history_snapshot(self.reference(raw=raw))
        reference=self.reference()
        with Path(reference['path']).open('wb') as stream:
            stream.seek(MAX_BYTES);stream.write(b'x')
        with self.assertRaisesRegex(ValueError,'snapshot_file'):
            load_history_snapshot(reference)

    def test_future_or_unaware_generation_rejected(self):
        for generated in ['2999-01-01T00:00:00+00:00','2026-01-01T01:00:00','2025-01-01T00:00:00+00:00']:
            value=document();value['generated_at']=generated
            with self.subTest(generated=generated),self.assertRaises(ValueError):
                load_history_snapshot(self.reference(value))

    def test_config_reference_bound_and_changed_snapshot_cannot_reuse_owner(self):
        reference=self.reference()
        owner=self.owner(reference)
        with patch.object(AnalysisWindowProducer,'_run',lambda self:None):
            owner.start(deadline=time.monotonic()+10)
            self.assertTrue(owner.close(5))
        original=(self.root/'producer/CONFIGURATION.json').read_bytes()
        second=self.reference(dict(document(),source_delivery_sha256='3'*64))
        changed=self.owner(second)
        with self.assertRaisesRegex(ValueError,'analysis_configuration_conflict'):
            changed.start(deadline=time.monotonic()+10)
        self.assertEqual((self.root/'producer/CONFIGURATION.json').read_bytes(),original)

    def test_research_rejected_at_construction_before_any_owner_state(self):
        value=document();value['qualification']='research_only'
        with self.assertRaises(ValueError):
            self.owner(self.reference(value))
        self.assertFalse((self.root/'producer').exists())

    def test_no_snapshot_default_identity_and_duplicate_current_is_rejected(self):
        self.assertNotIn('auxiliary_history_snapshot',self.owner()._configuration)
        snapshot=load_history_snapshot(self.reference())
        item=snapshot.publications[0]
        with self.assertRaisesRegex(ValueError,'duplicate_auxiliary_publication'):
            fill_history((item,item),snapshot,days={item.statistic_date},symbols={'510300.SH'})


if __name__=='__main__':
    unittest.main()
