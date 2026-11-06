"""独立原版回放：真实CLI、人工算例、固定原路由差分和准入边界。"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'apps/guanheng/strategy_original'
sys.path.insert(0, str(PACKAGE))
from guanheng_strategy_original import reference
from guanheng_strategy_original.cli import main


@pytest.fixture
def source():
    path = Path(os.environ.get('RESONANCE_ORIGINAL_SOURCE', str(ROOT / 'research/resonance-20261105/upstream-resonance')))
    if not (path / 'backend/base/analysis/strategy/router.py').is_file():
        pytest.skip('需显式原版检出；上游原件保留本地，不随测试再发行')
    return path


@pytest.fixture
def snapshot():
    dates, day = [], date(2021, 1, 4)
    while len(dates) < 274:
        if day.weekday() < 5:
            dates.append(day.isoformat())
        day += timedelta(days=1)
    closes = [round(3.6-i*.003, 4) for i in range(270)] + [2.79, 2.90, 3.10, 3.20]
    rows = []
    for day, price in zip(dates, closes):
        row = dict.fromkeys(reference.DAILY_FIELDS)
        row.update(date=day, code='510300', open_price=price, high_price=price,
                   low_price=price, close_price=price, change_pct=0., price_position=50.,
                   trade_direction='NEUTRAL', share_prob=10., composite_prob=45., volume_ratio=0.)
        rows.append(row)
    rows[270].update(price_position=5., share_prob=90., change_pct=-3.)
    rows[272].update(change_pct=3.9, volume_ratio=.8)
    return dict(schema=reference.SCHEMA, upstream_commit=reference.UPSTREAM_COMMIT,
                data_kind='synthetic', source={'description':'人工构造熊市反弹执行算例，派生字段并非真实行情'},
                units={'price':'CNY/share','volume':'upstream-source-unit','shares':'1e8-share','market':'1e8-CNY'},
                codes=['510300'], daily={'510300':rows}, calendar=dates, evaluation_start='2021-01-01',
                turnover=[dict(date=d,total_amount_yi=1000.-i) for i,d in enumerate(dates)],
                margin=[dict(date=d,fin_balance_yi=1000.-i) for i,d in enumerate(dates)])


def test_actual_cli_manual_execution_and_no_overwrite(source, snapshot, tmp_path):
    inp, out = tmp_path/'input.json', tmp_path/'report.json'
    inp.write_bytes(reference.canonical(snapshot))
    command = [sys.executable, '-B', str(PACKAGE/'run.py'), 'run', '--source', str(source),
               '--input', str(inp), '--output', str(out)]
    process = subprocess.run(command, capture_output=True, timeout=30, check=False)
    assert process.returncode == 0, process.stdout
    report = json.loads(out.read_bytes())
    assert [t['date'] for t in report['trades_by_code']['510300']] == ['2022-01-17','2022-01-19']
    log = report['portfolio']['trade_log']
    assert [(t['date'],t['kind'],t['price']) for t in log] == [('2022-01-18','BUY',2.90),('2022-01-20','SELL',3.20)]
    assert report['portfolio']['final_equity'] == round(3.20/2.90,6)
    assert report['execution_qualified'] is False and report['point_in_time_qualified'] is False
    assert report['input_sha256'] == reference.digest(snapshot)
    assert report['model']['execution'] == 'next-trading-day-close'
    before = out.read_bytes()
    assert subprocess.run(command, capture_output=True, timeout=30, check=False).returncode == 1
    assert out.read_bytes() == before


def test_fixed_router_and_simulator_differential(source, snapshot, tmp_path):
    # 覆盖原17证券及A500/芯片的跨证券引用，不把589000替换为589680。
    codes = ['510300','510050','510500','512100','588000','589680','159780','159781',
             '515080','159352','563300','515880','588200','159740','512400','510150','159842']
    original_rows = snapshot['daily']['510300']
    snapshot['codes'] = codes
    snapshot['daily'] = {c:[dict(r,code=c) for r in original_rows] for c in codes}
    before = deepcopy(snapshot)
    report = reference.run_reference(source, snapshot)
    assert snapshot == before
    inp = tmp_path/'input.json'
    inp.write_bytes(reference.canonical(snapshot))
    # 独立解释器直接装载原件，不经过新包的worker与临时源码复制。
    script = """
