"""WT 研究横截面备用来源，使用现有定日股票池约束 BigQuant 原件。"""

from datetime import date, datetime, timezone
from decimal import Decimal
from math import fsum, isfinite
from statistics import median
import os
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic, sleep

from ..guanheng_market_client.daily_facts import validate_day_facts, validate_stock_cross_section
from ..guanheng_market_client import strict_json
from .market_generation import encode

TABLE = 'cn_stock_real_bar1d'
FIELDS = ('date', 'instrument', 'close', 'pre_close', 'amount')
SUFFIXES = {'SSE': 'SH', 'SZSE': 'SZ', 'BSE': 'BJ'}


def _instrument(symbol):
    exchange, code = symbol.split('.')
    return f'{code}.{SUFFIXES[exchange]}'


def _number(value):
    return type(value) in (int, float) and isfinite(value)


def project(facts, records):
    """核对定日身份、有效股票和前收盘口径，再按原公式形成研究快照。"""
    validate_day_facts(facts, response='source_snapshot_id' in facts)
    day = facts['date']
    members = {_instrument(symbol) for symbol in facts['members']}
    if type(records) is not list or len(records) > 20000:
        raise ValueError('stock_cross_section_capacity')
    by_symbol = {}
    for record in records:
        if (type(record) is not dict or set(record) != set(FIELDS) or record['date'] != day
                or type(record['instrument']) is not str or record['instrument'] in by_symbol):
            raise ValueError('stock_cross_section_identity')
        by_symbol[record['instrument']] = record
    if members - by_symbol.keys():
        raise ValueError('stock_cross_section_members_missing')
    amounts, changes = [], []
    for _, symbol, reference_close, reference_previous, volume, _, state, quality in facts['rows']:
        if quality != 'qualified' or state == '?' or state == '1' and not volume:
            raise ValueError('stock_cross_section_state_unqualified')
        if state != '1' or Decimal(volume) <= 0:
            continue
        row = by_symbol[_instrument(symbol)]
        close, previous, amount = row['close'], row['pre_close'], row['amount']
        if not all(_number(value) and value > 0 for value in (close, previous, amount)):
            raise ValueError('stock_cross_section_active_quote_missing')
        # 保留同口径样本，价格最小刻度内的浮点表示误差按原价复核。
        if (not reference_close or not reference_previous
                or abs(Decimal(str(close)) - Decimal(reference_close)) > Decimal('0.000001')
                or abs(Decimal(str(previous)) - Decimal(reference_previous)) > Decimal('0.000001')):
            raise ValueError('stock_cross_section_price_mismatch')
        amounts.append(amount)
        changes.append((close / previous - 1) * 100)
    if not amounts or len(facts['rows']) != len(members):
        raise ValueError('stock_cross_section_not_qualified')
    top = (len(amounts) + 19) // 20
    return dict(date=day, sample_count=len(amounts),
                top5_pct=100 * fsum(sorted(amounts, reverse=True)[:top]) / fsum(amounts),
                median_return_pct=median(changes))


def normalize_rows(rows):
    records = rows.astype(object).where(rows.notna(), None).to_dict('records')
    for row in records:
        value = row['date']
        if isinstance(value, datetime) and value.hour == value.minute == value.second == value.microsecond == 0 and not getattr(value, 'nanosecond', 0):
            row['date'] = value.date().isoformat()
    return records


def validate_policy(value):
    """固定隔离 SDK 解释器的绝对路径及单次查询截止，凭据仅从进程环境取得。"""
    required = {'bigquant_python', 'timeout_seconds', 'minimum_sample_count'}
    if (type(value) is not dict or not required <= set(value) or set(value) - required - {'history_from','history_days_per_cycle'}
            or type(value['bigquant_python']) is not str or not Path(value['bigquant_python']).is_absolute()
            or type(value['timeout_seconds']) is not int or not 1 <= value['timeout_seconds'] <= 60
            or type(value['minimum_sample_count']) is not int or not 1 <= value['minimum_sample_count'] <= 20000):
        raise ValueError('stock cross section policy invalid')
    if 'history_from' in value or 'history_days_per_cycle' in value:
        first = value.get('history_from')
        count = value.get('history_days_per_cycle')
        if (type(first) is not str or date.fromisoformat(first).isoformat() != first
                or type(count) is not int or not 1 <= count <= 30):
            raise ValueError('stock cross section history policy invalid')


