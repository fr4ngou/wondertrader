"""受控共享账户材料→惰性原Native借用；全部为独立合成材料。"""
import ctypes as C
from datetime import date, timedelta
import hashlib
import json
from types import SimpleNamespace
from time import monotonic
from uuid import uuid4

import pytest

from guanheng_wt_runtime.account_attribution import create_runtime_attribution, NativeEvent, NativeReply
from guanheng_strategy_original.reference import DEFAULT_CODES
from guanheng_market_client.exchange_calendar import encode


def test_frozen_seed_creates_book_only_inside_native_borrow_and_preserves_million(tmp_path):
    def save(name, value):
        path = tmp_path/name;raw=encode(value);path.write_bytes(raw)
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
    original_id='resonance-original-wt-351f9d5-stable';old_id='resonance-regime-v1'
    universe=sorted(('SZSE' if c.startswith('1') else 'SSE')+'.ETF.'+c for c in DEFAULT_CODES)
    old_basis=save('old-basis.json',dict(schema='synthetic-old-basis',cash_cny='12345.67'))
    account=save('account.json',dict(schema='synthetic-account',positions=[],available_cny='2000000.00'))
    scope=dict(account='SYNTHETIC', environment='simulation', currency='CNY')
    scope_sha=hashlib.sha256(json.dumps(scope,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest()
    initial=dict(schema='guanheng.account-allocation-seed.v1', seeds=[
        dict(strategy_id=old_id,version='1.2.2',cash_cny='12345.67',positions=[],priority=0,universe=[universe[0]]),
        dict(strategy_id=original_id,version='0.2.0a1',cash_cny='1000000',positions=[],priority=1,universe=universe)],
        unallocated_cash_cny='0',account_snapshot=dict(revision=1,trading_day='2026-11-06',available_cny='2000000.00',
        positions=[],source_sha256=account['sha256']),source_evidence=dict(old_basis=old_basis,account_observation=account))
    start,finish=date(2026,11,1),date(2026,11,10)
    opens=[(start+timedelta(days=i)).isoformat()for i in range((finish-start).days+1)
           if(start+timedelta(days=i)).weekday()<5]
    calendar=save('calendar.json',dict(id='synthetic-calendar',kind='official-exchange-calendar/v1',
        coverage_start=start.isoformat(),coverage_end=finish.isoformat(),verified_through=finish.isoformat(),
        closed_dates=[],verified_open_dates_sha256=hashlib.sha256(encode(opens)).hexdigest(),method='synthetic',evidence=[]))
    fee=save('fees.json',dict(schema='guanheng.asa-fee-reserve.v1',source='synthetic explicit model',securities={
        symbol:{side:dict(fixed_cny='5',per_share_cny='0.01')for side in('buy','sell')}for symbol in universe}))
    financial=tmp_path/'financial';financial.mkdir()
    shared=save('shared.json',dict(schema='guanheng.shared-account-allocation.v1',identity=dict(
        account_scope_sha256=scope_sha,financial_book_id=str(uuid4()),baseline_sha256=old_basis['sha256']),
        financial_root=str(financial),initialization=save('initial.json',initial),calendar=calendar,
        fee_reserve_model=fee,callback_seconds=5))
    native=dict(output_directory=str(financial),trader=dict(expected_account='SYNTHETIC',environment='simulation'),strategies=[
        dict(id=old_id,parameters=dict(python_strategy=dict(schema='guanheng.retained-cta.v1'))),
        dict(id=original_id,parameters=dict(python_strategy=dict(schema='guanheng.original-live-cta.v1',shared_account=shared,strategy_version='0.2.0a1')))])
    coordinator,bridge=create_runtime_attribution(native,SimpleNamespace(configuration=tmp_path/'execution.json'),
        tmp_path,str(uuid4()),deadline=monotonic()+10)
    assert coordinator._account_observation_day('2026-11-07') == '2026-11-06'
    assert coordinator._account_observation_day('2026-11-09') == '2026-11-09'
    assert coordinator._account_observation_day('2026-11-11') is None
    assert not(financial/'account-allocation.sqlite3').exists()
    with pytest.raises(RuntimeError,match='attribution_owner_not_borrowed'):
        coordinator.view(original_id,deadline=monotonic()+5)
    assert not(financial/'account-allocation.sqlite3').exists()
    bridge.bind_owner(SimpleNamespace(financial_borrowed=lambda: bridge.callback_active))
    balances=[]
    handle=bridge._handler
    def capture(event):
        result=handle(event)
        balances.append((str(coordinator.view(old_id,deadline=event.deadline).ledger_cash_cny),
                         str(coordinator.view(original_id,deadline=event.deadline).ledger_cash_cny)))
        return result
    bridge._handler=capture
    coordinator.prepare_intent(original_id,1,source_sha256='a'*64,known_at='2026-11-06T07:00:00+00:00',
        buy_price_caps={},common_prices=(),deadline=monotonic()+5)
    raw=encode(dict(strategy_id=original_id,targets=[dict(symbol=s,quantity=0)for s in universe]))
    buffer=C.create_string_buffer(raw)
    event=NativeEvent(C.sizeof(NativeEvent),1,1,1,1,0,len(raw),0,C.cast(buffer,C.c_void_p))
    reply=NativeReply(C.sizeof(NativeReply),1,-1,0,0)
    assert bridge._callback(C.byref(event),C.byref(reply),None)==0,bridge.failure
    assert(financial/'account-allocation.sqlite3').exists()
    assert balances == [('12345.67','1000000.00')]
    # 返回回调后即收回借用；无法借后台普通线程绕过原Native owner。
    with pytest.raises(RuntimeError,match='attribution_owner_not_borrowed'):
        coordinator.view(original_id,deadline=monotonic()+5)
