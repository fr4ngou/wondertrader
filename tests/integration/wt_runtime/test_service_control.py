"""WT 日常启停入口回归；隔离替身只模拟 Runtime 收据，不触碰现场实例。"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from uuid import uuid4

from guanheng_wt_runtime import service_control
from guanheng_wt_runtime.service_control import (
    ServiceConfig,
    ServiceController,
    _process_exists,
    _process_identity,
    _safe_projection,
    validate_current,
)


class QuoteInputStatusTests(unittest.TestCase):
    def test_ready_process_distinguishes_closed_parser_and_recovered_quotes(self):
        from guanheng_wt_runtime.execution_process import _quote_input_state

        observation = dict(schema='guanheng.execution.cta-observation.v1', control_id='control',
                           config_sha256='config', pid=13, closed=False,
                           parser_connects=1, parser_closes=1, parser_quotes=11)
        def observed(value):
            return _quote_input_state(value, 'control', 'config', 13, 1)
        self.assertEqual(observed(observation), 'disconnected')
        self.assertEqual(observed(dict(observation, parser_connects=2, parser_quotes=12)), 'receiving')
        self.assertEqual(observed(dict(observation, parser_closes=0, parser_quotes=0)), 'waiting')
        self.assertEqual(observed(dict(observation, control_id='old')), 'unknown')
        status = dict(ready=True, pid=1, components={'execution': dict(ready=True, quote_input_state=observed(observation))})
        projected = _safe_projection('status', None, status, 'ready', changed=False)
        self.assertEqual(projected['components']['execution'], {'ready': True, 'quote_input_state': 'disconnected'})


def _raw(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def _write(path, value):
    path.write_bytes(_raw(value))
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _FakeProcess:
    def __init__(self):
        self.code = None
        self.pid = os.getpid()

    def poll(self):
        return self.code


class _RuntimeFixture:
    """按正式状态/停止/关闭协议推进两代，记录每次启动身份。"""

    def __init__(self):
        self.processes = []
        self.controls = []
        self.fail_next = False

    def launch(self, command, cwd, environment):
        self.last_environment = environment
        values = {command[index]: command[index + 1] for index in range(len(command) - 1) if command[index].startswith("--")}
        control = Path(values["--control-directory"])
        configuration = Path(values["--config"])
        runtime = json.loads(configuration.read_bytes())
        control.mkdir()
        identity = {
            "control_id": values["--control-id"],
            "instance_id": runtime["instance_id"],
            "configuration_sha256": values["--config-sha256"],
            "pid": os.getpid(),
        }
        component_name = next(iter(runtime["components"]))
        component = {"state": "ready", "ready": True, "error_code": None, "pid": 20000 + len(self.processes)}
        if component_name == "execution":
            native_control = control.parent / ("native-" + values["--control-id"])
            native_control.mkdir()
            descriptor = json.loads(Path(runtime["components"]["execution"]["descriptor"]).read_bytes())
            native_raw = Path(descriptor["configuration"]).read_bytes()
            (native_control / "execution.json").write_bytes(native_raw)
            native_sha = hashlib.sha256(native_raw).hexdigest()
            _write(native_control / "ready.json", {
                "schema": "guanheng.execution.ready.v1", "control_id": native_control.name,
                "config_sha256": native_sha, "pid": component["pid"], "closed": False,
            })
            observation = native_control / "strategies.json"
            _write(observation, {"fixture": True})
            component["business_observation"] = {
                "schema": "guanheng.execution-observation-reference.v1",
                "control_id": native_control.name,
                "config_sha256": native_sha,
                "pid": component["pid"],
                "path": str(observation),
                "ready_path": str(native_control / "ready.json"),
            }
        status = {
            "schema": "guanheng.wt-runtime-status.v1",
            **identity,
            "state": "faulted" if self.fail_next else "ready",
            "error_code": "fixture_failure" if self.fail_next else None,
            "ready": not self.fail_next,
            "components": {component_name: component},
        }
        _write(control / "status.json", status)
        process = _FakeProcess()
        if self.fail_next:
            _write(
                control / "failure.json",
                {
                    "schema": "guanheng.wt-runtime-failure.v1",
                    **identity,
                    "components_closed": True,
                    "error_code": "fixture_failure",
                    "status": "faulted",
                },
            )
            process.code = 2
            self.fail_next = False
        else:
            _write(control / "ready.json", {"schema": "guanheng.wt-runtime-ready.v1", **identity})
        self.processes.append(process)
        self.controls.append((control, identity, status))
        return process

    def sleep(self, unused):
        for index, (control, identity, status) in enumerate(self.controls):
            if (control / "stop.json").exists() and not (control / "closed.json").exists():
                status.update(state="closed", ready=False)
                for component in status["components"].values():
                    component.update(state="closed", ready=False)
                _write(control / "status.json", status)
                _write(
                    control / "closed.json",
                    {
                        "schema": "guanheng.wt-runtime-closed.v1",
                        **identity,
                        "components_closed": True,
                        "error_code": None,
                        "status": "stopped",
                    },
                )
                self.processes[index].code = 0


@unittest.skipUnless(os.name == "nt", "WT 服务锁和路径合同属于 Windows 运行产品")
class ServiceControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="E:/workspace")
        self.root = Path(self.temp.name)
        self.control = self.root / "controls"
        self.generations = self.root / "generations"
        self.public = self.root / "public"
        for path in (self.control, self.generations, self.public):
            path.mkdir()
        self.pythonw = self.root / "pythonw.exe"
        shutil.copyfile(sys.executable, self.pythonw)
        self.host = _write(self.root / "host.json", {"fixture": True})
        self.instance_id = str(uuid4())
        self.runtime = _write(
            self.root / "runtime.json",
            {
                "schema": "guanheng.wt-runtime.v1",
                "instance_id": self.instance_id,
                "startup_seconds": 5,
                "stop_seconds": 5,
                "components": {
                    "host": {
                        "kind": "qmt_read",
                        "descriptor": str(self.host),
                        "sha256": "0" * 64,
                    }
                },
            },
        )
        self.environment = _write(self.root / "environment.json", {"WT_SERVICE_TEST_SECRET": "private"})
        self.current = self.public / "CURRENT.json"
        self.service_path = _write(
            self.root / "service.json",
            {
                "schema": "guanheng.wt-service.v1",
                "pythonw": str(self.pythonw),
                "pythonw_sha256": _sha(self.pythonw),
                "bootstrap_configuration": str(self.runtime),
                "bootstrap_configuration_sha256": _sha(self.runtime),
                "control_root": str(self.control),
                "generation_root": str(self.generations),
                "current_file": str(self.current),
                "environment_file": str(self.environment),
                "environment_sha256": _sha(self.environment),
            },
        )
        self.fixture = _RuntimeFixture()
        self.controller = ServiceController(
            ServiceConfig.from_path(self.service_path),
            launcher=self.fixture.launch,
            sleeper=self.fixture.sleep,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_windows_process_probe_reports_current_process_alive(self):
        self.assertTrue(_process_exists(os.getpid()))
        self.assertFalse(_process_exists(0))

    def test_ready_status_rejects_reused_pid_identity(self):
        code, first = self.controller.start()
        self.assertEqual((code, first["state"]), (0, "ready"))
        generation = self.generations / first["current"]["wt_control_id"]
        owner_path = generation / "runtime-owner.json"
        owner = json.loads(owner_path.read_bytes())
        owner["creation_filetime"] += 1
        _write(owner_path, owner)
        self.assertEqual(self.controller.status()[1]["state"], "process_lost")
        self.assertFalse(self.controller.status()[1]["ready"])
        self.assertEqual(self.controller.start()[1]["state"], "process_lost")

    def test_status_retries_sharing_conflict_without_reporting_startup(self):
        code, first = self.controller.start()
        self.assertEqual((code, first["state"]), (0, "ready"))
        original = service_control.read_status
        remaining = 1

        def busy_once(path, max_bytes):
            nonlocal remaining
            if Path(path) == Path(first["current"]["wt_status_file"]) and remaining:
                remaining -= 1
                raise service_control.CollectionStatusPending()
            return original(path, max_bytes)

        with patch.object(service_control, "read_status", side_effect=busy_once):
            _, result = self.controller.status()
        self.assertEqual((result["state"], result["current"], remaining), ("ready", first["current"], 0))
        with patch.object(service_control, "read_status", side_effect=service_control.CollectionStatusPending) as busy:
            _, result = self.controller.status()
        self.assertEqual((result["state"], result["error_code"], busy.call_count),
                         ("status_read_pending", "status_file_busy", 3))

    def test_start_waits_for_ready_receipt_after_ready_status(self):
        pending = {}

        def launch(command, cwd, environment):
            process = self.fixture.launch(command, cwd, environment)
            control = Path(command[command.index("--control-directory") + 1])
            path = control / "ready.json"
            pending["ready"] = (path, path.read_bytes())
            path.unlink()
            return process

        def sleep(seconds):
            if "ready" in pending:
                path, raw = pending.pop("ready")
                path.write_bytes(raw)
            self.fixture.sleep(seconds)

        controller = ServiceController(self.controller.config, launcher=launch, sleeper=sleep)
        code, result = controller.start()
        self.assertEqual((code, result["state"], result["ready"]), (0, "ready", True))
        self.assertTrue((self.generations / result["current"]["wt_control_id"] / "runtime-owner.json").exists())
        self.assertEqual(controller.stop()[0], 0)

    def test_start_is_idempotent_then_stop_and_restart_same_instance(self):
        code, first = self.controller.start()
        self.assertEqual((code, first["state"], first["changed"]), (0, "ready", True))
        self.assertEqual(self.fixture.last_environment["WT_SERVICE_TEST_SECRET"], "private")
        code, duplicate = self.controller.start()
        self.assertEqual((code, duplicate["state"], duplicate["changed"]), (0, "ready", False))
        self.assertEqual(len(self.fixture.processes), 1)
        code, stopped = self.controller.stop()
        self.assertEqual((code, stopped["state"], stopped["changed"]), (0, "stopped", True))
        code, second = self.controller.start()
        self.assertEqual((code, second["state"], second["changed"]), (0, "ready", True))
        self.assertEqual(len(self.fixture.processes), 2)
        self.assertNotEqual(first["current"]["wt_control_id"], second["current"]["wt_control_id"])
        self.assertEqual(first["current"]["wt_instance_id"], second["current"]["wt_instance_id"])
        self.assertEqual(set(json.loads(self.current.read_bytes())), {
            "schema", "wt_status_file", "wt_control_id", "wt_instance_id", "wt_configuration_sha256"
        })
        code, final = self.controller.stop()
        self.assertEqual((code, final["state"]), (0, "stopped"))

    def test_user_start_hands_failed_generation_to_successor_chain(self):
        self.fixture.fail_next = True
        code, failed = self.controller.start()
        self.assertEqual((code, failed["state"], failed["changed"]), (2, "faulted", True))
        code, repeated = self.controller.start()
        self.assertEqual((code, repeated["state"], repeated["changed"]), (0, "ready", True))
        self.assertNotEqual(failed["current"]["wt_control_id"], repeated["current"]["wt_control_id"])
        self.assertEqual(len(self.fixture.processes), 2)

    def test_public_current_rejects_extra_or_ambiguous_fields(self):
        valid = {
            "schema": "guanheng.wt-current.v1",
            "wt_status_file": str(self.control / str(uuid4()) / "status.json"),
            "wt_control_id": str(uuid4()),
            "wt_instance_id": self.instance_id,
            "wt_configuration_sha256": "1" * 64,
        }
        valid["wt_status_file"] = str(self.control / valid["wt_control_id"] / "status.json")
        self.assertEqual(set(validate_current(valid)), set(valid))
        with self.assertRaises(ValueError):
            validate_current({**valid, "account": "forbidden"})

    def test_current_outside_owned_control_root_is_rejected_before_stop(self):
        foreign = self.root / "foreign" / str(uuid4())
        foreign.mkdir(parents=True)
        value = {
            "schema": "guanheng.wt-current.v1",
            "wt_status_file": str(foreign / "status.json"),
            "wt_control_id": foreign.name,
            "wt_instance_id": self.instance_id,
            "wt_configuration_sha256": _sha(self.runtime),
        }
        _write(self.current, value)
        with self.assertRaises(ValueError):
            self.controller.stop()
        self.assertFalse((foreign / "stop.json").exists())

    def test_normal_restart_rebuilds_execution_recovery_generation(self):
        native = _write(
            self.root / "native.json",
            {"recovery": {"mode": "resume_reconciled", "transition": {"file": str(self.root / "old"), "sha256": "2" * 64}}},
        )
        descriptor = _write(
            self.root / "execution.json",
            {
                "schema": "guanheng.execution-deployment.v1",
                "configuration": str(native),
                "configuration_sha256": _sha(native),
                "initial_inventory": {"fixture": "already_materialized"},
            },
        )
        runtime = _write(
            self.root / "execution-runtime.json",
            {
                "schema": "guanheng.wt-runtime.v1",
                "instance_id": self.instance_id,
                "startup_seconds": 5,
                "stop_seconds": 5,
                "components": {
                    "execution": {"kind": "execution", "descriptor": str(descriptor), "sha256": _sha(descriptor)}
                },
            },
        )
        service_value = json.loads(self.service_path.read_bytes())
        service_value["bootstrap_configuration"] = str(runtime)
        service_value["bootstrap_configuration_sha256"] = _sha(runtime)
        _write(self.service_path, service_value)
        fixture = _RuntimeFixture()
        controller = ServiceController(
            ServiceConfig.from_path(self.service_path), launcher=fixture.launch, sleeper=fixture.sleep
        )
        self.assertEqual(controller.start()[0], 0)
        self.assertEqual(controller.stop()[0], 0)

        with patch.object(controller, "_runtime_owner_active", return_value=False), \
                patch("guanheng_wt_runtime.service_control.require_process_exited"), \
                patch("guanheng_wt_runtime.service_control.prepare_transition") as forbidden:
            self._assert_adoption_rejected(controller)
        forbidden.assert_not_called()

        def prepare(configuration, predecessor_configuration, predecessor_control, destination, **unused):
            self.assertEqual(Path(predecessor_configuration), Path(predecessor_control) / "execution.json")
            self.assertTrue(Path(predecessor_control).name.startswith("native-"))
            value = {"schema": "guanheng.execution-recovery-transition.v1", "fixture": True}
            _write(Path(destination), value)
            return {"file": str(destination), "sha256": _sha(destination)}

        with patch("guanheng_wt_runtime.service_control.prepare_transition", side_effect=prepare) as called:
            code, second = controller.start()
        self.assertEqual((code, second["state"]), (0, "ready"))
        self.assertEqual(called.call_count, 1)
        generation = json.loads((self.generations / second["current"]["wt_control_id"] / "generation.json").read_bytes())
        successor_runtime = json.loads(Path(generation["runtime_configuration"]).read_bytes())
        successor_descriptor = json.loads(Path(successor_runtime["components"]["execution"]["descriptor"]).read_bytes())
        successor_native = json.loads(Path(successor_descriptor["configuration"]).read_bytes())
        self.assertNotIn("initial_inventory", successor_descriptor)
        self.assertEqual(successor_native["recovery"]["transition"]["file"], generation["transition_file"])
        self.assertEqual(successor_runtime["instance_id"], self.instance_id)
        self.assertEqual(controller.stop()[0], 0)

    def _dependency_failure_controller(self, *, fail_runs=(2,), execution_failure=False, incomplete_close=False):
        """真实Runtime串行start/逆序close；只有来源/Native进程为隔离替身。"""
        from types import SimpleNamespace
        from guanheng_wt_runtime.runtime import Runtime, RuntimeConfig
        from guanheng_wt_runtime.execution_process import ManagedPythonExecutionProcess

        native = _write(self.root / "pre-native.json", {"recovery": {"mode": "record_clean"}})
        descriptor = _write(self.root / "pre-execution.json", {
            "schema": "guanheng.execution-deployment.v1", "configuration": str(native),
            "configuration_sha256": _sha(native), "initial_inventory": {"fixture": "original"}})
        value = json.loads(self.runtime.read_bytes())
        value["components"] = {
            "analysis_host": {"kind": "qmt_read", "descriptor": str(self.host), "sha256": "0" * 64},
            "execution": {"kind": "execution", "descriptor": str(descriptor), "sha256": _sha(descriptor)}}
        _write(self.runtime, value)
        service = json.loads(self.service_path.read_bytes())
        service["bootstrap_configuration_sha256"] = _sha(self.runtime)
        _write(self.service_path, service)
        ledger = _write(self.root / "unchanged-ledger.json", {"cash": 1000000, "positions": {"fixture": 100}})
        entries, native_calls = [], []

        class Source:
            def __init__(owner, failed): owner.failed, owner.state = failed, "new"
            def start(owner, deadline): owner.state = "faulted" if owner.failed else "ready"; return not owner.failed
            def request_close(owner): pass
            def close(owner, timeout): owner.state = "closed"; return not (owner.failed and incomplete_close)
            def status(owner): return dict(state=owner.state, ready=owner.state == "ready", error_code=None, pid=None)

        class Execution(ManagedPythonExecutionProcess):
            def start(owner, deadline):
                native_calls.append(owner._control_id)
                if execution_failure and len(entries) + 1 in fail_runs:
                    owner._state = "faulted"; owner._error = "fixture_no_ready"; return False
                owner._directory.mkdir()
                raw = Path(owner.config.configuration).read_bytes()
                (owner._directory / "execution.json").write_bytes(raw)
                owner._host_pid, owner._state = os.getpid(), "ready"
                _write(owner._directory / "ready.json", dict(schema="guanheng.execution.ready.v1",
                    control_id=owner._control_id, config_sha256=_sha(Path(owner.config.configuration)),
                    pid=owner._host_pid, closed=False))
                return True
            def close(owner, timeout=2):
                if owner._host_pid is None: return super().close(timeout)
                owner._state = "closed"; return True

        def launch(command, cwd, environment):
            args = {command[j]:command[j+1] for j in range(len(command)-1) if command[j].startswith("--")}
            directory = Path(args["--control-directory"]); directory.mkdir()
            identity = dict(control_id=args["--control-id"], instance_id=self.instance_id,
                configuration_sha256=args["--config-sha256"], pid=os.getpid())
            def factory(component):
                if component.kind == "qmt_read":return Source(len(entries)+1 in fail_runs and not execution_failure)
                item = json.loads(Path(component.descriptor).read_bytes())
                return Execution(SimpleNamespace(control_root=self.control, configuration=item["configuration"],
                    configuration_sha256=item["configuration_sha256"], stop_seconds=5, startup_seconds=5))
            runtime = Runtime(RuntimeConfig.from_path(args["--config"],args["--config-sha256"]), factory=factory)
            process = _FakeProcess(); success = runtime.start(__import__('time').monotonic()+5)
            if not success:
                closed = runtime.close(5)
                _write(directory / "failure.json", dict(schema="guanheng.wt-runtime-failure.v1", **identity,
                    components_closed=closed, error_code="runtime_failure", status="faulted"))
                process.code = 2
            else:
                _write(directory / "ready.json", dict(schema="guanheng.wt-runtime-ready.v1", **identity))
            _write(directory / "status.json", {**runtime.status(), **identity})
            entries.append((directory, runtime, identity, process))
            return process

        def sleep(unused):
            for directory, runtime, identity, process in entries:
                if (directory / "stop.json").exists() and not (directory / "closed.json").exists():
                    self.assertTrue(runtime.close(5))
                    _write(directory / "status.json", {**runtime.status(), **identity})
                    _write(directory / "closed.json", dict(schema="guanheng.wt-runtime-closed.v1", **identity,
                        components_closed=True, error_code=None, status="stopped"))
                    process.code = 0
        return ServiceController(ServiceConfig.from_path(self.service_path), launcher=launch, sleeper=sleep), entries, native_calls, ledger

    def test_dependency_failure_reuses_original_transition_then_same_start_succeeds(self):
        controller, entries, native_calls, ledger = self._dependency_failure_controller(fail_runs=(2,3), incomplete_close=True)
        ledger_raw = ledger.read_bytes()
        self.assertEqual(controller.start()[0], 0); self.assertEqual(controller.stop()[0], 0)
        def prepare(configuration, previous, control, destination, **unused):
            _write(Path(destination), dict(schema="guanheng.execution-recovery-transition.v1",
                predecessor_configuration=str(previous), predecessor_control_directory=str(control)))
            return dict(file=str(destination), sha256=_sha(Path(destination)))
        with patch("guanheng_wt_runtime.service_control.prepare_transition", side_effect=prepare) as called:
            self.assertEqual(controller.start()[0], 2)
            failed_id = entries[-1][2]["control_id"]
            record = json.loads((self.generations / failed_id / "generation.json").read_bytes())
            transition = Path(record["transition_file"]); raw = transition.read_bytes()
            before = json.loads(Path(record["runtime_configuration"]).read_bytes())["components"]["execution"]
            self.assertEqual(controller.start()[0], 2)
            self.assertEqual(controller.start()[0], 0)
            self.assertEqual(called.call_count, 1)
        latest = json.loads((self.generations / entries[-1][2]["control_id"] / "generation.json").read_bytes())
        self.assertEqual(latest["transition_file"], str(transition))
        after = json.loads(Path(latest["runtime_configuration"]).read_bytes())["components"]["execution"]
        self.assertEqual(before, after)
        self.assertEqual(json.loads(raw)["predecessor_control_directory"], str(self.control / native_calls[0]))
        self.assertEqual(transition.read_bytes(), raw); self.assertEqual(ledger.read_bytes(), ledger_raw)
        self.assertEqual(len(native_calls), 2)
        self.assertTrue(all(item[1].status()["components"]["execution"]["pid"] is None for item in entries[1:3]))
        self.assertEqual(controller.stop()[0], 0)

    def test_execution_start_failure_without_ready_keeps_unknown_and_does_not_reuse(self):
        controller, entries, native_calls, ledger = self._dependency_failure_controller(execution_failure=True)
        self.assertEqual(controller.start()[0], 0); self.assertEqual(controller.stop()[0], 0)
        def prepare(configuration, previous, control, destination, **unused):
            _write(Path(destination), {"schema":"guanheng.execution-recovery-transition.v1"})
            return dict(file=str(destination), sha256=_sha(Path(destination)))
        with patch("guanheng_wt_runtime.service_control.prepare_transition", side_effect=prepare) as called:
            self.assertEqual(controller.start()[0], 2)
            self.assertEqual(len(native_calls), 2)
            with self.assertRaises(ValueError):controller.start()
            self.assertEqual(called.call_count, 1)
        self.assertEqual(len(entries), 2)

    def test_first_start_dependency_failure_preserves_unused_initial_input(self):
        controller, entries, native_calls, ledger = self._dependency_failure_controller(fail_runs=(1,))
        original = ledger.read_bytes()
        self.assertEqual(controller.start()[0], 2)
        with patch("guanheng_wt_runtime.service_control.prepare_transition") as prepare:
            self.assertEqual(controller.start()[0], 0)
            prepare.assert_not_called()
        record = json.loads((self.generations / entries[-1][2]["control_id"] / "generation.json").read_bytes())
        self.assertIsNone(record["transition_file"])
        runtime = json.loads(Path(record["runtime_configuration"]).read_bytes())
        descriptor = json.loads(Path(runtime["components"]["execution"]["descriptor"]).read_bytes())
        self.assertEqual(descriptor["initial_inventory"], {"fixture":"original"})
        self.assertEqual(len(native_calls), 1); self.assertEqual(ledger.read_bytes(), original)
        self.assertEqual(controller.stop()[0], 0)

    def test_bootstrap_prepared_transition_survives_first_dependency_failure(self):
        controller, entries, native_calls, ledger = self._dependency_failure_controller(fail_runs=(1,))
        transition = _write(self.root / "bootstrap-transition.json", {
            "schema":"guanheng.execution-recovery-transition.v1", "predecessor_control_directory":"original-native"})
        native = self.root / "pre-native.json"
        _write(native,{"recovery":{"mode":"resume_reconciled","transition":{"file":str(transition),"sha256":_sha(transition)}}})
        descriptor = self.root / "pre-execution.json"; value = json.loads(descriptor.read_bytes())
        value["configuration_sha256"] = _sha(native); _write(descriptor,value)
        value = json.loads(self.runtime.read_bytes()); value["components"]["execution"]["sha256"] = _sha(descriptor)
        _write(self.runtime,value); value = json.loads(self.service_path.read_bytes())
        value["bootstrap_configuration_sha256"] = _sha(self.runtime); _write(self.service_path,value)
        controller.config = ServiceConfig.from_path(self.service_path)
        raw = transition.read_bytes()
        self.assertEqual(controller.start()[0], 2)
        with patch("guanheng_wt_runtime.service_control.prepare_transition") as prepare:
            self.assertEqual(controller.start()[0], 0); prepare.assert_not_called()
        record = json.loads((self.generations / entries[-1][2]["control_id"] / "generation.json").read_bytes())
        self.assertEqual(record["transition_file"], str(transition))
        self.assertEqual(transition.read_bytes(), raw); self.assertEqual(len(native_calls), 1)
        self.assertEqual(controller.stop()[0], 0)

    def test_missing_execution_resource_proof_rejects_preexecution_reuse(self):
        controller, entries, native_calls, ledger = self._dependency_failure_controller(fail_runs=(1,))
        self.assertEqual(controller.start()[0], 2)
        directory = entries[-1][0]; path = directory / "status.json"; status = json.loads(path.read_bytes())
        status["components"]["execution"].pop("pending"); _write(path,status)
        with self.assertRaises(ValueError):controller.start()
        self.assertEqual(native_calls, [])


    def _history_successor(self, *, before_components=None, after_components=None, change_instance=False):
        """旧代正常关闭、新固定bootstrap；进程协议替身的OS退出由各测试显式替换。"""
        before=json.loads(self.runtime.read_bytes())
        history=dict(kind='source_market',descriptor=str(self.host),sha256=_sha(self.host))
        before['components']=before_components or {'history':history}
        _write(self.runtime,before)
        original=json.loads(self.service_path.read_bytes())
        original['bootstrap_configuration_sha256']=_sha(self.runtime)
        _write(self.service_path,original)
        old=ServiceController(ServiceConfig.from_path(self.service_path),launcher=self.fixture.launch,sleeper=self.fixture.sleep)
        first=old.start()[1];self.assertEqual(old.stop()[0],0)
        successor={**before,'components':after_components or {'history':{**history,'descriptor':str(self.root/'new-history.json')}}}
        if change_instance:successor['instance_id']=str(uuid4())
        new_runtime=_write(self.root/'new-runtime.json',successor)
        new_service=_write(self.root/'new-service.json',{**original,'bootstrap_configuration':str(new_runtime),
            'bootstrap_configuration_sha256':_sha(new_runtime)})
        controller=ServiceController(ServiceConfig.from_path(new_service),launcher=self.fixture.launch,sleeper=self.fixture.sleep)
        return controller,first,new_runtime

    def _assert_adoption_rejected(self,controller):
        """拒绝必须发生在生成后继或启动来源之前，保留公开指针及原代目录。"""
        original=self.current.read_bytes() if self.current.exists() else None
        generations=set(self.generations.iterdir());launches=len(self.fixture.processes)
        with self.assertRaises((ValueError,FileNotFoundError)):
            controller.adopt_bootstrap()
        self.assertEqual(self.current.read_bytes() if self.current.exists() else None,original)
        self.assertEqual(set(self.generations.iterdir()),generations)
        self.assertEqual(len(self.fixture.processes),launches)

    def test_history_explicit_adoption_and_default_predecessor_restore(self):
        controller,first,new_runtime=self._history_successor()
        ordinary=controller.start()[1]
        generation=json.loads((self.generations/ordinary['current']['wt_control_id']/'generation.json').read_bytes())
        ordinary_value=json.loads(Path(generation['runtime_configuration']).read_bytes())
        self.assertEqual(ordinary_value['components']['history']['descriptor'],str(self.host))
        self.assertEqual(controller.stop()[0],0)
        with patch.object(controller,'_runtime_owner_active',return_value=False), \
                patch('guanheng_wt_runtime.service_control.require_process_exited') as exited:
            code,adopted=controller.adopt_bootstrap()
        self.assertEqual((code,adopted['action'],adopted['state']),(0,'adopt-bootstrap','ready'))
        self.assertEqual(exited.call_args.args,(os.getpid(),))
        record=json.loads((self.generations/adopted['current']['wt_control_id']/'generation.json').read_bytes())
        self.assertEqual(record['runtime_configuration'],str(new_runtime))
        self.assertEqual(record['predecessor_control_id'],ordinary['current']['wt_control_id'])
        self.assertEqual(first['current']['wt_instance_id'],adopted['current']['wt_instance_id'])
        self.assertEqual(controller.stop()[0],0)
        resumed=controller.start()[1]
        record=json.loads((self.generations/resumed['current']['wt_control_id']/'generation.json').read_bytes())
        self.assertEqual(json.loads(Path(record['runtime_configuration']).read_bytes())['components']['history']['descriptor'],str(self.root/'new-history.json'))
        self.assertEqual(controller.stop()[0],0)

    def test_adoption_requires_prior_normal_close_and_exited_owner(self):
        self._assert_adoption_rejected(self.controller)
        controller,first,_=self._history_successor()
        # 协议替身ready绑定本测试活PID；closed本身不能证明进程已退出。
        self._assert_adoption_rejected(controller)
        with patch.object(controller,'_runtime_owner_active',return_value=False), \
                patch('guanheng_wt_runtime.service_control.require_process_exited',side_effect=ValueError('unknown_exit')):
            self._assert_adoption_rejected(controller)
        owner=self.generations/first['current']['wt_control_id']/'runtime-owner.json'
        owner.unlink()
        self._assert_adoption_rejected(controller)

    def test_adoption_rejects_running_faulted_and_incomplete_close(self):
        controller,first,_=self._history_successor()
        control=Path(first['current']['wt_status_file']).parent
        closed=(control/'closed.json').read_bytes()
        (control/'closed.json').unlink()
        self._assert_adoption_rejected(controller)
        (control/'closed.json').write_bytes(closed)
        failure=json.loads(closed);failure.update(schema='guanheng.wt-runtime-failure.v1',status='faulted',error_code='fixture_failure')
        _write(control/'failure.json',failure)
        self._assert_adoption_rejected(controller)
        (control/'failure.json').unlink()
        value=json.loads(closed);value['components_closed']=False;_write(control/'closed.json',value)
        self._assert_adoption_rejected(controller)
        value['components_closed']=True;value['pid']+=1;_write(control/'closed.json',value)
        self._assert_adoption_rejected(controller)

    def test_adoption_rejects_foreign_instance_before_generation(self):
        controller,_,_=self._history_successor(change_instance=True)
        self._assert_adoption_rejected(controller)

    def test_adoption_rejects_non_history_and_mixed_components(self):
        history=dict(kind='source_market',descriptor=str(self.host),sha256=_sha(self.host))
        host=dict(kind='qmt_read',descriptor=str(self.host),sha256=_sha(self.host))
        for before,after in [({'host':host},{'history':history}),
                             ({'history':history},{'host':host}),
                             ({'history':history},{'execution':dict(kind='execution',descriptor=str(self.host),sha256=_sha(self.host))}),
                             ({'history':history},{'host':host,'history':history})]:
            with self.subTest(before=list(before),after=list(after)):
                # 每次保留已有代，helper仅为下一次造显式新旧隔离协议代。
                if self.current.exists():self.current.unlink()
                controller,_,_=self._history_successor(before_components=before,after_components=after)
                with patch.object(controller,'_runtime_owner_active',return_value=False), \
                        patch('guanheng_wt_runtime.service_control.require_process_exited'):
                    self._assert_adoption_rejected(controller)

    def test_adoption_rejects_changed_bootstrap_sha_and_sanitizes_cli(self):
        controller,_,runtime=self._history_successor()
        runtime.write_bytes(runtime.read_bytes()+b' ')
        with patch.object(controller,'_runtime_owner_active',return_value=False), \
                patch('guanheng_wt_runtime.service_control.require_process_exited'):
            self._assert_adoption_rejected(controller)
        from guanheng_wt_runtime.service_control import main
        output=io.StringIO()
        with patch('guanheng_wt_runtime.service_control.ServiceConfig.from_path',return_value=controller.config), \
                patch('guanheng_wt_runtime.service_control.ServiceController',return_value=controller),redirect_stdout(output):
            self.assertEqual(main(['adopt-bootstrap','--service-config',str(self.service_path)]),2)
        value=json.loads(output.getvalue())
        self.assertEqual((value['action'],value['state'],value['changed']),('adopt-bootstrap','control_error',False))
        self.assertNotIn('private',output.getvalue())




class WindowsProcessIdentityTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows进程句柄生命周期")
    def test_exited_process_with_retained_handle_is_not_alive(self):
        # 父进程继续持有Popen句柄时，Windows仍能返回子进程创建时间；须同时核退出状态。
        self.assertIsNotNone(_process_identity(os.getpid()))
        child = subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", "pass"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            self.assertEqual(child.wait(timeout=10), 0)
            self.assertIsNone(_process_identity(child.pid))
        finally:
            child.wait(timeout=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
