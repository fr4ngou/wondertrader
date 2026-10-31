"""冻结QMT单次事件转WT累计因子；分析价格只接受原WT Reader读回值。"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

SYMBOLS = tuple(sorted(('510300.SH', '510050.SH', '510500.SH', '512100.SH',
                        '588000.SH', '589000.SH', '159780.SZ', '515080.SH')))
FIELDS = ('open', 'high', 'low', 'close', 'volume', 'amount')
ZONE = timezone(timedelta(hours=8))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_sha(path):
    result, size = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        while True:
            block = stream.read(131072)
            if not block:
                break
            size += len(block)
            _require(size <= 64*1024*1024, 'adjustment_file_capacity')
            result.update(block)
    return result.hexdigest()


def _require(value, reason):
    if not value:
        raise ValueError(reason)


def _load(path, maximum=8*1024*1024):
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum+1)
    _require(len(raw) <= maximum, 'adjustment_input_capacity')
    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, 'adjustment_duplicate_json_key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('adjustment_nonfinite')))


def _day(value):
    if type(value) is date:
        parsed = value
    else:
        _require(type(value) is str, 'adjustment_date')
        parsed = date.fromisoformat(value)
    _require(1992 <= parsed.year <= 2099, 'adjustment_date_range')
    return parsed


def _time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'adjustment_received_at')
    return parsed.astimezone(timezone.utc)


def _number(value, *, positive=False):
    _require(type(value) in (int, float) and math.isfinite(value)
             and (value > 0 if positive else value >= 0), 'adjustment_number')
    return value


def _contained(parent, name):
    parent = Path(parent).resolve(strict=True)
    value = (parent/name).resolve(strict=True)
    _require(value.is_relative_to(parent), 'adjustment_input_path')
    return value


def load_factors(manifest_path, basis_date):
    """按上海事件日累乘第7列；保留空事件与基准日之后的原事件身份。"""
    path = Path(manifest_path).resolve(strict=True)
    source = _load(path)
    basis = _day(basis_date)
    _require(source['schema'] == 'qmt.native-factor-inputs.v1'
             and source['data_basis'] == 'current-visible-reconstruction'
             and source['historical_first_available'] == 'unknown', 'adjustment_factor_manifest')
    _require(len(source['items']) == 8 and sorted(i['symbol'] for i in source['items']) == list(SYMBOLS),
             'adjustment_factor_symbols')
    native, records = {'SSE': {}, 'SZSE': {}}, {}
    for item in source['items']:
        _require(item['api_ok'] is True, 'adjustment_factor_api')
        original = _contained(path.parent, item['file'])
        _require(file_sha(original) == item['sha256'], 'adjustment_factor_sha')
        received = _time(item['received_at'])
        _require(_time(item['requested_at']) <= received, 'adjustment_factor_clock')
        reply = _load(original)
        _require(reply['ok'] is True and reply['operation_id'] == 'market.divid_factors'
                 and reply['error_code'] is None and type(reply['data']) is dict
                 and len(reply['data']) == item['event_count'] <= 4096, 'adjustment_factor_reply')
        events, seen, cumulative, factors = [], set(), 1.0, []
        for stamp, row in sorted(reply['data'].items(), key=lambda pair: int(pair[0])):
            _require(stamp.isascii() and stamp.isdigit() and len(stamp) <= 13
                     and type(row) is list and len(row) == 7, 'adjustment_factor_event')
            day = datetime.fromtimestamp(int(stamp)/1000, ZONE).date()
            _require(1992 <= day.year <= 2099 and day not in seen, 'adjustment_factor_event_date')
            seen.add(day)
            _require(all(type(x) in (int, float) and math.isfinite(x) for x in row), 'adjustment_factor_fields')
            multiplier = _number(row[6], positive=True)
            event = dict(source_time_ms=stamp, date=day.isoformat(), native_fields=row,
                         event_multiplier=multiplier, included=day <= basis)
            if day <= basis:
                cumulative *= multiplier
                _number(cumulative, positive=True)
                # 原getDouble接受十进制字符串；原JSON实数先经过%.10f会损失累计因子精度。
                factors.append(dict(date=int(day.strftime('%Y%m%d')), factor=format(cumulative, '.17g')))
                event['cumulative_factor'] = cumulative
            events.append(event)
        symbol = item['symbol']
        code, exchange = symbol.split('.')
        native['SSE' if exchange == 'SH' else 'SZSE']['ETF.'+code] = factors
        records[symbol] = dict(events=events, received_at=received.isoformat(),
            original_path=str(original), original_sha256=item['sha256'],
            request_id=reply['request_id'], empty_meaning=item['empty_meaning'],
            native_empty=not events)
    return dict(basis_date=basis.isoformat(), manifest_sha256=file_sha(path), native=native,
                securities=records)


def _daily_inputs(daily_store):
    store = Path(daily_store).resolve(strict=True)
    manifest_path = store/'qmt-import.json'
    manifest = _load(manifest_path)
    _require(manifest['schema_version'] == 3 and manifest['period'] == '1d'
             and manifest['status'] == 'passed', 'adjustment_daily_manifest')
    records = {r['symbol']: r for r in manifest['securities']}
    _require(len(records) == len(manifest['securities']) and set(SYMBOLS) <= set(records), 'adjustment_daily_symbols')
    inputs = {}
    for symbol in SYMBOLS:
        item = records[symbol]
        data = _contained(store, item['path'])
        metadata_path = _contained(store, item['metadata_path'])
        _require(len(str(data).encode('utf8')) < 240, 'adjustment_native_path_budget')
        _require(file_sha(data) == item['sha256'] and file_sha(metadata_path) == item['metadata_sha256'],
                 'adjustment_daily_sha')
        metadata = _load(metadata_path)
        _require(metadata['period'] == '1d' and metadata['adjustment'] == 'none'
                 and metadata['factor_version'] == '' and metadata['price_unit'] == 'CNY'
                 and metadata['volume_unit'] == 'lot' and metadata['amount_unit'] == 'unknown', 'adjustment_daily_semantics')
        _require(type(item['count']) is int and 1 <= item['count'] <= 20000, 'adjustment_daily_capacity')
        _require(not (data.parent/(item['code']+'-.dsb')).exists(), 'adjustment_preadjusted_cache')
        inputs[symbol] = dict(path=str(data), sha256=item['sha256'], metadata_path=str(metadata_path),
            metadata_sha256=item['metadata_sha256'], count=item['count'], last_label=item['last_label'])
    _require(sum(item['count'] for item in inputs.values()) <= 32768, 'adjustment_total_capacity')
    return manifest_path, inputs


def _revisions(manifest_path, inputs, factors):
    identity = {symbol: {key: value for key, value in item.items() if key not in ('path', 'metadata_path')}
                for symbol, item in inputs.items()}
    source_revision = digest(canonical(dict(manifest_sha256=file_sha(manifest_path), securities=identity)))
    factor_body = canonical(factors['native'])
    factor_revision = digest(canonical(dict(manifest_sha256=factors['manifest_sha256'],
        basis_date=factors['basis_date'], native_factor_sha256=digest(factor_body))))
    return source_revision, factor_revision, factor_body


def prepare_inputs(factor_manifest, daily_store, basis_date, output):
    """校验只读源后，向全新目录写最新已封闭日基准的WT JSON。"""
    output = Path(output).resolve()
    _require(not output.exists(), 'adjustment_output_exists')
    _require(len(str(output/'adjfactors.json').encode('utf8')) < 240, 'adjustment_native_path_budget')
    store = Path(daily_store).resolve(strict=True)
    _require(not output.is_relative_to(store)
             and not output.is_relative_to(Path(factor_manifest).resolve(strict=True).parent), 'adjustment_output_overlaps_source')
    manifest_path, inputs = _daily_inputs(store)
    factors = load_factors(factor_manifest, basis_date)
    _require(all(_time(item['last_label']).astimezone(ZONE).date().isoformat() == factors['basis_date'] for item in inputs.values()),
             'adjustment_latest_common_basis')
    received = datetime.now(timezone.utc)
    _require(all(_time(item['received_at']) <= received for item in factors['securities'].values()), 'adjustment_future_factor')
    source_revision, factor_revision, factor_body = _revisions(manifest_path, inputs, factors)
    output.mkdir()
    (output/'adjfactors.json').write_bytes(factor_body)
    value = dict(schema='guanheng.qmt-native-adjustment-inputs.v1', source_revision=source_revision,
        factor_revision=factor_revision, daily_manifest_path=str(manifest_path),
        factor_manifest_path=str(Path(factor_manifest).resolve(strict=True)),
        daily_manifest_sha256=file_sha(manifest_path), securities=inputs, factors=factors,
        factor_file_sha256=digest(factor_body), module_received_at=received.isoformat())
    (output/'INPUTS.json').write_bytes(canonical(value))
    return value


def _verified_inputs(input_path):
    path = Path(input_path).resolve(strict=True)
    inputs = _load(path)
    _require(inputs['schema'] == 'guanheng.qmt-native-adjustment-inputs.v1', 'adjustment_input_schema')
    manifest, securities = _daily_inputs(Path(inputs['daily_manifest_path']).parent)
    factors = load_factors(inputs['factor_manifest_path'], inputs['factors']['basis_date'])
    source_revision, factor_revision, body = _revisions(manifest, securities, factors)
    _require(str(manifest) == inputs['daily_manifest_path']
             and file_sha(manifest) == inputs['daily_manifest_sha256']
             and securities == inputs['securities'] and factors == inputs['factors']
             and source_revision == inputs['source_revision'] and factor_revision == inputs['factor_revision'],
             'adjustment_derived_identity')
    _require(all(_time(item['last_label']).astimezone(ZONE).date().isoformat() == factors['basis_date'] for item in securities.values()),
             'adjustment_latest_common_basis')
    _require(digest(body) == inputs['factor_file_sha256'] == file_sha(path.parent/'adjfactors.json'),
             'adjustment_factor_json_sha')
    return inputs


@dataclass(frozen=True)
class Artifact:
    path: str
    sha256: str

    @classmethod
    def capture(cls, path):
        path = Path(path).resolve(strict=True)
        return cls(str(path), file_sha(path))

    def verify(self):
        _require(file_sha(self.path) == self.sha256, 'adjustment_artifact_changed')


@dataclass(frozen=True)
class NativeRead:
    inputs: Artifact
    request: Artifact
    output: Artifact
    reader: Artifact
    probe: Artifact
    metadata: tuple[Artifact, ...]


def _native_request(inputs_path, request_path):
    inputs = _verified_inputs(inputs_path)
    request = _load(request_path)
    _require(set(request) == {'path', 'adjfactor', 'adjust_flag', 'basis_date', 'symbols',
                              'sessions', 'commodities', 'contracts'}, 'adjustment_native_request_fields')
    _require(Path(request['path']).resolve(strict=True) == Path(inputs['daily_manifest_path']).parent
             and Path(request['adjfactor']).resolve(strict=True) == Path(inputs_path).resolve(strict=True).parent/'adjfactors.json'
             and type(request['adjust_flag']) is int and request['adjust_flag'] == 0
             and type(request['basis_date']) is int and str(request['basis_date']) == inputs['factors']['basis_date'].replace('-', '')
             and request['symbols'] == list(SYMBOLS), 'adjustment_native_request_binding')
    return inputs, tuple(Artifact.capture(request[key]) for key in ('sessions', 'commodities', 'contracts'))


def read_native(input_path, request_path, output_path, *, reader: Artifact, probe: Artifact, timeout=30.):
    """运行固定原生Reader探针，冻结本次输入/请求/输出身份；子进程无网络入口。"""
    _require(type(reader) is Artifact and type(probe) is Artifact, 'adjustment_native_binary_identity')
    _require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 60,
             'adjustment_native_timeout')
    inputs, metadata = _native_request(input_path, request_path)
    output = Path(output_path).resolve()
    _require(not output.exists() and output.parent.is_dir(), 'adjustment_native_output_exists')
    _require(not output.is_relative_to(Path(inputs['daily_manifest_path']).parent)
             and not output.is_relative_to(Path(inputs['factor_manifest_path']).parent), 'adjustment_output_overlaps_source')
    frozen = (Artifact.capture(input_path), Artifact.capture(request_path), reader, probe, *metadata)
    for artifact in frozen:
        artifact.verify()
    completed = subprocess.run([probe.path, reader.path, str(Path(request_path).resolve()), str(output)],
        cwd=output.parent, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=timeout, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    _require(completed.returncode == 0, 'adjustment_native_process_exit')
    for artifact in frozen:
        artifact.verify()
    _native_request(input_path, request_path)
    _load(output)
    return NativeRead(frozen[0], frozen[1], Artifact.capture(output), reader, probe, metadata)


def _rows(value):
    _require(type(value) is list and 1 <= len(value) <= 20000, 'adjustment_native_capacity')
    result, previous = {}, None
    for row in value:
        _require(type(row) is list and len(row) == 7, 'adjustment_native_row')
        day = datetime.strptime(str(row[0]), '%Y%m%d').date()
        _require(previous is None or day > previous, 'adjustment_native_order')
        previous = day
        for x in row[1:5]:
            _number(x, positive=True)
        for x in row[5:]:
            _number(x)
        result[day.isoformat()] = dict(zip(FIELDS, row[1:]))
    return result


def assemble_window(native_read: NativeRead, reference_receipts):
    """只装配原生返回价格；逐字段核实QMT原价/前复权参考后授分析资格。"""
    _require(type(native_read) is NativeRead, 'adjustment_native_read_required')
    for artifact in (native_read.inputs, native_read.request, native_read.output,
                     native_read.reader, native_read.probe, *native_read.metadata):
        artifact.verify()
    input_path, native_path = Path(native_read.inputs.path), Path(native_read.output.path)
    inputs, metadata = _native_request(input_path, native_read.request.path)
    _require(metadata == native_read.metadata, 'adjustment_native_metadata_binding')
    native = _load(native_path)
    _require(native['schema'] == 'guanheng.native-adjusted-read.v1'
             and native['reader_deleted'] is True and native['slices_released'] is True and native['reader_errors'] == 0
             and sorted(native['securities']) == list(SYMBOLS), 'adjustment_native_receipt')
    native_identity = {key: asdict(getattr(native_read, key)) for key in ('reader', 'probe')}
    basis = inputs['factors']['basis_date']
    raw, front, all_bars, evidence = {}, {}, [], []
    for symbol in SYMBOLS:
        source = inputs['securities'][symbol]
        _require(file_sha(source['path']) == source['sha256']
                 and file_sha(source['metadata_path']) == source['metadata_sha256'], 'adjustment_source_changed')
        raw[symbol], front[symbol] = (_rows(native['securities'][symbol][key]) for key in ('raw', 'front'))
        _require(raw[symbol].keys() == front[symbol].keys() and max(raw[symbol]) == basis, 'adjustment_native_dates')
        _require(len(raw[symbol]) == source['count'], 'adjustment_native_count')
        _require(raw[symbol][basis] == front[symbol][basis], 'adjustment_basis_not_raw')
        timeline = [event for event in inputs['factors']['securities'][symbol]['events'] if event['included']]
        dates = [event['date'] for event in timeline]
        cumulative = [event['cumulative_factor'] for event in timeline]
        denominator = cumulative[-1] if cumulative else 1.
        for day, original in raw[symbol].items():
            adjusted = front[symbol][day]
            _require(adjusted['volume'] == original['volume'] and adjusted['amount'] == original['amount'],
                     'adjustment_native_volume_amount')
            ratio = adjusted['close']/original['close']
            index = bisect_right(dates, day)-1
            expected = (cumulative[index] if index >= 0 else 1.)/denominator
            _require(math.isclose(ratio, expected, rel_tol=1e-12, abs_tol=1e-12), 'adjustment_native_factor_pair')
            _require(all(math.isclose(adjusted[k], original[k]*ratio, rel_tol=1e-12, abs_tol=1e-12)
                         for k in FIELDS[:4]), 'adjustment_native_ohlc_ratio')
    confirmed = set()
    for receipt in reference_receipts:
        receipt = Path(receipt).resolve(strict=True)
        record = _load(receipt)
        _require(record['passed'] is True, 'adjustment_reference_receipt')
        pairs = {}
        _require(type(record['operations']) is list and len(record['operations']) <= 16, 'adjustment_reference_capacity')
        for item in record['operations']:
            if item['name'] not in ('none', 'front_ratio'):
                continue
            _require(item['name'] not in pairs, 'adjustment_reference_duplicate')
            path = _contained(receipt.parent, item['file'])
            _require(item['ok'] is True and file_sha(path) == item['sha256'], 'adjustment_reference_sha')
            body = _load(path)
            _require(body['ok'] is True and body['operation_id'] == 'market.market_data', 'adjustment_reference_reply')
            pairs[item['name']] = body['data']
            _require(_time(item['requested_at']) <= _time(item['received_at']), 'adjustment_reference_clock')
            evidence.append(dict(path=str(path), sha256=item['sha256'], received_at=_time(item['received_at']).isoformat()))
        _require(set(pairs) == {'none', 'front_ratio'} and pairs['none'].keys() == pairs['front_ratio'].keys(),
                 'adjustment_reference_pair')
        for symbol, days in pairs['none'].items():
            _require(symbol in raw and type(days) is dict and bool(days)
                     and days.keys() == pairs['front_ratio'][symbol].keys(), 'adjustment_reference_symbols')
            for label, original in days.items():
                day = datetime.strptime(label, '%Y%m%d').date().isoformat()
                _require(day in raw[symbol], 'adjustment_reference_date')
                for key in FIELDS[:4]:
                    _require(math.isclose(original[key], raw[symbol][day][key], rel_tol=1e-12, abs_tol=1e-12)
                        and math.isclose(pairs['front_ratio'][symbol][label][key], front[symbol][day][key],
                                         rel_tol=1e-10, abs_tol=1e-10), 'adjustment_reference_value')
            confirmed.add(symbol)
    _require(confirmed == set(SYMBOLS), 'adjustment_reference_coverage')
    days = sorted(set.intersection(*(set(value) for value in raw.values())))
    _require(len(days) >= 100 and days[-1] == basis, 'adjustment_common_window')
    for day in days:
        for symbol in SYMBOLS:
            original, adjusted = raw[symbol][day], front[symbol][day]
            observation = dict(symbol=symbol, trade_date=day, **adjusted,
                market_available_at=None, market_source_sha256=inputs['source_revision'])
            all_bars.append(dict(observation=observation, raw_close=original['close'],
                                 factor=adjusted['close']/original['close']))
    now = datetime.now(timezone.utc).isoformat()
    latest_input = max([_time(v['received_at']) for v in inputs['factors']['securities'].values()]
                       + [_time(v['received_at']) for v in evidence] + [_time(inputs['module_received_at'])])
    _require(latest_input <= _time(now), 'adjustment_future_input')
    analysis = dict(basis_date=basis, known_at=now, source_revision=inputs['source_revision'],
        factor_revision=inputs['factor_revision'], bars=all_bars, adjustment='front_ratio', source_kind='qmt-native-verified')
    history = dict(source_revision=inputs['source_revision'], factor_revision=inputs['factor_revision'], observations=[
        dict(row['observation'], **raw[row['observation']['symbol']][row['observation']['trade_date']]) for row in all_bars])
    return dict(schema='guanheng.qmt-native-analysis-window.v1', analysis_ready=True,
        analysis=analysis, history=history, current_view=dict(dataset_sha256=inputs['source_revision'], received_at=now,
            history_basis='current-visible-reconstruction', historical_first_available='unknown', revision_history='unknown',
            source_amount_unit='unknown', amount_usage='unused'),
        units=dict(price='CNY', volume='lot', amount='unknown'), input_sha256=file_sha(input_path),
        native_output_sha256=file_sha(native_path), native_identity=native_identity, references=evidence,
        factor_events=inputs['factors']['securities'], native_securities=native['securities'],
        selection=dict(kind='intersection-of-observed-raw-dates', first_date=days[0], last_date=days[-1],
            dates=len(days), market_coverage='unknown'),
        qualification='current-visible native price analysis only; auxiliary facts and historical first visibility unknown')
