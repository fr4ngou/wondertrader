"""真实私有文件与原子发布的容量回归；只写E盘测试目录，不启动服务。"""
from pathlib import Path
import tempfile
import unittest

from guanheng_qmt_shm.private_files import write_private_new
from guanheng_qmt_shm_agent.protocol import decode
from integrations.guanheng.collection_projection import PROJECTION_LIMITS, publish_projection
from integrations.guanheng.market_generation import read_fixed, _read_stream


class ProjectionCapacityTests(unittest.TestCase):
    def test_projection_over_two_mib_is_complete_and_consumable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = dict(schema='qmt.collection-minute-maintenance.v1', payload='x'*2097153)
            publish_projection(root,'minute-maintenance.json',value,True)
            body = read_fixed(root/'minute-maintenance.json',maximum=PROJECTION_LIMITS['minute-maintenance.json'])
            self.assertGreater(len(body),2097152)
            self.assertEqual(decode(body),value)
            self.assertEqual(list(root.glob('*.tmp')),[])

    def test_oversized_replacement_preserves_original_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publish_projection(root,'status.json',dict(state='running'),True)
            before = (root/'status.json').read_bytes()
            with self.assertRaises(ValueError):
                publish_projection(root,'status.json',dict(payload='x'*65536),True)
            self.assertEqual((root/'status.json').read_bytes(),before)
            self.assertEqual(list(root.glob('*.tmp')),[])

    def test_open_reader_keeps_old_snapshot_during_large_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publish_projection(root,'minute-maintenance.json',dict(version=1),True)
            target=root/'minute-maintenance.json'
            before=target.read_bytes()
            with _read_stream(target)as old:
                publish_projection(root,'minute-maintenance.json',dict(version=2,payload='x'*2097153),True)
                self.assertEqual(old.read(),before)
            self.assertEqual(decode(read_fixed(target,maximum=PROJECTION_LIMITS['minute-maintenance.json']))['version'],2)

    def test_private_default_and_explicit_maximum_remain_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                write_private_new(root/'ordinary',b'x'*2097153)
            self.assertFalse((root/'ordinary').exists())
            write_private_new(root/'maximum',b'x'*16777216,maximum_bytes=16777216)
            self.assertEqual((root/'maximum').stat().st_size,16777216)
            for maximum in (True,0,16777217):
                with self.assertRaises(ValueError):
                    write_private_new(root/'rejected',b'x',maximum_bytes=maximum)
            self.assertFalse((root/'rejected').exists())
