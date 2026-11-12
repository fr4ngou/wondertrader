"""QNA 持续发布的业务边界；原值导入及复权算法继续由既有模块执行。"""
from __future__ import annotations

import argparse
import subprocess
import csv
from dataclasses import asdict
from datetime import date, datetime, timezone
import io
import json
import math
from pathlib import Path
import time

from integrations.guanheng import qmt_native_adjustment as qna
from .source import SourceUnavailable, write_json, utc_now


def load(path, maximum=16*1024*1024):
    return qna._load(Path(path), maximum)


def need(value, reason):
    if not value:
        raise ValueError(reason)


def stamp(value):
    return qna._time(value)


def validate_snapshot(value, capture_id, *, max_age_seconds, now=None):
    """校验完整来源和实收时点，返回最新共同闭合日及完整源年龄区间。"""
    need(type(value) is dict and set(value) == {'schema', 'capture_id', 'source', 'closed_through',
        'closure_evidence', 'daily', 'factors', 'references'}, 'analysis_snapshot_fields')
    need(value['schema'] == 'guanheng.qna-source-snapshot.v1'
         and value['capture_id'] == capture_id, 'analysis_snapshot_identity')
    source = value['source']
    need(type(source) is dict and set(source) == {'provider', 'instance_id', 'session_id', 'generation',
        'sdk_version', 'source_license', 'input_kind'} and source['provider'] == 'Qmt'
        and source['input_kind'] in ('synthetic', 'qmt_export')
        and type(source['generation']) is int and source['generation'] > 0, 'analysis_source_identity')
    need(all(type(source[k]) is str and 0 < len(source[k]) <= 256 for k in
        ('instance_id', 'session_id', 'sdk_version', 'source_license')), 'analysis_source_identity')
    closure = date.fromisoformat(value['closed_through'])
    need(type(value['closure_evidence']) is str and 0 < len(value['closure_evidence']) <= 1024,
        'analysis_closure_evidence')
    now = now or utc_now()
    from .source import closed_through
    need(closure <= date.fromisoformat(closed_through(now)), 'analysis_future_closed_day')
    times, dates, total = [], [], 0

    def receipt(item, operation):
        need(type(item) is dict and set(item) == {'request_id', 'requested_at', 'received_at', 'reply'},
            'analysis_receipt_fields')
        requested, received = stamp(item['requested_at']), stamp(item['received_at'])
        need(requested <= received <= now, 'analysis_source_clock')
        reply = item['reply']
        need(type(reply) is dict and reply['request_id'] == item['request_id']
            and reply['operation_id'] == operation and reply['ok'] is True
            and reply['error_code'] is None, 'analysis_source_reply')
        times.append(received)
        return reply['data']

    for group in ('daily', 'factors', 'references'):
        need(type(value[group]) is dict and sorted(value[group]) == list(qna.SYMBOLS), 'analysis_snapshot_symbols')
    for symbol in qna.SYMBOLS:
        data = receipt(value['daily'][symbol], 'market.market_data')
        need(type(data) is dict and set(data) == {symbol} and type(data[symbol]) is dict,
            'analysis_daily_reply')
        rows = data[symbol]
        if not rows:
            raise SourceUnavailable('analysis_daily_missing')
        need(len(rows) <= 4096, 'analysis_daily_capacity')
        valid = set()
        for label, row in rows.items():
            need(type(label) is str and len(label) == 8 and label.isascii() and label.isdigit(), 'analysis_daily_label')
            day = datetime.strptime(label, '%Y%m%d').date()
            need(type(row) is dict and set(row) == set(qna.FIELDS), 'analysis_daily_fields')
            for key in qna.FIELDS:
                need(type(row[key]) in (int, float) and math.isfinite(row[key])
                    and (row[key] > 0 if key in qna.FIELDS[:4] else row[key] >= 0), 'analysis_daily_value')
            if day <= closure:
                valid.add(day)
        total += len(rows)
        dates.append(valid)
        factors = receipt(value['factors'][symbol], 'market.divid_factors')
        need(type(factors) is dict and len(factors) <= 4096, 'analysis_factor_capacity')
    need(total <= 32768, 'analysis_total_capacity')
    common = set.intersection(*dates)
    if len(common) < 100:
        raise SourceUnavailable('analysis_common_dates_missing')
    basis = max(common)
    for symbol in qna.SYMBOLS:
        pair = value['references'][symbol]
        need(type(pair) is dict and set(pair) == {'none', 'front_ratio'}, 'analysis_reference_fields')
        for item in pair.values():
            data = receipt(item, 'market.market_data')
            need(type(data) is dict and set(data) == {symbol} and type(data[symbol]) is dict
                and set(data[symbol]) == {basis.strftime('%Y%m%d')}, 'analysis_reference_basis')
    oldest, latest = min(times), max(times)
    if (now-oldest).total_seconds() >= max_age_seconds:
        raise SourceUnavailable('analysis_source_stale')
    return dict(basis_date=basis.isoformat(), source_oldest_received_at=oldest.isoformat(),
        source_received_at=latest.isoformat())


