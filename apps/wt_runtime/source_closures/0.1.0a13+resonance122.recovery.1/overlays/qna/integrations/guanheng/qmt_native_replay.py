"""原 WT Reader 逐基准读取、按因子前缀分组的可搬迁回放目录。"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

try:
    from . import qmt_native_adjustment as q
except ImportError:  # 独立安装包的 lib 不带仓库 package。
    import qmt_native_adjustment as q


def _check_deadline(deadline):
    q._require(type(deadline) in (int, float) and math.isfinite(deadline)
               and time.monotonic() < deadline, 'replay_deadline')


def _native_rows(native):
    q._require(native['schema'] == 'guanheng.native-adjusted-read.v1'
               and native['reader_deleted'] is True and native['slices_released'] is True
               and native['reader_errors'] == 0 and sorted(native['securities']) == list(q.SYMBOLS),
               'replay_native_receipt')
    return {s: {kind: q._rows(native['securities'][s][kind]) for kind in ('raw', 'front')}
            for s in q.SYMBOLS}


def _group_rows(native, seed, factors, end):
    """核对原 Reader 值和事件前缀；此处乘法只用于验真，不产生分析价格。"""
    rows = _native_rows(native)
    for symbol in q.SYMBOLS:
        original, adjusted = rows[symbol]['raw'], rows[symbol]['front']
        expected_raw = {d: r for d, r in seed[symbol]['raw'].items() if d <= end}
        q._require(original == expected_raw and original.keys() == adjusted.keys()
                   and max(original) == end, 'replay_native_dates_raw')
        timeline = [e for e in factors['securities'][symbol]['events'] if e['included']]
        dates = [e['date'] for e in timeline]
        cumulative = [e['cumulative_factor'] for e in timeline]
        denominator = cumulative[-1] if cumulative else 1.
        for day, raw in original.items():
            front = adjusted[day]
            index = bisect_right(dates, day) - 1
            ratio = (cumulative[index] if index >= 0 else 1.) / denominator
            q._require(front['volume'] == raw['volume'] and front['amount'] == raw['amount'],
                       'replay_native_volume_amount')
            q._require(all(math.isclose(front[k], raw[k] * ratio, rel_tol=1e-12, abs_tol=1e-12)
                           for k in q.FIELDS[:4]), 'replay_native_factor_pair')
        q._require(original[end] == adjusted[end], 'replay_end_not_raw')
    return rows


def build_catalog(native_read, references, output, *, probe: q.Artifact, deadline):
    """从已验最新读回构建逐日目录；原件只读，所有派生物写入全新独占根。

    deadline 是调用者原 monotonic 总截止。隐藏原 Reader 子进程沿外层 Job
    继承；每次子调用最多60秒，目录构建不会扩大外层预算。
    """
    _check_deadline(deadline)
    q._require(type(native_read) is q.NativeRead, 'replay_native_read_required')
    q._require(type(probe) is q.Artifact, 'replay_native_probe_identity')
    probe.verify()
    qualification = q.assemble_window(native_read, references)
    inputs = q._verified_inputs(native_read.inputs.path)
    request = q._load(native_read.request.path)
    seed = _native_rows(q._load(native_read.output.path))
    days = sorted(set.intersection(*(set(seed[s]['raw']) for s in q.SYMBOLS)))
    q._require(1 <= len(days) <= 4096, 'replay_date_capacity')
    target = Path(output).resolve()
    q._require(not target.exists(), 'replay_output_exists')
    source_roots = [Path(inputs['daily_manifest_path']).parent, Path(inputs['factor_manifest_path']).parent]
    q._require(all(not target.is_relative_to(p) for p in source_roots), 'replay_output_overlaps_source')
    target.mkdir()
    pinned = []

    def copy(source, relative):
        _check_deadline(deadline)
        source = Path(source).resolve(strict=True)
        artifact = q.Artifact.capture(source)
        pinned.append(artifact)
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        q._require(q.file_sha(dest) == artifact.sha256, 'replay_copy_identity')

    copy(native_read.output.path, 'seed/NATIVE.json')
    (target / 'seed/QUALIFICATION.json').write_bytes(q.canonical(dict(
        source_revision=inputs['source_revision'], factor_revision=inputs['factor_revision'],
        native_read={k: asdict(getattr(native_read, k)) for k in ('inputs', 'request', 'output', 'reader', 'probe')},
        native_metadata=[asdict(a) for a in native_read.metadata],
        references=qualification['references'], historical_first_available='unknown',
        data_basis='current-visible-reconstruction')))
    copy(inputs['daily_manifest_path'], 'inputs/raw/qmt-import.json')
    raw_root = Path(inputs['daily_manifest_path']).parent
    for record in inputs['securities'].values():
        for field in ('path', 'metadata_path'):
            copy(record[field], Path('inputs/raw') / Path(record[field]).relative_to(raw_root))
    factor_manifest = Path(inputs['factor_manifest_path'])
    copy(factor_manifest, 'inputs/factors/FACTOR-INPUTS.json')
    for item in q._load(factor_manifest)['items']:
        copy(q._contained(factor_manifest.parent, item['file']), Path('inputs/factors') / item['file'])
    for index, reference in enumerate(references):
        ref = Path(reference).resolve(strict=True)
        copy(ref, f'inputs/references/{index}/RESULT.json')
        for item in q._load(ref)['operations']:
            copy(q._contained(ref.parent, item['file']), Path(f'inputs/references/{index}') / item['file'])
    for field in ('sessions', 'commodities', 'contracts'):
        copy(request[field], 'config/' + field + '.json')
    copy(native_read.reader.path, 'bin/WtDataStorage.dll')
    copy(probe.path, 'bin/WtReplayProbe.exe')
    copy(Path(q.__file__), 'lib/qmt_native_adjustment.py')
    copy(Path(__file__), 'lib/qmt_native_replay.py')
    groups, date_items = [], []
    portable_factors = target / 'inputs/factors/FACTOR-INPUTS.json'
    portable_manifest, portable_raw = q._daily_inputs(target / 'inputs/raw')
    for day in days:
        _check_deadline(deadline)
        factors = q.load_factors(portable_factors, day)
        source_revision, factor_revision, body = q._revisions(portable_manifest, portable_raw, factors)
        q._require(source_revision == inputs['source_revision'], 'replay_relocation_source_revision')
        # 全JSON字节相等才合组，避免仅分母相等而漏掉事件前缀变化。
        if not groups or groups[-1]['factor_body'] != body:
            groups.append(dict(index=len(groups), dates=[], factor_body=body))
        group = groups[-1]
        group['dates'].append(day)
        date_items.append(dict(date=day, group=group['index'], factor_revision=factor_revision))
    for group in groups:
        _check_deadline(deadline)
        name = f"groups/{group['index']:03d}"
        directory = target / name
        directory.mkdir(parents=True)
        body = group.pop('factor_body')
        (directory / 'adjfactors.json').write_bytes(body)
        end = group['dates'][-1]
        native_request = dict(path=str((target / 'inputs/raw').resolve()),
            adjfactor=str((directory / 'adjfactors.json').resolve()), adjust_flag=0,
            basis_date=int(end.replace('-', '')), symbols=list(q.SYMBOLS),
            **{k: str((target / 'config' / (k + '.json')).resolve())
               for k in ('sessions', 'commodities', 'contracts')})
        q._require(all(len(native_request[k].encode('utf8')) < 240
                       for k in ('path', 'adjfactor', 'sessions', 'commodities', 'contracts')),
                   'replay_native_path_budget')
        (directory / 'request.json').write_bytes(q.canonical(native_request))
        result = subprocess.run([str(target / 'bin/WtReplayProbe.exe'), str(target / 'bin/WtDataStorage.dll'),
            str(directory / 'request.json'), str(directory / 'NATIVE.json')], cwd=directory,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=min(60., max(.001, deadline - time.monotonic())), check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        q._require(result.returncode == 0, 'replay_native_process_exit')
        factors = q.load_factors(portable_factors, end)
        _group_rows(q._load(directory / 'NATIVE.json'), seed, factors, end)
        group.update(native=name + '/NATIVE.json', factor_file=name + '/adjfactors.json',
            request=name + '/request.json', native_sha256=q.file_sha(directory / 'NATIVE.json'),
            native_factor_sha256=q.digest(body), reader_deleted=True, slices_released=True)
    for artifact in pinned:
        artifact.verify()
    q._verified_inputs(native_read.inputs.path)
    for artifact in (native_read.inputs, native_read.request, native_read.output, *native_read.metadata):
        artifact.verify()
    now = datetime.now(timezone.utc).isoformat()
    catalog = dict(schema='guanheng.qmt-native-replay-catalog.v1', source_revision=inputs['source_revision'],
        dates=date_items, groups=groups, known_at=now, basis='per-date-front-ratio', symbols=list(q.SYMBOLS),
        current_view=dict(dataset_sha256=inputs['source_revision'], received_at=now,
            history_basis='current-visible-reconstruction', historical_first_available='unknown',
            revision_history='unknown', source_amount_unit='unknown', amount_usage='unused'),
        seed_native_sha256=native_read.output.sha256, reader_sha256=native_read.reader.sha256,
        probe_sha256=probe.sha256, units=dict(price='CNY', volume='lot', amount='unknown'),
        qualification='current-visible native price reconstruction; not historical first-visibility qualification')
    (target / 'CATALOG.json').write_bytes(q.canonical(catalog))
    files = {p.relative_to(target).as_posix(): q.file_sha(p) for p in sorted(target.rglob('*')) if p.is_file()}
    (target / 'MANIFEST.json').write_bytes(q.canonical(dict(schema='guanheng.qmt-native-replay-package.v1',
        files=files, source_revision=inputs['source_revision'], date_count=len(days), group_count=len(groups))))
    _check_deadline(deadline)
    return dict(path=str(target), manifest_sha256=q.file_sha(target / 'MANIFEST.json'),
                dates=len(days), groups=len(groups), source_revision=inputs['source_revision'])


class ReplayCatalog:
    """装入时核全包后持有纯值；window 不接触磁盘、不查询来源、不重算OHLC。"""

    @classmethod
    def open(cls, path, manifest_sha256):
        root = Path(path).resolve(strict=True)
        q._require(q.file_sha(root / 'MANIFEST.json') == manifest_sha256, 'replay_manifest_identity')
        manifest = q._load(root / 'MANIFEST.json')
        q._require(manifest['schema'] == 'guanheng.qmt-native-replay-package.v1'
                   and type(manifest['files']) is dict and len(manifest['files']) <= 4096,
                   'replay_manifest_schema')
        for relative, sha in manifest['files'].items():
            q._require(q.file_sha(q._contained(root, relative)) == sha, 'replay_artifact_identity')
        q._require('CATALOG.json' in manifest['files'] and 'seed/NATIVE.json' in manifest['files'],
                   'replay_manifest_catalog')
        catalog = q._load(root / 'CATALOG.json')
        q._require(catalog['schema'] == 'guanheng.qmt-native-replay-catalog.v1'
                   and catalog['symbols'] == list(q.SYMBOLS)
                   and catalog['basis'] == 'per-date-front-ratio', 'replay_catalog_schema')
        q._require(catalog['current_view'] == dict(dataset_sha256=catalog['source_revision'],
            received_at=catalog['known_at'], history_basis='current-visible-reconstruction',
            historical_first_available='unknown', revision_history='unknown',
            source_amount_unit='unknown', amount_usage='unused'), 'replay_current_view')
        q._time(catalog['known_at'])
        manifest_path, inputs = q._daily_inputs(root / 'inputs/raw')
        seed = _native_rows(q._load(root / 'seed/NATIVE.json'))
        days = sorted(set.intersection(*(set(seed[s]['raw']) for s in q.SYMBOLS)))
        q._require([v['date'] for v in catalog['dates']] == days
                   and manifest['date_count'] == len(days) <= 4096
                   and manifest['group_count'] == len(catalog['groups']) <= len(days), 'replay_date_identity')
        q._require(q.file_sha(root / 'seed/NATIVE.json') == catalog['seed_native_sha256']
                   and q.file_sha(root / 'bin/WtDataStorage.dll') == catalog['reader_sha256']
                   and q.file_sha(root / 'bin/WtReplayProbe.exe') == catalog['probe_sha256'],
                   'replay_native_identity')
        factors_path = root / 'inputs/factors/FACTOR-INPUTS.json'
        rows, date_map, covered = {}, {}, []
        for index, group in enumerate(catalog['groups']):
            q._require(group['index'] == index and group['dates'] and group['dates'] == sorted(set(group['dates'])),
                       'replay_group_dates')
            body = q._contained(root, group['factor_file']).read_bytes()
            q._require(q.digest(body) == group['native_factor_sha256']
                       and q.file_sha(q._contained(root, group['native'])) == group['native_sha256'],
                       'replay_group_identity')
            for day in group['dates']:
                factors = q.load_factors(factors_path, day)
                source_revision, factor_revision, expected_body = q._revisions(manifest_path, inputs, factors)
                q._require(expected_body == body and source_revision == catalog['source_revision'] == manifest['source_revision'],
                           'replay_group_factor_prefix')
                date_map[day] = dict(date=day, group=index, factor_revision=factor_revision)
            rows[index] = _group_rows(q._load(q._contained(root, group['native'])), seed, factors, group['dates'][-1])
            covered.extend(group['dates'])
        q._require(covered == days and [date_map[d] for d in days] == catalog['dates'], 'replay_group_partition')
        instance = cls()
        instance._catalog, instance._days, instance._rows, instance._dates = catalog, tuple(days), rows, date_map
        instance.manifest_sha256 = manifest_sha256
        return instance

    @property
    def dates(self):
        return self._days

    def window(self, basis_date):
        """返回截至该日原生价格前缀；返回新容器，调用者改动不影响后续窗口。"""
        basis = q._day(basis_date).isoformat()
        q._require(basis in self._dates, 'replay_basis_outside_catalog')
        item = self._dates[basis]
        rows = self._rows[item['group']]
        catalog = self._catalog
        bars, original = [], []
        for day in self._days:
            if day > basis:
                break
            for symbol in q.SYMBOLS:
                raw, front = rows[symbol]['raw'][day], rows[symbol]['front'][day]
                observation = dict(symbol=symbol, trade_date=day, **front,
                    market_available_at=None, market_source_sha256=catalog['source_revision'])
                bars.append(dict(observation=observation, raw_close=raw['close'], factor=front['close'] / raw['close']))
                original.append(dict(observation, **raw))
        return dict(schema='guanheng.qmt-native-analysis-window.v1', analysis_ready=True,
            analysis=dict(basis_date=basis, known_at=catalog['known_at'], source_revision=catalog['source_revision'],
                factor_revision=item['factor_revision'], bars=bars, adjustment='front_ratio', source_kind='qmt-native-verified'),
            history=dict(source_revision=catalog['source_revision'], factor_revision=item['factor_revision'], observations=original),
            current_view=dict(catalog['current_view']), units=dict(catalog['units']),
            selection=dict(kind='intersection-of-observed-raw-dates', first_date=self._days[0], last_date=basis,
                dates=len(original) // len(q.SYMBOLS), market_coverage='unknown'),
            replay_identity=dict(manifest_sha256=self.manifest_sha256, group=item['group'],
                native_output_sha256=catalog['groups'][item['group']]['native_sha256']),
            qualification=catalog['qualification'])
