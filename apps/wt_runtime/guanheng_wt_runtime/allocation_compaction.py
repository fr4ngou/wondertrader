"""离线归并分账收件，同时保留原始证据。"""
from __future__ import annotations

import hashlib
from contextlib import closing
from pathlib import Path
import sqlite3
from .account_allocation import AccountAllocation, _wire
from .allocation_records import broker_receipt_key, ensure_broker_receipt_index


# 交易事实和既有证明逐行保持。映射库可从旧序号反查候选、原始记录及其历史证明。
UNCHANGED_TABLES = ('asa_identity', 'asa_book', 'asa_record', 'asa_events', 'asa_source_proof', 'asa_conflicts')


def _check_integrity(db):
    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise ValueError('allocation database integrity check failed')


def compact(source, output):
    """只读连接原库，候选通过全部核验后生成完成收据。"""
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir()
    archive_path = output / 'original.sqlite3'
    candidate_path = output / 'account-allocation.sqlite3'
    mapping_path = output / 'receipt-map.sqlite3'
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as live, closing(
            sqlite3.connect(archive_path)) as archive, closing(sqlite3.connect(candidate_path)) as candidate, closing(
            sqlite3.connect(mapping_path)) as mapping:
        live.backup(archive)
        _check_integrity(archive)
        archive.backup(candidate)
        ensure_broker_receipt_index(candidate)
        mapping.execute('CREATE TABLE receipt (original_sequence INTEGER PRIMARY KEY, original_event_id TEXT UNIQUE, '
                        'retained_sequence INTEGER NOT NULL, retained_event_id TEXT NOT NULL)')
        # 同一业务状态但不同应用结果保留各自证据。正常收件优先绑定已应用代表。
        representatives = {}
        primary = {}
        removed = 0
        with mapping, candidate:
            candidate.execute('UPDATE asa_inbox SET receipt_key=NULL WHERE receipt_key IS NOT NULL')
            for sequence, event_id, kind, raw, digest, source_sha, applied, reason in archive.execute(
                    'SELECT sequence,event_id,kind,raw_json,payload_sha256,source_sha256,applied,reason '
                    'FROM asa_inbox ORDER BY sequence'):
                expected, body = AccountAllocation._event_payload(event_id, kind, bytes(raw), source_sha, with_payload=True)
                if digest != expected:
                    raise ValueError(f'original receipt checksum mismatch at sequence {sequence}')
                key = broker_receipt_key(kind, body, _wire)
                if key is None:
                    continue
                state = (key, applied, reason)
                retained = representatives.setdefault(state, (sequence, event_id))
                if retained[0] != sequence:
                    candidate.execute('DELETE FROM asa_inbox WHERE sequence=?', (sequence,))
                    mapping.execute('INSERT INTO receipt VALUES(?,?,?,?)', (sequence, event_id, *retained))
                    removed += 1
                    continue
                previous = primary.get(key)
                if previous is None or (applied and not previous[1]):
                    primary[key] = (sequence, applied)
            candidate.executemany('UPDATE asa_inbox SET receipt_key=? WHERE sequence=?',
                                  ((key, value[0]) for key, value in primary.items()))
        candidate.execute('VACUUM')
        _check_integrity(candidate)
        candidate.execute('ATTACH DATABASE ? AS original', (str(archive_path),))
        for table in UNCHANGED_TABLES:
            for first, second in (('main', 'original'), ('original', 'main')):
                if candidate.execute(f'SELECT * FROM {first}.{table} EXCEPT '
                                     f'SELECT * FROM {second}.{table} LIMIT 1').fetchone():
                    raise ValueError(f'allocation migration changed {table}')
        before = archive.execute('SELECT count(*) FROM asa_inbox').fetchone()[0]
        after = candidate.execute('SELECT count(*) FROM asa_inbox').fetchone()[0]
        if before - after != removed or mapping.execute('SELECT count(*) FROM receipt').fetchone()[0] != removed:
            raise ValueError('allocation receipt mapping incomplete')
        _check_integrity(mapping)
    def sha256(path):
        result = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                result.update(block)
        return result.hexdigest()

    report = {
        'original_receipts': before, 'candidate_receipts': after, 'mapped_duplicates': removed,
        'original_bytes': archive_path.stat().st_size, 'candidate_bytes': candidate_path.stat().st_size,
        'mapping_bytes': mapping_path.stat().st_size, 'unchanged_tables': UNCHANGED_TABLES,
        'sha256': {path.name: sha256(path) for path in (archive_path, candidate_path, mapping_path)},
    }
    (output / 'verified.json').write_text(_wire(report) + '\n', encoding='ascii')
    return report
