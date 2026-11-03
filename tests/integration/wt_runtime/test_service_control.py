"""WT 日常启停入口回归；隔离替身只模拟 Runtime 收据，不触碰现场实例。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from guanheng_wt_runtime.service_control import (
    ServiceConfig,
    ServiceController,
    _process_exists,
    _process_identity,
    validate_current,
)


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
