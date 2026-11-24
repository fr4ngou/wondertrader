"""同绑定账户2→3的真实SQLite接续；无网络、SDK或生产资料。"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import sqlite3
from time import monotonic
from uuid import uuid4

import pytest

from guanheng_qmt_shm_agent.account_query import AccountQueryAdapter
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.results import finalize_result
from guanheng_qmt_shm_agent.trading_contract import command_digest
from guanheng_qmt_shm.journal import JournalConflict
from guanheng_qmt_shm.trade_binding_extension import VERSION
from guanheng_qmt_shm.trade_binding_maintenance import open_binding_extension_owner
from guanheng_qmt_shm.trade_event_records import CONTINUITY_VERSION
from guanheng_qmt_shm.trading_journal import HostTradingJournal

from test_trade_capabilities import binding, profile, request, trade_profile


NOW = datetime(2026, 11, 6, 7, tzinfo=timezone.utc)


def end():
    return monotonic() + 10


def original_configuration():
    # 复用已登记的合成能力原件；本轮只升级读取投影，交易绑定逐字保持。
    private = dict(binding(), schema_version='qmt.trade-binding.v2')
    private.pop('symbol_rules')
    descriptor = trade_profile(private)
    descriptor['limits'].update(max_command_bytes=4096, max_command_ttl_ms=5000,
        max_call_result_bytes=1024, max_events=16, max_event_bytes=2048,
        max_total_event_bytes=8192, max_event_page_bytes=4096)
    read = profile(descriptor=descriptor)
    read['operation_profiles']['account.trade_detail']['policy_version'] = '2.0'
    return dict(max_records=32, max_result_bytes=16384, max_request_bytes=8192,
        max_journal_bytes=32 * (8192 + 16384 + 16384), trade_binding=private,
        max_trade_commands=16, max_trade_bytes=200000, max_trade_result_bytes=1024,
        read_profile=read, event_storage=dict(max_streams=4, max_events=32,
        max_bytes=60000, max_page_bytes=4096), connection_continuity=CONTINUITY_VERSION)


def source(route, read, generation='a'):
    return host_binding(route=route, generation=generation * 32,
        host_instance_id='b' * 32, journal_generation=None, observation_identity=None,
        capability_sha256=sha256(canonical(read)).hexdigest(), schema_version='2.0')


def unknown_insert(owner, actual, number):
    command = dict(schema_version='qmt.trade-command.v1', command_id=str(uuid4()),
        operation='order.insert', binding_id='synthetic-only', account_id='SYNTHETIC',
        account_type='stock', entrust_id=f'fee.upgrade.{number}', user_tag=f'fee.tag.{number}',
        symbol='000001.SZ', side='buy', order_type='limit', limit_price='10.01',
        quantity=100, sdk_user_order_id=f'fee.token.{number}')
    owner.submit_trade(canonical(command), actual, ttl_ms=5000, deadline=end())
    claimed = owner.claim_trade(actual, deadline=end())
    assert claimed['command_id'] == command['command_id']
    # 真实进入结果未知，沿公开收据落账；后继维护不能改成未调用或重新派发。
    answer = dict(schema_version='qmt.trade-call-result.v1',
        command_id=command['command_id'], command_sha256=command_digest(command),
        operation='order.insert', stage='unknown', sdk_entered=True,
        signal_sent=None, error_code='sdk_exception')
    owner.finish_trade(command['command_id'], answer, actual, deadline=end())
    return command


def observe_terminal(owner, actual, command, version):
    query = request('account.trade_detail')
    query.update(request_id=str(uuid4()), correlation_id=str(uuid4()), policy_version=str(version) + '.0')
    query['arguments']['datatype'] = 'order'
    row = dict(m_strAccountID='SYNTHETIC', m_strInstrumentID='000001', m_strExchangeID='SZ',
        m_strRemark=command['sdk_user_order_id'], m_strOrderSysID=f"broker.{command['user_tag']}",
        m_strOrderRef='original-reference', m_strInsertDate='20261106', m_strInsertTime='09:30:00',
        m_nVolumeTotalOriginal=100, m_nVolumeTraded=100, m_nVolumeTotal=0,
        m_nOrderStatus=56, m_nOffsetFlag=48, m_dLimitPrice=10.01)
    limits = owner.admission_profile['operation_profiles']['account.trade_detail']['limits']
    adapter = AccountQueryAdapter(lambda *args: [row], limits, 16384, clock=lambda: 0,
        utc_now=lambda: NOW, projection_version=version)
    answer = finalize_result(dict(request_id=query['request_id'], operation_id='account.trade_detail',
        ok=True, completed_at=NOW.isoformat().replace('+00:00', 'Z'),
        data=adapter.execute(query['arguments'], 10)), 16384)
    assert answer['data']['schema_version'] == f'qmt.account-batch.v{version}'
    rid = owner.submit_bound(canonical(query), actual, queue_timeout_ms=1000, deadline=end())
    claimed = owner.claim_bound(actual, deadline=end())
    assert claimed[0] == rid
    owner.finish_bound(rid, answer, actual, deadline=end())
    return rid


def original_tables(path):
    """只读核全部原表字节；允许维护新增自己的版本表。"""
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                  if row[0] not in ('trade_binding_versions', 'trade_binding_current')]
        assert db.execute('PRAGMA quick_check').fetchall() == [('ok',)]
        return {name: db.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall() for name in tables}


@pytest.mark.parametrize('unresolved', [False, True])
def test_same_binding_fee_upgrade_preserves_old_proof_and_unknown(tmp_path, unresolved):
    path = tmp_path / 'communication.sqlite'
    route = dict(route_id='fee-profile-upgrade', executor_id='synthetic', route_epoch=1)
    old = original_configuration()
    actual = source(route, old['read_profile'])
    owner = HostTradingJournal(path, route, **old)
    try:
        first = unknown_insert(owner, actual, 1)
        assert owner.trade_admission(deadline=end()) == {'unknown_fenced': True, 'hard_fault': None}
        rid = observe_terminal(owner, actual, first, 2)
        assert owner.trade_admission(deadline=end()) == {'unknown_fenced': False, 'hard_fault': None}
        proof = owner.lookup_trade_order(dict(sdk_user_order_id=first['sdk_user_order_id']), deadline=end())
        assert proof['query_observation']['request_id'] == rid
        commands = [first]
        if unresolved:
            commands.append(unknown_insert(owner, actual, 2))
        saved = [owner.get_trade(item['command_id'], deadline=end()) for item in commands]
        saved_read = owner.get_bound(rid, deadline=end())
        assert all(item['state'] == 'unknown' for item in saved)
    finally:
        owner.close(deadline=end())
    original = original_tables(path)
    newer = deepcopy(old)
    newer['read_profile']['operation_profiles']['account.trade_detail']['policy_version'] = '3.0'
    assert newer['trade_binding'] == old['trade_binding']
    owner = open_binding_extension_owner(path, route, deadline=end(), **old)
    try:
        plan = owner.prepare_binding_extension(old['trade_binding'], 'c' * 64, {},
            read_profile=newer['read_profile'], deadline=end())
        adopted = owner.adopt_binding_extension(plan, deadline=end())
        assert adopted['version'] == 2
        assert owner.adopt_binding_extension(plan, deadline=end()) == adopted
    finally:
        owner.close(deadline=end())
    assert original_tables(path) == original
    newer['trade_binding_extension'] = VERSION
    for unused in range(2):
        # 每次重开均通过真实构造/原proof验证；旧unknown结果及原委托身份不被改写。
        owner = HostTradingJournal(path, route, **newer)
        try:
            assert owner.trade_admission(deadline=end()) == {'unknown_fenced': unresolved, 'hard_fault': None}
            assert owner.get_bound(rid, deadline=end()) == saved_read
            assert owner.lookup_trade_order(dict(sdk_user_order_id=first['sdk_user_order_id']), deadline=end()) == proof
            assert [owner.get_trade(item['command_id'], deadline=end()) for item in commands] == saved
            assert owner.claim_trade(source(route, newer['read_profile'], 'c'), deadline=end()) is None
        finally:
            owner.close(deadline=end())
        assert original_tables(path) == original
    for extra in ({}, {'trade_binding_extension': VERSION}):
        with pytest.raises(JournalConflict):
            HostTradingJournal(path, route, **dict(old, **extra))
        assert original_tables(path) == original
    owner = HostTradingJournal(path, route, **newer)
    try:
        if unresolved:
            # 新3查询沿原token核回原unknown；始终使用原UUID，未创建新金融命令。
            observe_terminal(owner, source(route, newer['read_profile'], 'c'), commands[-1], 3)
        assert owner.trade_admission(deadline=end()) == {'unknown_fenced': False, 'hard_fault': None}
        assert [owner.get_trade(item['command_id'], deadline=end()) for item in commands] == saved
        assert owner.lookup_trade_order(dict(sdk_user_order_id=first['sdk_user_order_id']), deadline=end()) == proof
    finally:
        owner.close(deadline=end())
