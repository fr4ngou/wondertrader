"""回测归属目录绑定原完成证明，完整绩效继续按选择独立核验。"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
import unittest
from unittest.mock import patch

from guanheng_app.backtest_archive import BacktestArchive, ArchiveError, SCHEMA, SCOPE


def wire(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('ascii')


def archive(root, run, version='1.2.2', capital='1000000', *, legacy=False):
    directory = root / run
    directory.mkdir()
    session = dict(policy=dict(initial_capital_cny=capital), strategy=dict(strategy_id='fixture', strategy_version=version))
    request = wire(dict(session=session))
    install = wire(dict(schema='fixture-installation'))
    report = dict(schema='nsb-report-v2' if legacy else 'guanheng.retained-replay-report.v1',
                  strategy_id='fixture', strategy_version=version,
                  policy=dict(initial_capital_cny=capital), records=[dict(trading_date=20260105)])
    result = wire(dict(schema='nsh-run-v1', run_id=run, request_sha256=sha256(request).hexdigest(),
                       installation_sha256=sha256(install).hexdigest(), report=report, report_schema=report['schema']))
    receipt = dict(schema=SCHEMA, run_id=run, owner_id='a'*32, request_id='b'*32,
                   request_sha256=sha256(request).hexdigest(), installation_sha256=sha256(install).hexdigest(),
                   result_sha256=sha256(result).hexdigest(), report_sha256=sha256(wire(report)).hexdigest(),
                   record_count=1, pid=1234, exit_code=0, forced=False, pid_reaped=True, pipes_joined=True,
                   elapsed_ms=1, scope=SCOPE, configuration=dict(label='unrelated label 9.9.9', name='fixture',
                       start=202601050930, end=202601051500, session_sha256='c'*64, max_seconds=30))
    for name, raw in [('request.json', request), ('installation.json', install), ('result.json', result),
                      ('completed-archive.json', wire(receipt))]:
        (directory/name).write_bytes(raw)
    return directory, receipt


class SummaryIndexTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.archive = BacktestArchive(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_current_and_legacy_ownership_without_loading_performance(self):
        archive(self.root, '1'*32)
        archive(self.root, '2'*32, version='1.1.2', capital='120000')
        archive(self.root, '3'*32, version='2.0', legacy=True)
        with (patch('guanheng_app.backtest_archive.validate_report_dict', side_effect=AssertionError('full report')),
              patch('guanheng_app.backtest_archive.build_performance', side_effect=AssertionError('full performance'))):
            value = self.archive.list(monotonic()+5, summaries=True)
        self.assertEqual(value['schema'], 'nbw-archive-summary-index-v1')
        self.assertEqual([item['summary']['strategy']['version'] for item in value['runs']], ['1.2.2','1.1.2','2.0'])
        self.assertEqual(value['runs'][1]['summary']['initial_capital_cny'], '120000')
        self.assertEqual(value['invalid_receipts'], 0)
        old = self.archive.list(monotonic()+5)
        self.assertEqual(old['schema'], 'nbw-archive-index-v1')
        self.assertTrue(all('summary' not in item for item in old['runs']))

    def test_changed_original_affects_its_summary_only(self):
        broken, _ = archive(self.root, '1'*32)
        archive(self.root, '2'*32)
        (broken/'request.json').write_bytes(b'{"changed":true}')
        value = self.archive.list(monotonic()+5, summaries=True)
        self.assertEqual(len(value['runs']), 2)
        self.assertIsNone(value['runs'][0]['summary'])
        self.assertEqual(value['runs'][1]['summary']['strategy']['version'], '1.2.2')

    def test_summary_is_not_full_report_qualification(self):
        _directory, receipt = archive(self.root, '1'*32)
        # 合成头部用于目录测试；缺完整报告/原生原件时，所选完整读取继续拒绝。
        value = self.archive.list(monotonic()+5, summaries=True)
        self.assertIsNotNone(value['runs'][0]['summary'])
        with self.assertRaises(ArchiveError):
            self.archive.read('1'*32, sha256(wire(receipt)).hexdigest(), monotonic()+5, performance=True)

    def test_report_bytes_and_declared_identity_remain_bound(self):
        directory, receipt = archive(self.root, '1'*32)
        result = json.loads((directory/'result.json').read_bytes())
        result['report']['strategy_version'] = '9.0'
        changed = wire(result)
        (directory/'result.json').write_bytes(changed)
        # 仅更新外层结果摘要仍不能替换完成证明中固定的报告摘要。
        receipt = deepcopy(receipt)
        receipt['result_sha256'] = sha256(changed).hexdigest()
        (directory/'completed-archive.json').write_bytes(wire(receipt))
        self.assertIsNone(self.archive.list(monotonic()+5, summaries=True)['runs'][0]['summary'])

    def test_original_http_owner_exposes_summary_get_and_keeps_write_closed(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from guanheng_app.backtest_readonly import router
        from guanheng_app.reading import BoundedReader
        archive(self.root, '1'*32)
        app = FastAPI()
        reader = BoundedReader(workers=1, capacity=4)
        app.state.backtest_reader = reader
        app.include_router(router(self.root))
        reader.start()
        try:
            with TestClient(app) as client:
                response = client.get('/v1/ui/backtest/archive-summaries')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['runs'][0]['summary']['strategy']['version'], '1.2.2')
                self.assertEqual(client.get('/v1/ui/backtest/archive-summaries?run=anything').status_code, 422)
                self.assertEqual(client.post('/v1/ui/backtest/archive-summaries', json={}).status_code, 405)
        finally:
            self.assertTrue(reader.close(monotonic()+5))


if __name__ == '__main__':
    unittest.main()