import json,sys
sys.path.insert(0,sys.argv[1])
from base.analysis.sentiment.core import enrich_turnover,percentile_series,turnover_value
from base.analysis.strategy.router import compute_trades
from portfolio.analysis.simulator import simulate
s=json.load(open(sys.argv[2],encoding='utf8'))
t=enrich_turnover(s['turnover']); m=s['margin']
tp=percentile_series([r['date'] for r in t],[turnover_value(r) for r in t],60,20)
mp=percentile_series([r['date'] for r in m],[r['fin_balance_yi'] for r in m],60,20)
r={c:compute_trades(c,s['daily'][c],t_pct=tp,m_pct=mp,hs300_rows=s['daily']['510300'],kc50_rows=s['daily']['588000'],version='stable') for c in s['codes']}
p=simulate({c:v['trades'] for c,v in r.items()},{c:{v['date']:v['close_price'] for v in s['daily'][c]} for c in s['codes']},s['calendar'])
print(json.dumps({'strategy':r,'portfolio':p},ensure_ascii=True,sort_keys=True))
"""
    direct = subprocess.run([sys.executable,'-I','-S','-B','-c',script,str(source/'backend'),str(inp)],
                            cwd=tmp_path,capture_output=True,timeout=30,check=False)
    assert direct.returncode == 0, direct.stderr
    oracle = json.loads(direct.stdout)
    assert report['strategy_results'] == oracle['strategy']
    assert report['portfolio'] == oracle['portfolio']


def test_source_tampering_rejected_before_execution(source, snapshot, tmp_path):
    manifest = json.loads((PACKAGE/'guanheng_strategy_original/source_manifest.json').read_text(encoding='utf8'))
    copy = tmp_path/'source'
    for name in manifest['files']:
        target = copy/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,target)
    first = next(iter(manifest['files']))
    (copy/first).write_bytes((copy/first).read_bytes()+b'\n# modified\n')
    with pytest.raises(ValueError, match='源码内容身份不匹配'):
        reference.run_reference(copy, snapshot)


@pytest.mark.parametrize('mutation', ['duplicate','reversed','nan','bad-ohlc','missing-field','code-type','missing-date','calendar-object'])
def test_invalid_snapshot_rejected(snapshot, mutation):
    value = deepcopy(snapshot)
    rows = value['daily']['510300']
    if mutation == 'duplicate': rows.insert(1,deepcopy(rows[0]))
    elif mutation == 'reversed': rows.reverse()
    elif mutation == 'nan': rows[0]['close_price'] = float('nan')
    elif mutation == 'bad-ohlc': rows[0]['high_price'] = 1.
    elif mutation == 'missing-field': del rows[0]['close_price']
    elif mutation == 'code-type': value['codes'] = [[]]
    elif mutation == 'missing-date': del rows[0]['date']
    elif mutation == 'calendar-object': value['calendar'] = [{'date':d} for d in value['calendar']]
    with pytest.raises(ValueError):
        reference.validate_snapshot(value)


def test_missing_selected_and_cross_reference_data(source, snapshot):
    empty = deepcopy(snapshot)
    empty['daily']['510300'] = []
    with pytest.raises(ValueError): reference.run_reference(source,empty)
    missing = deepcopy(snapshot)
    missing['codes'] = ['159352']
    missing['daily'] = {'159352':[dict(r,code='159352') for r in snapshot['daily']['510300']]}
    with pytest.raises(ValueError): reference.run_reference(source,missing)


def test_empty_auxiliary_and_short_history_are_diagnosed(source, snapshot):
    value = deepcopy(snapshot)
    value['daily']['510300'] = value['daily']['510300'][:25]
    value['calendar'] = value['calendar'][:25]
    value['turnover'] = []
    value['margin'] = []
    report = reference.run_reference(source,value)
    assert report['trades_by_code']['510300'] == []
    assert report['portfolio']['final_equity'] == 1.
    assert report['data_audit']['qualification'] == 'diagnostic-only'
    # 诊断正文须给出缺失与暖机状态；不把“空交易”当成充分准入。
    audit = json.dumps(report['data_audit'],ensure_ascii=False)
    assert 'turnover' in audit and 'margin' in audit and '250' in audit


def test_worker_timeout_returns_bounded_failure(source, snapshot, monkeypatch):
    def timed_out(*args,**kwargs):
        raise subprocess.TimeoutExpired('isolated-worker',.001)
    monkeypatch.setattr(reference.subprocess,'run',timed_out)
    with pytest.raises(TimeoutError,match='超时'):
        reference.run_reference(source,snapshot,timeout_seconds=.001)


def test_readonly_export_sees_committed_wal(snapshot, tmp_path):
    path = tmp_path/'original.db'
    writer = sqlite3.connect(path)
    try:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('CREATE TABLE etf_daily ('+','.join(f+' '+('TEXT' if f in ('date','code','signal_level','trade_direction') else 'REAL') for f in reference.DAILY_FIELDS)+')')
        writer.execute('CREATE TABLE market_turnover (date TEXT,total_amount_yi REAL)')
        writer.execute('CREATE TABLE margin_trading (date TEXT,fin_balance_yi REAL)')
        writer.execute('CREATE TABLE trade_calendar (date TEXT)')
        fields = reference.DAILY_FIELDS
        writer.executemany('INSERT INTO etf_daily VALUES ('+','.join('?' for _ in fields)+')', [[r[f] for f in fields] for r in snapshot['daily']['510300']])
        writer.executemany('INSERT INTO market_turnover VALUES (?,?)',[(r['date'],r['total_amount_yi']) for r in snapshot['turnover']])
        writer.executemany('INSERT INTO margin_trading VALUES (?,?)',[(r['date'],r['fin_balance_yi']) for r in snapshot['margin']])
        writer.executemany('INSERT INTO trade_calendar VALUES (?)',[(d,) for d in snapshot['calendar']])
        writer.commit()
        assert path.with_name(path.name+'-wal').is_file()
        before = writer.execute('SELECT count(*),sum(close_price) FROM etf_daily').fetchone()
        frozen = reference.export_database(path,('510300',))
        assert frozen['daily'] == snapshot['daily']
        assert frozen['source']['historical_available_at'] is None
        assert writer.execute('SELECT count(*),sum(close_price) FROM etf_daily').fetchone() == before
    finally:
        writer.close()


def test_cli_malformed_input_reports_failure_without_output(tmp_path, capsys):
    inp,out = tmp_path/'broken.json',tmp_path/'no-report.json'
    inp.write_text('{',encoding='utf8')
    assert main(['run','--source',str(tmp_path),'--input',str(inp),'--output',str(out)]) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'failed'
    assert not out.exists()


def test_cli_invalid_sqlite_returns_sanitized_failure(tmp_path, capsys):
    database, out = tmp_path/'missing-original-tables.db',tmp_path/'no-report.json'
    with sqlite3.connect(database) as conn:
        # 满足首个schema检查，让后续缺market_turnover实际触发sqlite3.Error。
        conn.execute('CREATE TABLE etf_daily ('+','.join(f+' '+('TEXT' if f in ('date','code','signal_level','trade_direction') else 'REAL') for f in reference.DAILY_FIELDS)+')')
    assert main(['export','--database',str(database),'--output',str(out)]) == 1
    response = json.loads(capsys.readouterr().out)
    assert response['status'] == 'failed'
    assert 'no such table' not in response['error']
    assert str(database) not in response['error']
    assert not out.exists()
