"""原进程丢失恢复已接收，策略就绪前零执行失败的回归。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch
from uuid import uuid4

from guanheng_wt_runtime.execution_recovery import initialization_abort_origin


def save(path, value):
    raw = json.dumps(value, sort_keys=True).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


class InitializationAbortTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[4])
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.origin = self.root / str(uuid4())
        self.abort = self.root / str(uuid4())
        self.origin.mkdir()
        self.abort.mkdir()
        self.config = {"output_directory": str(self.root), "budget": {"run_ms": 0},
                       "trader": {"writes_enabled": True, "expected_account": "fixture"}}
        source_sha = save(self.origin / "execution.json", self.config)
        self.source_identity = dict(control_id=self.origin.name, config_sha256=source_sha, pid=1001)
        binding_sha = save(self.origin / "python-binding.json", {"files": []})
        ready_sha = save(self.origin / "ready.json", dict(self.source_identity,
                         schema="guanheng.execution.ready.v1"))
        self.loss = dict(self.source_identity, schema="guanheng.execution.owner-loss.v1",
                         reason="process_lost", ready_sha256=ready_sha)
        save(self.origin / "owner-loss.json", self.loss)
        save(self.origin / "installation-identity.json", dict(self.source_identity,
             schema="guanheng.execution-installation.v1", installation_sha256="a" * 64))
        self.state = {"portfolio/datas.json": "1" * 64}
        old = self.root / "old-transition.json"
        old_sha = save(old, dict(schema="guanheng.execution-recovery-transition.v1",
            predecessor_control_directory=str(self.origin),
            predecessor_configuration=str(self.origin / "execution.json"),
            predecessor_configuration_sha256=source_sha, predecessor_python_binding_sha256=binding_sha,
            predecessor_installation_sha256="a" * 64, successor_installation_sha256="b" * 64,
            state_files=self.state))
        abort_sha = save(self.abort / "execution.json", dict(self.config, recovery={
            "mode": "resume_reconciled", "transition": {"file": str(old), "sha256": old_sha}}))
        identity = dict(control_id=self.abort.name, config_sha256=abort_sha, pid=1002)
        admission = self.abort / "reconciled.json"
        admission_sha = save(admission, dict(identity, schema="guanheng.cta-reconciled.v1",
            admission_kind="process_lost_reconciled", predecessor_control_id=self.origin.name,
            transition_sha256=old_sha, state_files=self.state, successor_installation_sha256="b" * 64))
        self.claim = self.root / (".cta-reconciled-" + old_sha + ".json")
        self.claim.write_bytes(admission.read_bytes())
        self.failure = dict(identity, schema="guanheng.execution.failure.v1", stage="cta", closed=False,
            execution_queue=dict(fault=0, accepting=False, inflight=False, accepted=0, entered=0,
                                 delivered=0, rejected=0, queued_commands=0, payload_bytes=0))
        save(self.abort / "failure.json", self.failure)
        save(self.abort / "close-prepared.json", dict(identity, schema="guanheng.execution.close-prepared.v1",
                                                     closed=True, ok=False, recovery_ready=False))
        self.transition = dict(predecessor_control_directory=str(self.abort), predecessor_configuration_sha256=abort_sha,
            predecessor_installation_sha256="b" * 64, state_files=self.state,
            initialization_abort={"file": str(admission), "sha256": admission_sha})

    def test_zero_effect_abort_returns_original_financial_owner(self):
        with patch("guanheng_wt_runtime.execution_recovery.require_process_exited") as exited:
            original = initialization_abort_origin(self.transition, current=self.config)
        self.assertEqual(original["control_directory"], self.origin)
        self.assertEqual(original["configuration"], self.config)
        self.assertEqual(exited.call_args_list, [call(1002), call(1001)])

    def assert_rejected(self, current=None):
        with patch("guanheng_wt_runtime.execution_recovery.require_process_exited"), self.assertRaises(ValueError):
            initialization_abort_origin(self.transition, current=self.config if current is None else current)

    def test_started_or_ready_rejected(self):
        for receipt in ("ready.json", "lifecycle-started.json"):
            with self.subTest(receipt=receipt):
                path = self.abort / receipt
                path.write_bytes(b"{}")
                self.assert_rejected()
                path.unlink()

    def test_nonzero_or_incomplete_queue_rejected(self):
        queue = self.failure["execution_queue"]
        for change in ({"entered": 1}, {"accepted": True}, {"inflight": True}):
            with self.subTest(change=change):
                save(self.abort / "failure.json", dict(self.failure, execution_queue=dict(queue, **change)))
                self.assert_rejected()
        incomplete = dict(queue)
        incomplete.pop("entered")
        save(self.abort / "failure.json", dict(self.failure, execution_queue=incomplete))
        self.assert_rejected()

    def test_changed_durable_claim_rejected(self):
        self.claim.write_bytes(b"{}")
        self.assert_rejected()

    def test_mismatched_owner_loss_rejected(self):
        save(self.origin / "owner-loss.json", dict(self.loss, ready_sha256="f" * 64))
        self.assert_rejected()

    def test_changed_trader_or_state_rejected(self):
        self.assert_rejected(dict(self.config, trader=dict(self.config["trader"], writes_enabled=False)))
        self.transition["state_files"] = {"portfolio/datas.json": "9" * 64}
        self.assert_rejected()