def _query_worker(dataset, first, last):
    """子进程只接受内部数据集选择和 ISO 日期，stdout 专用于结构化数据。"""
    from contextlib import redirect_stdout
    if not all(re.fullmatch(r'\d{4}-\d{2}-\d{2}', day) and date.fromisoformat(day).isoformat() == day
               for day in (first, last)) or first > last:
        return 2
    if dataset == 'stocks' and first == last:
        sql = f"SELECT {', '.join(FIELDS)} FROM {TABLE} WHERE date = '{first}' LIMIT 20001"
    elif dataset == 'small_cap_turnover' and (date.fromisoformat(last) - date.fromisoformat(first)).days < 366:
        sql = ("SELECT date, instrument, amount FROM cn_stock_index_bar1d "
               f"WHERE instrument = '932000.CSI' AND date BETWEEN '{first}' AND '{last}' LIMIT 367")
    else:
        return 2
    try:
        with redirect_stdout(sys.stderr):
            import bigquant
            secret = os.environ.pop('GUANHENG_BIGQUANT_CREDENTIAL')
            ak, sk = secret.split('.', 1)
            bigquant.init(ak=ak, sk=sk)
            records = normalize_rows(bigquant.dai.query(sql, filters={'date': [first, last]}).df())
        sys.stdout.buffer.write(encode(records))
    except Exception:
        return 1
    return 0


def acquire_bigquant(policy, day, *, deadline, cancelled, environ):
    return query_bigquant(policy, 'stocks', day, day, deadline=deadline, cancelled=cancelled, environ=environ)


def query_bigquant(policy, dataset, first, last, *, deadline, cancelled, environ):
    """隔离依赖，沿 WT 批次的绝对截止和停止信号回收 SDK 进程。"""
    import tempfile
    if not environ.get('GUANHENG_BIGQUANT_CREDENTIAL'):
        raise ValueError('bigquant_unavailable')
    end = min(deadline, monotonic() + policy['timeout_seconds'])
    # 独立供应商解释器只加载这个固定工作脚本，SDK 输出不进入 WT 日志。
    module_root = Path(__file__).resolve().parents[2]
    command = [policy['bigquant_python'], '-I', '-B', '-c',
               'import sys;sys.path.insert(0,sys.argv[1]);from integrations.guanheng.stock_cross_section import _query_worker;sys.path.pop(0);sys.exit(_query_worker(*sys.argv[2:]))',
               str(module_root), dataset, first, last]
    environment = {key: value for key, value in environ.items()
                   if key.upper() in {'GUANHENG_BIGQUANT_CREDENTIAL','SYSTEMROOT','WINDIR','TEMP','TMP',
                                      'USERPROFILE','LOCALAPPDATA','APPDATA','HTTPS_PROXY','HTTP_PROXY','NO_PROXY',
                                      'PATH','PROCESSOR_ARCHITECTURE','PROCESSOR_IDENTIFIER','PROCESSOR_LEVEL',
                                      'PROCESSOR_REVISION','NUMBER_OF_PROCESSORS','SYSTEMDRIVE'}}
    output_budget = 8 * 1024 * 1024
    # 使用固定文件描述符；Windows 的临时文件在最后一个句柄关闭后由系统清理。
    with tempfile.TemporaryFile() as stream:
        job = None
        process = None
        primary = None
        try:
            if os.name == 'nt':
                try:
                    from ._process_job import ProcessJob
                except ModuleNotFoundError as error:
                    if error.name != __package__ + '._process_job':
                        raise
                    from scripts.native_support.process_job import ProcessJob
                job = ProcessJob()
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.DEVNULL,
                                       env=environment, creationflags=(0x08000004 if job is not None else 0))
            if job is not None:
                job.attach_and_resume(process, deadline=end)
            while process.poll() is None:
                if cancelled():
                    raise InterruptedError('WT stock cross section stopped')
                if monotonic() >= end or os.fstat(stream.fileno()).st_size > output_budget:
                    raise ValueError('bigquant_unavailable')
                sleep(.05)
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                try:
                    if process is not None:
                        reap_by = monotonic() + 1
                        if job is not None and job.assigned:
                            # Windows venv 引导器和真实解释器可同时持有 stdout。先确认整树退出，
                            # 再释放输出文件，避免临时目录共享冲突掩盖查询超时或取消。
                            if job.active_processes():
                                job.terminate()
                            while job.active_processes():
                                remaining = reap_by - monotonic()
                                if remaining <= 0:
                                    raise TimeoutError('BigQuant process tree did not exit')
                                sleep(min(.01, remaining))
                        elif process.poll() is None:
                            process.kill()
                        process.wait(timeout=max(0., reap_by - monotonic()))
                finally:
                    if job is not None:
                        job.close()
            except Exception as error:
                if primary is None:
                    raise
                primary.add_note('BigQuant cleanup: ' + type(error).__name__)
        if process.returncode != 0:
            raise ValueError('bigquant_unavailable')
        stream.seek(0)
        raw = stream.read(output_budget + 1)
        if len(raw) > output_budget:
            raise ValueError('bigquant_unavailable')
        records = strict_json(raw)
        if cancelled():
            raise InterruptedError('WT stock cross section stopped')
        if monotonic() >= end:
            raise ValueError('bigquant_unavailable')
        return records


