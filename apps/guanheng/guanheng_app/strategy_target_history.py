"""WT原生signals.csv只读历史；不另建目标日志或调用执行器。"""
import base64
from collections import deque
import csv
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from time import monotonic
from zoneinfo import ZoneInfo

from guanheng_market_client.runtime_status import _open_status_file
from .managed_local_process import _inspect, _json, _path, _read
from .strategy_runtime_projection import published_identity
from .wt_business_observation import read_business
from .wt_runtime_observation import RuntimeObservationConfig, resolve_runtime_configuration, read_runtime_snapshot
from .contracts.strategy_target_history import TargetHistoryResponse

_HEADER = b'code,target,sigprice,gentime,usertag'
_LINE_BYTES = 2048  # 原生五列和有限usertag的单行读取上限，不限制日志保留期。


class TargetHistoryChanged(ValueError):
    """原日志被替换/截断或分页前缀改变；调用者重新读取最新页。"""


def _need(ok):
    if not ok: raise ValueError('target history source invalid')


def _check(deadline):
    if monotonic() >= deadline: raise TimeoutError('target history deadline')


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _cursor(value):
    if value is None: return None
    _need(type(value) is str and 1 <= len(value) <= 512 and re.fullmatch('[A-Za-z0-9_-]+', value))
    data = _json(base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)))
    _need(type(data) is dict and set(data) == {'source', 'bytes', 'sha', 'before'}
          and all(type(data[k]) is str and re.fullmatch('[a-f0-9]{64}', data[k]) for k in ('source', 'sha'))
          and all(type(data[k]) is int and 0 < data[k] <= 9007199254740991 for k in ('bytes', 'before')))
    return data


def _encode_cursor(value):
    return base64.urlsafe_b64encode(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).decode().rstrip('=')


def _number(value, *, quantity=False):
    _need(type(value) is str and len(value) <= 64)
    number = Decimal(value)
    _need(number.is_finite() and 0 <= number <= 9007199254740900)
    if quantity:
        _need(number == number.to_integral_value())
        return int(number)
    # 原生可写科学记数；展开前先限规模，避免短指数输入膨胀成任意大字符串。
    _need(-126 <= number.as_tuple().exponent <= 126)
    text = format(number, 'f')
    _need(len(text) <= 128)
    return text


def _hash_prefix(stream, size, deadline):
    # 绕过BufferedReader旧缓冲区，复核必须重新读取原只读句柄的实际文件字节。
    source = getattr(stream, 'raw', stream)
    source.seek(0)
    digest, left = hashlib.sha256(), size
    while left:
        _check(deadline)
        raw = source.read(min(left, 65536))
        if not raw: raise TargetHistoryChanged()
        digest.update(raw); left -= len(raw)
    return digest.hexdigest()


def _row(raw, sequence, source_id):
    values = next(csv.reader([raw.decode('utf8')], strict=True))
    _need(len(values) == 5)
    code, target, price, clock, unused_tag = values
    match = re.fullmatch(r'(SSE|SZSE)\.ETF\.([0-9]{6})', code)
    _need(match is not None and re.fullmatch('[0-9]{17}', clock) and len(unused_tag) <= 512)
    stamp = datetime.strptime(clock, '%Y%m%d%H%M%S%f').replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    _need(stamp <= datetime.now(timezone.utc))
    return dict(id=_sha([source_id, sequence, hashlib.sha256(raw).hexdigest()]), sequence=sequence,
        changed_at=stamp.isoformat(timespec='milliseconds'), symbol=match[2]+{'SSE':'.SH','SZSE':'.SZ'}[match[1]],
        target_quantity=_number(target, quantity=True), reference_price_cny=_number(price),
        target_weight=None, strategy_version=None, reason=None)


