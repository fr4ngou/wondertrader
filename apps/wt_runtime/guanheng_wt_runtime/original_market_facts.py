"""已发布WT快照到原版事实的只读接缝；采集、特征和金融执行分别归原owner。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
import time

class OriginalFactsUnavailable(RuntimeError):
    """本次快照/分组尚未可读或已换代；调用方保留上次结果及原时钟。"""


@dataclass(frozen=True)
class CollectedOriginalFacts:
    facts: dict  # guanheng.original-current-facts.v1原版输入；只含同一WT快照事实。
    diagnostics: dict  # 查询窗口、缺口、原摘要和单位；诊断不授交易或历史可知资格。


def _iso(value):
    if type(value) is int:
        text = str(value)
        if len(text) != 8:
            raise OriginalFactsUnavailable('history_date_invalid')
        value = text[:4] + '-' + text[4:6] + '-' + text[6:]
    if type(value) is not str or date.fromisoformat(value).isoformat() != value:
        raise OriginalFactsUnavailable('history_date_invalid')
    return value


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    return hashlib.sha256(raw).hexdigest()


def _price_unit(value, code):
    # 旧日线合同的CNY表示OHLC单价；指数条目以代码域解释为点，原标签仍留诊断。
    if value == 'CNY':
        return 'index-point' if code == '000300' else 'CNY/share'
    return value


def _qualified_price_dates(item, code, unit_evidence):
    """沿发布源分段核对价格维度，保留混合包内有明确单位的日期。"""
    from guanheng_market_client.source_units import resolve_source_price_units

    rows = item['bars']
    parts = item.get('provenance', [dict(offset=0, count=len(rows), metadata=item['metadata'])])
    offset = 0
    accepted = []
    for part in parts:
        count = part['count']
        if part['offset'] != offset or not 0 < count <= len(rows) - offset:
            raise OriginalFactsUnavailable('history_provenance_coverage')
        metadata = part['metadata']
        values = rows[offset:offset + count]
        expected = 'index-point' if code == '000300' else 'CNY/share'
        unit = _price_unit(metadata.get('price_unit', 'unknown'), code)
        if unit_evidence is not None and unit != expected:
            proof = resolve_source_price_units(unit_evidence, item['symbol'], dict(bars=values, metadata=metadata))
            unit = 'CNY/share' if proof.semantic_price_unit == 'CNY' else proof.semantic_price_unit
        if unit == expected:
            accepted.extend(_iso(row['date']) for row in values)
        offset += count
    if offset != len(rows):
        raise OriginalFactsUnavailable('history_provenance_coverage')
    return accepted


def collect_current_facts(client, *, observation_date, history_from='2019-01-01', codes=None,
                          feature_stage='recalc', turnover_kind='official', seconds=120.,
                          clock=time.monotonic, utcnow=lambda: datetime.now(timezone.utc), unit_evidence=None, segment_units=False):
    """只调用MarketClient已发布查询；固定快照分段读全历史，不触发HPR或Source采集。

    客户端自行承担每次HTTP截止，本函数以单次总截止核对各调用前后。每段最多2000
    自然日，因此2000行协议上限能够覆盖全部日期，无首尾裁剪。源单位unknown原样传递。
    """
    from guanheng_strategy_original.reference import DEFAULT_CODES
    if unit_evidence is not None:
        from guanheng_market_client.source_units import UnitEvidence, resolve_source_price_units
        if not isinstance(unit_evidence, UnitEvidence):
            raise ValueError('原版单位证据类型不匹配')
    codes = DEFAULT_CODES if codes is None else codes
    start_day, end_day = date.fromisoformat(_iso(history_from)), date.fromisoformat(_iso(observation_date))
    if start_day > end_day or feature_stage not in ('seed', 'recalc') or turnover_kind not in ('official', 'proxy'):
        raise ValueError('原版读取窗口或特征模型不匹配')
    if type(codes) not in (list, tuple) or not codes or len(set(codes)) != len(codes) or not set(codes) <= set(DEFAULT_CODES):
        raise ValueError('原版交易池不匹配')
    if type(seconds) not in (float, int) or not 0 < seconds <= 600:
        raise ValueError('原版读取总截止不匹配')
    deadline = clock() + seconds

    def checked(call):
        if clock() >= deadline:
            raise TimeoutError('original facts deadline')
        reply = call()
        if clock() >= deadline:
            raise TimeoutError('original facts deadline')
        if reply.get('status', {}).get('code') != 'Ok' or type(reply.get('data')) is not dict:
            raise OriginalFactsUnavailable('published_query_unavailable')
        return reply['data'], utcnow().isoformat()

    snapshot, _ = checked(lambda: client.source_market_snapshot_query(observation_date))
    identity = snapshot.get('snapshot_id')
    if type(identity) is not str or not re.fullmatch('[0-9a-f]{64}', identity) or snapshot.get('observation_date') != observation_date:
        raise OriginalFactsUnavailable('snapshot_identity_invalid')
    required = set(codes) | {'000300'} | ({'510300'} if '159352' in codes else set())
    symbols = sorted(('SZSE.' if c.startswith('159') else 'SSE.') + c for c in required)
    packets = {'analysis': {}, 'raw': {}}
    diagnostics = dict(snapshot_id=identity, snapshot_provenance=snapshot.get('provenance'),
                       history={}, supplement={}, query_count=1, source_operations=0)
    if unit_evidence is not None:
        diagnostics['unit_evidence_sha256'] = unit_evidence.sha256
    for group, adjustment in (('analysis', 'front_ratio'), ('raw', 'none')):
        cursor = start_day
        while cursor <= end_day:
            last = min(end_day, cursor + timedelta(days=1999))
            request = dict(symbols=symbols, **{'from': int(cursor.strftime('%Y%m%d')), 'to': int(last.strftime('%Y%m%d'))},
                           limit=2000, adjustment=adjustment, snapshot_id=identity, view='archive', include_archive=True)
            data, received = checked(lambda: client.source_daily_history_batch_query(request))
            diagnostics['query_count'] += 1
            results = data.get('results', [])
            if [r.get('symbol') for r in results] != symbols:
                raise OriginalFactsUnavailable('history_selection_changed')
            for result in results:
                code = result['symbol'].split('.')[1]
                if result.get('status', {}).get('code') != 'Ok' or type(result.get('data')) is not dict:
                    raise OriginalFactsUnavailable('history_security_unavailable')
                item = result['data']; metadata = item.get('metadata', {})
                if item.get('source_snapshot_id') != identity or metadata.get('adjustment') != adjustment:
                    raise OriginalFactsUnavailable('history_snapshot_changed')
                entry = diagnostics['history'].setdefault(group + ':' + code, dict(canonical_response_sha256=[], source_metadata=metadata))
                entry['canonical_response_sha256'].append(_digest(item))
                # 空窗口没有价格事实；其旧兼容metadata不能确定后继非空窗口的复权基准。
                if not item.get('bars'):
                    continue
                units = dict(price_unit=_price_unit(metadata.get('price_unit', 'unknown'), code),
                             volume_unit=metadata.get('volume_unit', 'unknown'))
                if unit_evidence is not None:
                    qualified = resolve_source_price_units(unit_evidence, result['symbol'], item)
                    if qualified.semantic_price_unit != 'unknown':
                        units = dict(price_unit=('CNY/share' if qualified.semantic_price_unit == 'CNY'
                                                else qualified.semantic_price_unit), volume_unit=qualified.volume_unit)
                        entry.setdefault('unit_evidence_windows', []).append(dict(
                            response_sha256=entry['canonical_response_sha256'][-1], evidence_sha256=unit_evidence.sha256,
                            semantic_price_unit=qualified.semantic_price_unit))
                known_units = entry.setdefault('known_units', dict(price_unit=[], volume_unit=[]))
                for key, value in units.items():
                    if value == 'unknown':
                        continue
                    # 未声明的中间段只降低资格，不能遗忘更早已知单位。
                    if known_units[key] and value not in known_units[key]:
                        raise OriginalFactsUnavailable('history_basis_changed', dict(group=group, code=code, field=key, known_units=known_units[key] + [value]))
                    if value not in known_units[key]:
                        known_units[key].append(value)
                packet = packets[group].setdefault(code, dict(source_sha256='', received_at=received, available_at=None,
                    **units,
                    price_basis=adjustment, factor_version=metadata.get('factor_version', ''), bars=[]))
                incoming = dict(**units, factor_version=metadata.get('factor_version', ''))
                different = {k: (packet[k], v) for k, v in incoming.items() if packet[k] != v}
                if 'factor_version' in different or any('unknown' not in pair for k, pair in different.items() if k != 'factor_version'):
                    raise OriginalFactsUnavailable('history_basis_changed', dict(group=group, code=code, differences=different))
                for key, pair in different.items():
                    # 一段单位未声明时，整个混合包保持未知；保留各段原标签供核验。
                    packet[key] = 'unknown'
                    entry.setdefault('unit_uncertainty', []).append(dict(field=key, units=list(pair)))
                    if key == 'volume_unit':
                        entry['volume_scale_continuity_qualified'] = False  # 跨段量纲未核实，量比结果只作诊断。
                if segment_units:
                    dated_item = dict(item, symbol=result['symbol'])
                    packet.setdefault('qualified_price_dates', []).extend(_qualified_price_dates(dated_item, code, unit_evidence))
                packet['received_at'] = received
                bars = []
                for row in item.get('bars', []):
                    day = _iso(row['date'])
                    if not cursor.isoformat() <= day <= last.isoformat():
                        raise OriginalFactsUnavailable('history_window_changed')
                    bars.append(dict(date=day, **{k: row[k] for k in ('open', 'high', 'low', 'close', 'volume')}))
                packet['bars'].extend(bars)
            cursor = last + timedelta(days=1)
        for code, packet in packets[group].items():
            dates = [b['date'] for b in packet['bars']]
            if dates != sorted(set(dates)):
                raise OriginalFactsUnavailable('history_dates_repeated')
            packet['source_sha256'] = _digest(diagnostics['history'][group + ':' + code]['canonical_response_sha256'])

    if any(set(group) != required for group in packets.values()):
        raise OriginalFactsUnavailable('history_security_unavailable')
    if len({p['factor_version'] for p in packets['analysis'].values()}) != 1:
        raise OriginalFactsUnavailable('analysis_reference_changed')

    auxiliary = {}
    selection = [s for s in symbols if s != 'SSE.000300']
    for name, metric, selected in (('shares', 'etf_total_shares', selection), ('margin', 'margin_balance', ['CN.MARGIN_REPORT']),
                                  ('turnover', 'market_turnover' if turnover_kind == 'official' else 'market_turnover_proxy', ['CN.SH_SZ'])):
        rows, gaps, offset, catalog = [], [], 0, None
        while True:
            request = dict(snapshot_id=identity, metric=metric, symbols=selected, **{'from': history_from, 'to': observation_date}, offset=offset, limit=2000)
            data, _ = checked(lambda: client.source_supplement_query(request)); diagnostics['query_count'] += 1
            if data.get('source_snapshot_id') != identity or (catalog is not None and data.get('source_sha256') != catalog):
                raise OriginalFactsUnavailable('supplement_snapshot_changed')
            catalog = data.get('source_sha256')
            rows.extend(data.get('rows', [])); gaps.extend(data.get('gaps', []))
            following = data['selection']['next_offset']
            if following is None:
                break
            if type(following) is not int or following <= offset:
                raise OriginalFactsUnavailable('supplement_cursor_invalid')
            offset = following
        converted = []
        for row in rows:
            item = {k: row[k] for k in ('date', 'value', 'unit', 'source_sha256', 'received_at', 'available_at')}
            if name == 'shares':
                item['code'] = row['symbol'].split('.')[1]
            if name == 'turnover':
                item['kind'] = turnover_kind
            converted.append(item)
        auxiliary[name] = sorted(converted, key=lambda r: (r.get('code', ''), r['date']))
        diagnostics['supplement'][name] = dict(catalog_sha256=catalog, rows=len(rows), gaps=gaps, kind=turnover_kind if name == 'turnover' else None)
    final, _ = checked(lambda: client.source_market_snapshot_query(observation_date)); diagnostics['query_count'] += 1
    if final.get('snapshot_id') != identity:
        raise OriginalFactsUnavailable('publication_changed_during_read')
    # raw指数日历保留前复权补齐前的真实交易日；每包事实仍保持自己的价格基准。
    calendar = sorted({b['date'] for group in packets.values() for packet in group.values() for b in packet['bars']})
    facts = dict(schema='guanheng.original-current-facts.v1', profile='causal-current', feature_stage=feature_stage,
                 decision_date=observation_date, decision_at=utcnow().isoformat(), snapshot_id=identity,
                 description='WT published history and supplement; canonical response hashes; unknown units retained',
                 codes=list(codes), calendar=calendar, **packets, **auxiliary)
    diagnostics['facts_sha256'] = _digest(facts)
    return CollectedOriginalFacts(facts, diagnostics)
