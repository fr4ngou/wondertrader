"""原完成目录副本上的发布故障与CLI语义；只替代路径绑定校验，无Native执行。"""
import argparse
from contextlib import redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
from time import monotonic
from unittest import TestCase, TestLoader, TextTestRunner
from unittest.mock import Mock, patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir()
    from guanheng_wt_runtime import backtest_completion as B, backtest_cli as CLI
    from guanheng_wt_runtime.strategy_host import HostResult, HostError, _encode
    original = json.loads((args.run/B.RECEIPT).read_bytes())
    raw_report = _encode(json.loads((args.run/'result.json').read_bytes())['report']).decode('ascii')
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    fixed = {p: sha(p) for p in args.run.rglob('*') if p.is_file()}

    class Publication(TestCase):
        def setUp(self):
            self.root = args.work/self._testMethodName
            self.root.mkdir()
            self.directory = self.root/args.run.name
            shutil.copytree(args.run, self.directory)
            self.result = HostResult(original['run_id'], 'completed', 'QA original completed result',
                original['request_sha256'], original['installation_sha256'], str(self.directory), raw_report,
                original['pid'], 0, False, True, True, original['elapsed_ms'])
            # 副本目录不同；只在发布故障测试替代原父端的路径会话摘要校验。
            # 400期实跑主链使用真实_result，不替代该方法。
            self.verifier = patch.object(B.StrategyHost, '_result', return_value=raw_report)
            self.verifier.start()
            self.addCleanup(self.verifier.stop)

        def publish(self, **kw):
            values = dict(label=original['configuration']['label'],
                max_seconds=original['configuration']['max_seconds'],
                deadline=monotonic()+30)
            values.update(kw)
            return B.publish_completed(self.result, self.root, **values)

        def unpublished(self):
            (self.directory/B.RECEIPT).unlink()

        def pending(self):
            return list(self.directory.glob('.archive-*.pending'))

        def test_same_completion_is_idempotent(self):
            before = {p: sha(p) for p in self.directory.rglob('*') if p.is_file()}
            self.assertEqual(self.publish(), sha(self.directory/B.RECEIPT))
            self.assertEqual(before, {p: sha(p) for p in self.directory.rglob('*') if p.is_file()})

        def test_conflict_preserves_original_proof(self):
            target = self.directory/B.RECEIPT
            before = target.read_bytes()
            with self.assertRaises(HostError):
                self.publish(label='Different frozen label')
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(self.pending(), [])

        def test_incomplete_parent_never_publishes(self):
            self.unpublished()
            good = self.result
            for fields in [dict(status='incomplete'), dict(forced=True), dict(exit_code=1),
                           dict(pid_reaped=False), dict(pipes_joined=False), dict(pid=True)]:
                self.result = replace(good, **fields)
                with self.assertRaises(HostError):
                    self.publish()
            self.assertFalse((self.directory/B.RECEIPT).exists())
            self.assertEqual(self.pending(), [])

        def test_expired_original_deadline_never_writes(self):
            self.unpublished()
            with self.assertRaises(HostError):
                self.publish(deadline=monotonic()-1)
            self.assertEqual(self.pending(), [])

        def test_wrong_request_identity_never_writes(self):
            self.unpublished()
            path = self.directory/'request.json'
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(HostError):
                self.publish()
            self.assertEqual(self.pending(), [])

        def test_total_entries_include_empty_directories(self):
            self.unpublished()
            for index in range(8193):
                (self.directory/('capacity-'+str(index))).mkdir()
            with self.assertRaisesRegex(HostError, '目录项|容量'):
                self.publish(deadline=monotonic()+120)
            self.assertFalse((self.directory/B.RECEIPT).exists())
            self.assertEqual(self.pending(), [])

        def test_hard_link_never_publishes(self):
            self.unpublished()
            os.link(self.directory/'request.json', self.directory/'extra-hard-link.json')
            with self.assertRaises(HostError):
                self.publish()
            self.assertEqual(self.pending(), [])

        def test_rename_failure_preserves_pending(self):
            self.unpublished()
            with patch.object(B.os, 'rename', side_effect=OSError('QA rename refused')):
                with self.assertRaises(OSError):
                    self.publish()
            self.assertEqual(len(self.pending()), 1)
            self.assertFalse((self.directory/B.RECEIPT).exists())

        def test_fsync_failure_preserves_pending(self):
            self.unpublished()
            with patch.object(B.os, 'fsync', side_effect=OSError('QA fsync refused')):
                with self.assertRaises(OSError):
                    self.publish()
            self.assertEqual(len(self.pending()), 1)
            self.assertFalse((self.directory/B.RECEIPT).exists())

        def test_final_readback_failure_keeps_published_file(self):
            self.unpublished()
            real = B._read
            def fail(path, maximum, deadline):
                if path.name == B.RECEIPT:
                    raise OSError('QA final readback unavailable')
                return real(path, maximum, deadline)
            with patch.object(B, '_read', side_effect=fail):
                with self.assertRaises(OSError):
                    self.publish()
            self.assertTrue((self.directory/B.RECEIPT).is_file())
            self.assertEqual(self.pending(), [])

        def test_racing_same_proof_is_confirmed(self):
            self.unpublished()
            def race(source, target):
                target.write_bytes(source.read_bytes())
                raise FileExistsError('QA same proof race')
            with patch.object(B.os, 'rename', side_effect=race):
                self.assertEqual(self.publish(), sha(self.directory/B.RECEIPT))
            self.assertEqual(self.pending(), [])

        def test_cli_noncanonical_file_uses_normalized_request_identity(self):
            # 原HostResult替身只用于无Native回归；输入格式变化不能产生第二份会话身份。
            self.unpublished()
            request = json.loads((self.directory/'request.json').read_bytes())
            input_path = self.root/'operator-input.json'
            input_path.write_text(json.dumps(request['session'], indent=2), encoding='utf8')
            self.assertNotEqual(sha(input_path), request['session_sha256'])
            holder = Mock()
            holder.run.return_value = self.result
            frozen = request['backtest']
            argv = ['--binding', str(self.directory/'installation.json'), '--binding-sha256', 'a'*64,
                '--work-root', str(self.root), '--session', str(input_path),
                '--start', str(frozen['start']), '--end', str(frozen['end']),
                '--name', frozen['name'], '--archive-label', original['configuration']['label'],
                '--seconds', str(original['configuration']['max_seconds'])]
            output = io.StringIO()
            with patch.object(CLI, 'StrategyHost', return_value=holder), redirect_stdout(output):
                code = CLI.main(argv)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())['archive']['status'], 'available')
            proof = json.loads((self.directory/B.RECEIPT).read_bytes())
            self.assertEqual(proof['configuration']['session_sha256'], request['session_sha256'])
            self.assertEqual(holder.run.call_count, 1)

        def test_cli_archive_failure_keeps_execution_completed(self):
            holder = Mock()
            holder.run.return_value = self.result
            argv = ['--binding', str(self.directory/'installation.json'), '--binding-sha256', 'a'*64,
                '--work-root', str(self.root), '--session', str(self.directory/'request.json'),
                '--start', '202501010930', '--end', '202610281500', '--archive-label', 'QA']
            output = io.StringIO()
            with patch.object(CLI, 'StrategyHost', return_value=holder), \
                 patch.object(CLI, 'publish_completed', side_effect=OSError('QA storage failure')), \
                 redirect_stdout(output):
                code = CLI.main(argv)
            value = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(value['status'], 'completed')
            self.assertTrue(value['pid_reaped'] and value['pipes_joined'])
            self.assertEqual(value['archive']['status'], 'unknown')
            self.assertEqual(holder.run.call_count, 1)

        def test_default_cli_receipt_retains_original_shape(self):
            holder = Mock()
            holder.run.return_value = self.result
            argv = ['--binding', str(self.directory/'installation.json'), '--binding-sha256', 'a'*64,
                '--work-root', str(self.root), '--session', str(self.directory/'request.json'),
                '--start', '202501010930', '--end', '202610281500']
            output = io.StringIO()
            with patch.object(CLI, 'StrategyHost', return_value=holder), \
                 patch.object(CLI, 'publish_completed', side_effect=AssertionError('unexpected publication')), \
                 redirect_stdout(output):
                code = CLI.main(argv)
            self.assertEqual(code, 0)
            self.assertEqual(set(json.loads(output.getvalue())), {'schema', *CLI._RESULT_FIELDS})

    result = TextTestRunner(verbosity=1).run(TestLoader().loadTestsFromTestCase(Publication))
    assert all(sha(p) == identity for p, identity in fixed.items())
    value = dict(passed=result.wasSuccessful(), tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), new_native_calls=0, real_broker_calls=0, original_drift=0,
        verification_scope='publication faults on copies; original path-bound financial verifier substituted')
    (args.work/'RESULT.json').write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')
    assert result.wasSuccessful()


if __name__ == '__main__':
    main()
