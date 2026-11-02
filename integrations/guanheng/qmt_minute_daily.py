"""将完整QMT分钟标签组交给原WT聚合并导入来源日线。

WT负责OHLC/量额聚合与DSB编码；适配器负责240个连续交易标签准入。
09:30附加来源记录原样参与。标签组完整、交易日日历覆盖、分钟边界、
物理单位和历史可获知时刻分别核实。
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import ctypes as C
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import stat

from .native_history import NativeHistory, WTSBar, BAR_CALLBACK, COUNT_CALLBACK, LOG_CALLBACK
from .qmt_minute_import import _Native, _digest, _read, _pairs, _write_json, import_dataset


MANDATORY_LABELS = frozenset(list(range(9*60+31, 11*60+31)) + list(range(13*60+1, 15*60+1)))
# 09:29是标签聚合坐标，首槽容纳可选09:30记录，避免原生无符号零分钟
# 减一溢出。全部准入标签映射到15:00结束的241槽bar；真实开市时间保持09:30。
LABEL_GRID = dict(offset=0, auction=None, sections=[dict(**{'from':929, 'to':1130}),
                                                       dict(**{'from':1300, 'to':1500})])
FIELDS = ('open', 'high', 'low', 'close', 'volume', 'amount')


def select_sessions(bars, start, end):
    """返回完整标签日和逐日排除原因；缺分钟保持实际缺项。"""
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start > end:
        raise ValueError('daily selection is reversed')
    grouped = defaultdict(list)
    previous = None
    for bar in bars:
        if previous is not None and bar.occurred_at <= previous:
            raise ValueError('minute input must be unique and increasing')
        previous = bar.occurred_at
        if start <= bar.occurred_at.date() <= end:
            grouped[bar.occurred_at.date().isoformat()].append(bar)
    admitted, excluded = {}, []
    for day, rows in sorted(grouped.items()):
        labels = {b.occurred_at.hour*60+b.occurred_at.minute for b in rows}
        missing = MANDATORY_LABELS-labels
        extra = labels-(MANDATORY_LABELS | {9*60+30})
        if missing or extra or len(labels) != len(rows):
            excluded.append(dict(date=day, records=len(rows), missing_labels=sorted(missing),
                                 unexpected_labels=sorted(extra), reason='incomplete_session_label_grid'))
        else:
            admitted[day] = rows
    return admitted, excluded


def _native_rows(sessions):
    rows = []
    for day, bars in sessions.items():
        numeric = int(day.replace('-', ''))
        for bar in bars:
            value = WTSBar()
            value.date = numeric
            value.time = (numeric-19900000)*10000 + bar.occurred_at.hour*100+bar.occurred_at.minute
            for source, native in zip(FIELDS, ('open', 'high', 'low', 'close', 'vol', 'money')):
                setattr(value, native, getattr(bar, source))
            rows.append(value)
    return rows


def aggregate_native(native, path, sessions):
    """同步调用原WT重采样；回调内复制数据并逐日核对输入六字段。"""
    native.write_verify(path, _native_rows(sessions))
    library = native.lib
    library.resample_bars.argtypes = [C.c_char_p, BAR_CALLBACK, COUNT_CALLBACK,
        C.c_uint64, C.c_uint64, C.c_char_p, C.c_uint32, C.c_char_p, LOG_CALLBACK, C.c_bool]
    library.resample_bars.restype = C.c_uint32
    counts, observed, events, failures = [], [], [], []

    @COUNT_CALLBACK
    def count(value):
        counts.append(value)

    @BAR_CALLBACK
    def receive(pointer, length, last):
        try:
            if not pointer or length == 0 or len(observed)+length > len(sessions):
                raise ValueError('native daily callback count')
            observed.extend(WTSBar.from_buffer_copy(pointer[i]) for i in range(length))
            events.append(bool(last))
        except Exception:
            failures.append(True)

    first, last = next(iter(sessions)), next(reversed(sessions))
    returned = library.resample_bars(os.fsencode(path), receive, count,
        int(first.replace('-', '')+'0000'), int(last.replace('-', '')+'2359'),
        b'm1', 241, json.dumps(LABEL_GRID).encode('ascii'), LOG_CALLBACK(lambda unused:None), False)
    if failures or counts != [len(sessions)] or returned != len(sessions) or len(observed) != len(sessions) or events != [True]:
        raise ValueError('native daily aggregation callback mismatch')
    output = []
    for (day, bars), value in zip(sessions.items(), observed):
        numeric = int(day.replace('-', ''))
        if value.date != numeric or value.time != (numeric-19900000)*10000+1500:
            raise ValueError('native daily aggregation date mismatch')
        # 独立计算只作核对；输出值来自上面的原WT重采样回调。
        expected = (bars[0].open, max(b.high for b in bars), min(b.low for b in bars),
                    bars[-1].close, sum(b.volume for b in bars), sum(b.amount for b in bars))
        actual = tuple(getattr(value, field) for field in ('open','high','low','close','vol','money'))
        if actual != expected:
            raise ValueError('native daily aggregation value mismatch')
        output.append(dict(date=day, **dict(zip(FIELDS, actual))))
    return output


def convert(configuration, output_root):
    """同步生成新来源仓；失败保留本次目录，成功收据由原导入器最后发布。