def prepare_section(facts, cache, unit_evidence, policy, objects, *, deadline, cancelled, environ=None):
    """由 WT 输入 owner 调用，返回随同日股票池归档的聚合和原件摘要。"""
    from .analysis_price_capture import load_price_capture, price_batches
    from .analysis_price_units import capture_price_units, load_unit_evidence, qualify_capture_units
    day = facts['date']
    provider = 'QMT'
    records = None
    if unit_evidence is not None:
        evidence = load_unit_evidence(unit_evidence, deadline=deadline, cancelled=cancelled)
        units = qualify_capture_units(cache, evidence, deadline=deadline, cancelled=cancelled)
        if units is not None:
            manifest = load_price_capture(cache)
            symbols = [_instrument(symbol) for symbol in facts['members']]
            if all(capture_price_units(manifest, cache['sha256'], symbol, units).amount_unit == 'CNY' for symbol in symbols):
                reference = {_instrument(row[1]): row for row in facts['rows']}
                stamp = day.replace('-', '')
                records = []
                for _, batch in price_batches(cache, manifest, deadline=deadline, cancelled=cancelled):
                    for symbol, item in batch.items():
                        if symbol in reference:
                            bar = item['data'].get(stamp, {})
                            previous = reference[symbol][3]
                            records.append(dict(date=day, instrument=symbol, close=bar.get('close'),
                                                pre_close=float(previous) if previous else None, amount=bar.get('amount')))
                try:
                    row = project(facts, records)
                except ValueError:
                    records = None
    if records is None:
        provider = 'BigQuant'
        try:
            records = acquire_bigquant(policy, day, deadline=deadline, cancelled=cancelled,
                                       environ=os.environ if environ is None else environ)
        except InterruptedError:
            raise
        except (ValueError, OSError):
            return dict(reason='bigquant_unavailable')
        try:
            row = project(facts, records)
        except ValueError:
            return dict(reason='cross_section_unqualified')
    if row['sample_count'] < policy['minimum_sample_count']:
        return dict(reason='cross_section_unqualified')
    original = objects.put(encode(dict(
        provider=provider,  # 整日成交额与收盘供应方。
        table=TABLE if provider == 'BigQuant' else None,  # 外部原始行情表。
        date=day,  # 交易日。
        records=records,  # 适配后的原始价格与成交额组合。
        universe_sha256=facts['provenance']['universe_sha256'],  # WT 定日股票池身份。
        qmt_capture_sha256=cache['sha256'],  # 本轮优先来源的捕获身份。
        retrieved_at=datetime.now(timezone.utc).isoformat())))  # 本次保存时间，历史首次可知保持未知。
    result = dict(provider=provider, source_sha256=original, **{key: value for key, value in row.items() if key != 'date'})
    return validate_stock_cross_section(result, len(facts['members']))