def materialize(snapshot, work, identity):
    """原日线裁至共同基准，因子及参考保持原 reply 字节对应纯值。"""
    daily, factors, references = work/'daily', work/'factors', work/'references'
    for directory in (daily, factors, references):
        directory.mkdir()
    profile = {key: snapshot['source'][key] for key in
        ('provider', 'instance_id', 'session_id', 'generation', 'source_license', 'input_kind')}
    profile.update(dataset_version=snapshot['capture_id'], timezone='Asia/Shanghai', minute_boundary='unknown',
        adjustment='none', factor_version='', value_semantics='source', price_unit='CNY', volume_unit='lot', amount_unit='unknown')
    securities, factor_items, reference_receipts = [], [], []
    basis = identity['basis_date'].replace('-', '')
    for symbol in qna.SYMBOLS:
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('timestamp', *qna.FIELDS))
        for label, row in sorted(snapshot['daily'][symbol]['reply']['data'][symbol].items()):
            if label <= basis:
                day = datetime.strptime(label, '%Y%m%d').date().isoformat()
                writer.writerow((day+'T00:00:00+08:00', *(row[key] for key in qna.FIELDS)))
        path = daily/(symbol+'.csv')
        path.write_bytes(stream.getvalue().encode('utf8'))
        securities.append(dict(symbol=symbol, chunks=[dict(path=path.name, sha256=qna.file_sha(path))]))
        item = snapshot['factors'][symbol]
        path = factors/(symbol+'.json')
        write_json(path, item['reply'])
        factor_items.append(dict(symbol=symbol, file=path.name, sha256=qna.file_sha(path), api_ok=True,
            event_count=len(item['reply']['data']), requested_at=item['requested_at'], received_at=item['received_at'],
            empty_meaning='source returned empty events; first visibility unknown'))
        directory = references/symbol
        directory.mkdir()
        operations = []
        for name, item in snapshot['references'][symbol].items():
            path = directory/(name+'.json')
            write_json(path, item['reply'])
            operations.append(dict(name=name, file=path.name, sha256=qna.file_sha(path), ok=True,
                requested_at=item['requested_at'], received_at=item['received_at']))
        write_json(directory/'RESULT.json', dict(passed=True, operations=operations))
        reference_receipts.append(directory/'RESULT.json')
    write_json(daily/'manifest.json', dict(schema_version=3, period='1d', profile=profile, securities=securities))
    write_json(factors/'manifest.json', dict(schema='qmt.native-factor-inputs.v1',
        data_basis='current-visible-reconstruction', historical_first_available='unknown', items=factor_items))
    return daily/'manifest.json', factors/'manifest.json', reference_receipts


def native_pipeline(request):
    """仅在隐藏 Job 工作进程中执行 DLL；所有复权价格来自原 WT Reader。"""
    from integrations.guanheng.qmt_minute_import import import_dataset
    work = Path(request['work'])
    snapshot = load(request['snapshot'])
    identity = validate_snapshot(snapshot, request['capture_id'], max_age_seconds=request['max_age_seconds'])
    daily, factors, references = materialize(snapshot, work, identity)
    artifacts = {key: qna.Artifact(**value) for key, value in request['artifacts'].items()}
    need(set(artifacts) == {'helper', 'reader', 'probe'}, 'analysis_native_artifacts')
    for item in artifacts.values():
        item.verify()
    import_receipt = import_dataset(daily, work/'store', artifacts['helper'].path, artifacts['helper'].sha256,
        max_bars=4096, max_total_bars=32768)
    qna.prepare_inputs(factors, work/'store', identity['basis_date'], work/'prepared')
    products = {e: {'ETF': dict(name='ETF', session='DAY', holiday='CHINA', category=0,
        pricetick=.001, volscale=1, covermode=0, pricemode=0, trademode=1)} for e in ('SSE', 'SZSE')}
    contracts = {'SSE': {}, 'SZSE': {}}
    for symbol in qna.SYMBOLS:
        code, market = symbol.split('.')
        exchange = 'SSE' if market == 'SH' else 'SZSE'
        contracts[exchange][code] = dict(name=symbol, exchg=exchange, product='ETF', opendate=19900101, expiredate=20991231)
    for name, value in [('sessions', {'DAY': {'name': 'day', 'offset': 0,
            'sections': [{'from': 930, 'to': 1130}, {'from': 1300, 'to': 1500}]}}),
            ('commodities', products), ('contracts', contracts)]:
        write_json(work/(name+'.json'), value)
    write_json(work/'request.json', dict(path=str(work/'store'), adjfactor=str(work/'prepared/adjfactors.json'),
        adjust_flag=0, basis_date=int(identity['basis_date'].replace('-', '')), symbols=list(qna.SYMBOLS),
        **{name: str(work/(name+'.json')) for name in ('sessions', 'commodities', 'contracts')}))
    remaining = min(60., request['deadline']-time.monotonic())
    need(remaining > 0, 'analysis_refresh_deadline')
    read = qna.read_native(work/'prepared/INPUTS.json', work/'request.json', work/'NATIVE.json',
        reader=artifacts['reader'], probe=artifacts['probe'], timeout=remaining)
    write_json(work/'NATIVE-READ.json', asdict(read))
    candidate = qna.assemble_window(read, references)
    write_json(work/'CANDIDATE.json', candidate)
    write_json(work/'RESULT.json', dict(schema='guanheng.qna-native-refresh.v1', passed=True,
        capture_id=request['capture_id'], **identity, generated_at=utc_now().isoformat(),
        candidate_sha256=qna.file_sha(work/'CANDIDATE.json'), import_rows=sum(v['count'] for v in import_receipt['securities']),
        native_output_sha256=qna.file_sha(work/'NATIVE.json')))


NATIVE_TOOL_TIMEOUT = 75  # 此worker显式分类的原生子工具超时退出码。


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native-request', type=Path, required=True)
    args = parser.parse_args()
    try:
        native_pipeline(load(args.native_request))
    except subprocess.TimeoutExpired:
        return NATIVE_TOOL_TIMEOUT
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
