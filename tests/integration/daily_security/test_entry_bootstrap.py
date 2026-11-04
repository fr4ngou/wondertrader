"""真实入口导入顺序与独立CLI能力；新子进程不预热SDK且不启动服务。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


class EntryBootstrapTests(unittest.TestCase):
    def test_package_helper_import_does_not_shadow_installed_sdk(self):
        script = '''
import sys
from pathlib import Path
import integrations.guanheng
root=Path(sys.argv[1])
integrations.guanheng.__path__.insert(0,str(root/'integrations/guanheng'))
before=list(sys.path)
import integrations.guanheng.quote_collection_service
assert sys.path==before, 'package import changed host search paths'
import integrations.guanheng.source_market_service
import guanheng_market_client
from guanheng_market_client.exchange_calendar import official_calendar
from guanheng_app.observation.calendars import closed_day_cutoff
assert str(root/'integrations')not in sys.path
assert Path(guanheng_market_client.__file__).parent.name=='guanheng_market_client'
print('fresh SMP import and shared calendar available')
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(ROOT)],
                cwd=directory, capture_output=True, text=True, timeout=30,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_direct_script_help_keeps_isolated_entry_support(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-I', '-B', str(ROOT/'integrations/guanheng/quote_collection_service.py'), '--help'],
                cwd=directory, capture_output=True, text=True, timeout=30,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('usage:', result.stdout)


if __name__ == '__main__':
    unittest.main()