调用者提供固定路径/摘要、证券和日期范围；只读原仓，不连接SDK/网络。
Reader、Helper和回调由本线程持有，finally关闭；已有输出根拒绝重用。
    """
    config_raw = _read(Path(configuration), 4*1024*1024)
    config = json.loads(config_raw, object_pairs_hook=_pairs)
    if set(config) != {'schema','minute_store','receipt_sha256','native_reader','helper','selection'} or config['schema'] != 'guanheng.qmt-minute-daily.v1':
        raise ValueError('daily conversion configuration fields')
    selection = config['selection']
    if type(selection) is not list or not 1 <= len(selection) <= 10000:
        raise ValueError('daily selection count')
    if any(set(item) != {'symbol','start','end'} for item in selection) or len({item['symbol'] for item in selection}) != len(selection):
        raise ValueError('daily selection fields or duplicates')
    source = Path(config['minute_store']).resolve(strict=True)
    receipt_path = source/'qmt-import.json'
    receipt_raw = _read(receipt_path, 4*1024*1024)
    if hashlib.sha256(receipt_raw).hexdigest() != config['receipt_sha256']:
        raise ValueError('minute receipt identity mismatch')
    receipt = json.loads(receipt_raw, object_pairs_hook=_pairs)
    if receipt['schema_version'] != 2 or receipt['status'] != 'passed':
        raise ValueError('source minute receipt required')
    root = Path(output_root).absolute()
    if '..' in root.parts:raise ValueError('daily output path contains parent traversal')
    for parent in reversed(root.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('daily output parent must be an ordinary directory')
    root.mkdir(exist_ok=False)
    (root/'CONFIGURATION.json').write_bytes(config_raw)
    (root/'csv').mkdir(); (root/'resampled-input').mkdir()
    reader = NativeHistory(config['native_reader']['library'], config['native_reader']['sha256'],
                           max_bars=1000000, max_file_bytes=268435456)
    native = None
    entries, securities = [], []
    try:
        native = _Native(config['helper']['library'], config['helper']['sha256'])
        for item in selection:
            code, market = item['symbol'].split('.')
            exchange = {'SH':'SSE','SZ':'SZSE'}[market]
            history = reader.read_source_store(source, exchange, code, expected_import_sha256=config['receipt_sha256'])
            sessions, excluded = select_sessions(history.bars, item['start'], item['end'])
            if not sessions:
                raise ValueError('selected security has no complete session label grid')
            rows = aggregate_native(native, root/'resampled-input'/(item['symbol']+'.dsb'), sessions)
            relative = 'csv/'+item['symbol']+'.csv'
            with (root/relative).open('x', newline='', encoding='ascii') as stream:
                writer = csv.writer(stream, lineterminator='\n')
                writer.writerow(('timestamp', *FIELDS))
                for row in rows:
                    writer.writerow((row['date']+'T00:00:00+08:00', *(repr(row[key]) for key in FIELDS)))
            original = next(s for s in receipt['securities'] if s['symbol'] == item['symbol'])
            entries.append(dict(**item, parent_minute_receipt_sha256=config['receipt_sha256'],
                parent_minute_native_sha256=original['sha256'], parent_source=receipt['profile'],
                parent_chunks=original['chunks'], selected_minute_records=sum(map(len, sessions.values())),
                rows=len(rows), first=rows[0]['date'], last=rows[-1]['date'], excluded_sessions=excluded,
                prefix_gap=dict(start=item['start'], end_exclusive=rows[0]['date']), coverage='unknown',
                suffix_gap=dict(start_exclusive=rows[-1]['date'], end=item['end']),
                native_aggregation_values_equal=True, source_minute_boundary=history.metadata.minute_boundary))
            securities.append(dict(symbol=item['symbol'], chunks=[dict(path=relative, sha256=_digest(root/relative))]))
    finally:
        if native is not None:native.close()
        reader.close()
    profile = dict(receipt['profile'], dataset_version='qmt-native-session-daily.v1', minute_boundary='unknown')
    provenance = dict(schema='guanheng.qmt-minute-daily-provenance.v1', configuration_sha256=hashlib.sha256(config_raw).hexdigest(),
        parent_store=str(source), parent_receipt_sha256=config['receipt_sha256'], entries=entries,
        label_grid=LABEL_GRID, mandatory_labels=sorted(MANDATORY_LABELS), optional_labels=[570],
        coverage='unknown', units_verified=False, historical_available_at_verified=False,
        helper_sha256=config['helper']['sha256'], reader_sha256=config['native_reader']['sha256'])
    provenance_sha = _write_json(root/'PROVENANCE.json', provenance)
    profile['instance_id'] = 'minute-daily:'+provenance_sha
    profile['session_id'] = 'minute-daily:'+config['receipt_sha256']
    _write_json(root/'manifest.json', dict(schema_version=3, period='1d', profile=profile, securities=securities))
    imported = import_dataset(root/'manifest.json', root/'store', config['helper']['library'], config['helper']['sha256'])
    result = dict(schema='guanheng.qmt-minute-daily-result.v1', status='completed',
        store=str(root/'store'), receipt_sha256=_digest(root/'store/qmt-import.json'),
        provenance_sha256=provenance_sha, securities=len(imported['securities']), total_rows=sum(e['count'] for e in imported['securities']),
        native_aggregation_and_day_readback_equal=True, coverage='unknown', qmt_or_shm_calls=0, framework_changes=0)
    _write_json(root/'RESULT.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='QMT minute store to native WT source day store')
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args(argv)
    print(json.dumps(convert(args.configuration, args.output_root), sort_keys=True))
    return 0


if __name__ == '__main__':raise SystemExit(main())
