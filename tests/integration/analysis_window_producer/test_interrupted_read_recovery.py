"""AWP 在旧代纯读取中断后以新认证全量重采。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from guanheng_analysis_window_producer.source import BoundAnalysisClient, SourcePending, SourceUnavailable
from guanheng_qmt_shm import bound
from guanheng_qmt_shm_agent.protocol import canonical, decode
from integrations.guanheng.source_history_transport import BoundHistorySource

from test_close_admission import CAP, CONFIG, ENV, Wire


class InterruptedReadRecovery(unittest.TestCase):
    def test_original_consumed_interruption_requires_matching_new_epoch(self):
        fixtures = Path(__file__).parent/'fixtures/close_retained'
        original = json.loads((fixtures/'159780.SZ-factor.json').read_bytes())
        terminal = original['result']
        reply = decode(bound.unb64(terminal['result_body_b64'], original['limits']['max_result_bytes']))
        reply.update(ok=False, error_code='operation_interrupted', data=None)
        del reply['result_sha256']
        reply['result_sha256'] = bound.digest(canonical(reply))
        raw_reply = canonical(reply)
        terminal.update(result_body_b64=bound.b64(raw_reply), result_body_sha256=bound.digest(raw_reply))
        original['consumed'] = True
        original_bytes = canonical(original)
        request = original['request']
        operation, args = request['operation_id'], request['arguments']
        wire = Wire('close_retained', True)

        def read(slot):
            client = BoundAnalysisClient(dict(CONFIG, read_retention=CAP), environ=ENV)
            return client.read(operation, args, slot, deadline=time.monotonic()+5)

        with TemporaryDirectory() as folder, patch.object(
                BoundHistorySource, 'exchange', lambda owner, *args: wire.exchange(owner, *args)):
            root = Path(folder)
            old = root/'old'
            old.mkdir()
            slot = old/'factor.json'
            slot.write_bytes(original_bytes)
            binding_file = old/'BINDING.json'
            binding_file.write_bytes((fixtures/'BINDING.json').read_bytes())
            marker = old/'SUPERSEDED.json'
            with self.assertRaises(SourcePending):
                read(slot)
            self.assertFalse(marker.exists())

            binding = wire.metadata['binding']
            binding['host_instance_id'] = 'a'*32
            binding['transport_generation'] = 'c'*32
            wire.metadata['binding_sha256'] = bound.digest(canonical(binding))
            missing = dict(original, result=None, received_at=None, consumed=False)
            slot.write_bytes(canonical(missing))
            with self.assertRaises(SourcePending):
                read(slot)
            self.assertFalse(marker.exists())
            self.assertEqual(wire.lookups, [request['request_id']])
            slot.write_bytes(original_bytes)

            binding['route']['route_epoch'] += 1
            wire.metadata['binding_sha256'] = bound.digest(canonical(binding))
            with self.assertRaises(SourcePending):
                read(slot)
            self.assertFalse(marker.exists())
            binding['route'] = original['binding']['route'].copy()
            wire.metadata['binding_sha256'] = bound.digest(canonical(binding))

            with self.assertRaisesRegex(SourceUnavailable, 'analysis_source_epoch_interrupted'):
                read(slot)
            marker_bytes = marker.read_bytes()
            self.assertEqual(json.loads(marker_bytes)['request_id'], request['request_id'])
            self.assertEqual(slot.read_bytes(), original_bytes)
            self.assertEqual(binding_file.read_bytes(), (fixtures/'BINDING.json').read_bytes())
            self.assertEqual(wire.posts, [])
            with self.assertRaises(SourceUnavailable):
                read(slot)
            self.assertEqual(marker.read_bytes(), marker_bytes)
            invalid = dict(json.loads(marker_bytes), new_binding_sha256='?'*64)
            marker.write_bytes(canonical(invalid))
            with self.assertRaisesRegex(ValueError, 'analysis_superseded_identity'):
                read(slot)
            marker.write_bytes(marker_bytes)

            fresh = root/'fresh'/'factor.json'
            fresh.parent.mkdir()
            with self.assertRaises(SourcePending):
                read(fresh)
            current = read(fresh)
            self.assertNotEqual(current['request_id'], request['request_id'])
            self.assertEqual(wire.posts, [current['request_id']])
            self.assertEqual(slot.read_bytes(), original_bytes)


if __name__ == '__main__':
    unittest.main()