def read_signal_history(path, logical_instance, strategy_id, limit, cursor, deadline):
    """只读共享写句柄，固定前缀两次SHA核同；顺序扫描，内存只保留一页及逐证券前值。

    原生追加不改变此页快照；替换、截断或原前缀变化返回冲突。末行未写完时保留明确缺口。
    """
    _check(deadline)
    token = _cursor(cursor)
    try:
        before = _inspect(path)
    except FileNotFoundError:
        if token: raise TargetHistoryChanged() from None
        raise
    with _open_status_file(path) as stream:
        opened = os.fstat(stream.fileno())
        _need(stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1
              and (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino))
        source_id = _sha([logical_instance, strategy_id, str(path).lower(), opened.st_dev, opened.st_ino])
        if token and (token['source'] != source_id or opened.st_size < token['bytes']): raise TargetHistoryChanged()
        size = token['bytes'] if token else opened.st_size
        # 旧分页先核原字节前缀再解释数据；前缀变坏仍是快照冲突，区别新坏源。
        if token and _hash_prefix(stream, size, deadline) != token['sha']: raise TargetHistoryChanged()
        stream.seek(0)
        remaining, sequence, changed, initial, unchanged = size, 0, 0, 0, 0
        hasher, previous, selected = hashlib.sha256(), {}, deque(maxlen=limit+1)
        first_at = last_at = None
        incomplete = False
        try:
            header = stream.readline(min(_LINE_BYTES+1, remaining)) if remaining else b''
            _check(deadline)
            hasher.update(header); remaining -= len(header)
            _need(not header or header.rstrip(b'\r\n') == _HEADER and header.endswith(b'\n'))
            while remaining:
                _check(deadline)
                raw = stream.readline(min(_LINE_BYTES+1, remaining))
                _need(raw and len(raw) <= _LINE_BYTES)
                hasher.update(raw); remaining -= len(raw)
                if not raw.endswith(b'\n'):
                    _need(remaining == 0); incomplete = True; break
                sequence += 1
                row = _row(raw, sequence, source_id)
                first_at = first_at or row['changed_at']; last_at = row['changed_at']
                prior = previous.get(row['symbol']); previous[row['symbol']] = row['target_quantity']
                if prior == row['target_quantity']:
                    unchanged += 1; continue
                if prior is None: initial += 1
                else: changed += 1
                row.update(previous_target_quantity=prior,
                    change_quantity=None if prior is None else row['target_quantity']-prior,
                    kind='initial' if prior is None else 'changed')
                if token is None or sequence < token['before']: selected.append(row)
        except (ValueError, UnicodeError, csv.Error, DecimalException):
            if token and _hash_prefix(stream, size, deadline) != token['sha']:
                raise TargetHistoryChanged() from None
            raise
        digest = hasher.hexdigest()
        if token and digest != token['sha']: raise TargetHistoryChanged()
        # 原生只追加，故只复核捕获前缀；不以mtime变化拒绝正常追加。
        verified_digest = _hash_prefix(stream, size, deadline)
        after = _inspect(path); final = os.fstat(stream.fileno())
        if (verified_digest != digest or final.st_size < size or after.st_size < size
                or (final.st_dev, final.st_ino) != (after.st_dev, after.st_ino)
                or (opened.st_dev, opened.st_ino) != (final.st_dev, final.st_ino)):
            raise TargetHistoryChanged()
    items = list(reversed(selected))[:limit]
    next_cursor = _encode_cursor(dict(source=source_id, bytes=size, sha=digest, before=items[-1]['sequence'])) if len(selected)>limit else None
    _check(deadline)
    return dict(kind='wt-native-signals', source_id=source_id, snapshot_sha256=digest, raw_count=sequence,
        changed_count=changed, initial_count=initial, unchanged_count=unchanged, incomplete_tail=incomplete,
        first_at=first_at, last_at=last_at), items, next_cursor


def read_target_history(settings, strategy_id, strategy_version, limit=20, cursor=None, *, deadline) -> TargetHistoryResponse:
    """CURRENT→原ready/业务身份→同代Native配置SHA→原生目标文件→同代CURRENT复核。"""
    _need(type(strategy_id) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}', strategy_id)
          and type(strategy_version) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}', strategy_version)
          and type(limit) is int and 1 <= limit <= 100)
    requested = dict(strategy_id=strategy_id, strategy_version=strategy_version)
    response = dict(schema_version='guanheng.strategy-target-history.v1', read_only=True,
        observed_at=datetime.now(timezone.utc).isoformat(), state='waiting', reason='WT尚未发布目标记录来源。',
        requested=requested, source=None, items=[], next_cursor=None)
    selection = RuntimeObservationConfig.from_settings(settings)
    configuration = resolve_runtime_configuration(selection, deadline)
    if configuration is None: return response
    strategies, reference, unused_state = read_business(configuration, deadline)
    if not strategies: return response
    report = strategies.get(strategy_id)
    if report is None:
        response.update(state='not_current', reason='当前所选策略没有同身份的线上目标记录。'); return response
    definition, unused_symbols = published_identity(strategy_id, report)
    if definition['strategy_version'] != strategy_version:
        response.update(state='not_current', reason='所选版本与WT本轮发布版本不同，目标记录按精确身份读取。'); return response
    native_path = Path(reference['path']).with_name('execution.json')
    raw = _read(native_path, 256*1024, clock=monotonic, deadline=deadline)
    _need(hashlib.sha256(raw).hexdigest() == reference['config_sha256'])
    native = _json(raw)
    _need(type(native) is dict and type(native.get('strategies')) is list
          and sum(type(x) is dict and x.get('id') == strategy_id for x in native['strategies']) == 1)
    output = _path(native['output_directory'])
    path = output/'outputs'/strategy_id/'signals.csv'
    try: source, items, next_cursor = read_signal_history(path, configuration.instance_id, strategy_id, limit, cursor, deadline)
    except FileNotFoundError:
        if cursor: raise TargetHistoryChanged() from None
        source, items, next_cursor = None, [], None
    after = read_runtime_snapshot(configuration, deadline).value
    _need(after['components'].get('execution', {}).get('business_observation') == reference
          and resolve_runtime_configuration(selection, deadline) == configuration)
    _check(deadline)
    if source is not None:
        response.update(state='available', source=source, items=items, next_cursor=next_cursor,
            reason='原生目标份数设置历史；重复同目标已归并。目标权重、历史算法版本和细分调整原因未记录。目标设置与实际成交分别查看。')
    return response
