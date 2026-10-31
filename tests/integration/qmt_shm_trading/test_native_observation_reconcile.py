"""原Common私有恢复接缝错误分类；真实签名loopback、原D与回调回收，SDK0。"""
import ctypes
import os
from pathlib import Path
import time
import unittest

from guanheng_qmt_shm_agent.protocol import canonical, decode
from test_native_event_context import _ContextServer
from test_native_trade_client_faults import _LOADED_DLLS


class ReconcileServer(_ContextServer):
    def response(self, method, path, raw):
        code, body, action = super().response(method, path, raw)
        if method != 'GET' or path != '/internal/v1/trade-status' or code != 200:
            return code, body, action
        value = decode(body); source = value['source_status']
        later = self.status_reads >= 2
        unknown = later and self.context_mode == 'unresolved'
        hard = {'code': 'synthetic_hard_fault'} if later and self.context_mode == 'hard' else None
        closing = later and self.context_mode == 'closed'
        available = hard is None and not closing
        source.update(schema_version='qmt.trade-source-status.v2', unknown_fenced=unknown,
                      hard_fault=hard, closing=closing, write_admission=available and not unknown,
                      cancel_admission=available)
        value.update(schema_version='qmt.trade-host-status.v2', unknown_fenced=unknown,
                     hard_fault=hard, closing=closing, accepting_commands=available and not unknown,
                     cancel_admission=available)
        return code, canonical(value), action


@unittest.skipUnless(os.name == 'nt' and os.environ.get('QMT_NATIVE_OBSERVATION_RECONCILE_DLL'),
                     'requires explicitly built Common observation DLL')
class NativeObservationReconcileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dll = ctypes.CDLL(str(Path(os.environ['QMT_NATIVE_OBSERVATION_RECONCILE_DLL']).resolve(strict=True)))
        _LOADED_DLLS.append(cls.dll)
        cls.call = cls.dll.gh_qmt_observation_reconcile_case
        cls.call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_uint]
        cls.call.restype = ctypes.c_int

    def case(self, mode, expected):
        server = ReconcileServer(mode, time.monotonic()+20)
        try:
            server.start(); output = ctypes.create_string_buffer(4096)
            result = self.call(('http://127.0.0.1:'+str(server.http.server_port)).encode(),
                               server.private_sha.encode(), mode.encode(), output, len(output))
            self.assertEqual(result, 0)
            value = decode(output.value)
            self.assertTrue(value['same_deadline'] and value['drained'])
            self.assertTrue(value[expected], value)
            self.assertEqual(value['unknown'], mode == 'unresolved')
            self.assertEqual(value['accepting'], mode == 'success')
            self.assertTrue(all(verb == 'GET' for verb, unused, body in server.requests))
            self.assertFalse(server.errors)
        finally:
            server.close()

    def test_transport_and_deadline_keep_actual_failure(self):
        for mode, expected in [('after-status-fail', 'io_error'), ('after-status-timeout', 'timeout'),
                               ('after-source-change', 'stale')]:
            with self.subTest(mode=mode): self.case(mode, expected)

    def test_success_unresolved_hard_fault_and_close_remain_distinct(self):
        for mode, expected in [('success','ok'), ('unresolved','unknown'), ('hard','conflict'), ('closed','unavailable')]:
            with self.subTest(mode=mode): self.case(mode, expected)
