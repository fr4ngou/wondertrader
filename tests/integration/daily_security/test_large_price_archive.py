from pathlib import Path
import hashlib
import json

from integrations.guanheng.daily_data_stages import prepare_directory
from integrations.guanheng.daily_data_update import _descriptor, _load
from integrations.guanheng.source_archive_identity import DAILY_ARCHIVE_MANIFEST_BYTES


def test_completed_large_price_archive_survives_retry_capacity(tmp_path):
    # 重现生产任务已有完成清单、后继尝试中断且本阶段尝试额度已用完。
    attempts = [f'{index:032x}' for index in range(16)]
    completed = tmp_path / f'price-archive-{attempts[0]}'
    completed.mkdir()
    manifest = completed / 'archive.json'
    body = b'{"schema":"guanheng.daily-native-archive.v1","entries":[]}' + b' ' * (17 * 1024 * 1024)
    manifest.write_bytes(body)
    stage = tmp_path / 'PHASE-price-archive.json'
    stage.write_text(json.dumps(dict(schema='guanheng.daily-immutable-stage.v1',
                                    name='price-archive', attempts=attempts, result=None)), encoding='utf8')

    def restore(directory: Path):
        result = _descriptor(directory / 'archive.json', DAILY_ARCHIVE_MANIFEST_BYTES)
        assert _load(result, DAILY_ARCHIVE_MANIFEST_BYTES)['entries'] == []
        return result

    def build(directory):
        raise AssertionError(f'已有完成原件时不应重建 {directory}')

    result = prepare_directory(tmp_path, 'price-archive', 'archive.json', build, restore, recover_prior=True)
    assert result == dict(path=str(manifest), sha256=hashlib.sha256(body).hexdigest())
    assert json.loads(stage.read_bytes())['result_attempt'] == attempts[0]
