import time
from contextlib import contextmanager
from hashlib import sha256

import pytest

from guanheng_qmt_shm.journal import JournalConflict, JournalFull
from guanheng_qmt_shm.trading_journal import HostTradingJournal
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
from test_trade_bootstrap import agent_config


def end():
    return time.monotonic() + 10


def test_repeated_event_page_and_ack_skip_unchanged_writes_after_restart(tmp_path, monkeypatch):
    config = agent_config()
    config['operation_profiles']['account.trade_detail']['policy_version'] = '2.0'
    admitted = validate_trade_configuration(config)
    route = config['route']
    binding = admitted.trade_binding['binding_id']
    kw = dict(max_records=32, max_result_bytes=16384, max_request_bytes=8192,
              max_journal_bytes=32*(8192+16384+16384), trade_binding=admitted.trade_binding,
              max_trade_commands=admitted.trade_binding['max_commands'], max_trade_bytes=160_000,
              max_trade_result_bytes=admitted.profile['trade_profile']['limits']['max_call_result_bytes'],
              read_profile=admitted.profile,
              event_storage=dict(max_streams=4, max_events=1, max_bytes=12000, max_page_bytes=4096))
    path = tmp_path / 'event.sqlite'
    source = host_binding(route=route, generation='a'*32, host_instance_id='b'*32, journal_generation=None,
                          observation_identity=None, capability_sha256=sha256(canonical(admitted.profile)).hexdigest(),
                          schema_version='2.0')
    session = dict(host_binding=source, session_id='repeated-source')
    event = dict(schema_version='qmt.trade-event.v1', session_id=session['session_id'], binding_id=binding,
                 sequence=1, kind='error', payload=dict(order_args={'accountID': 'SYNTHETIC'}, err_msg='first'))
    page = dict(schema_version='qmt.trade-event-page.v1', session_id=session['session_id'], binding_id=binding,
                acknowledged_through=0, published_through=1, gap=None, events=[event])
    ack = canonical(dict(schema_version='qmt.trade-event-ack.v1', session_id=session['session_id'], through_seq=1))

    def ingest(owner, body):
        return owner.events.ingest(session, canonical(body), after_seq=0, limit=16, max_bytes=4096, deadline=end())

    owner = HostTradingJournal(path, route, **kw)
    try:
        ingest(owner, page)
        accepted = owner.events.acknowledge(session, ack, through_seq=1, deadline=end())
    finally:
        owner.close()

    owner = HostTradingJournal(path, route, **kw)
    try:
        counts = []
        check_capacity = owner.events._usage

        def record_capacity_check(db):
            counts.append(True)
            return check_capacity(db)

        monkeypatch.setattr(owner.events, '_usage', record_capacity_check)
        changes = owner._database.total_changes
        assert ingest(owner, page) == accepted
        assert owner.events.acknowledge(session, ack, through_seq=1, deadline=end()) == accepted
        with pytest.raises(JournalConflict):
            ingest(owner, dict(page, events=[dict(event, payload=dict(event['payload'], err_msg='different'))]))
        assert not counts
        assert owner._database.total_changes == changes

        gap = dict(code='source-unavailable', sequence=2)
        advanced_observation = ingest(owner, dict(page, gap=gap, published_through=2))
        assert advanced_observation['gap'] == gap
        assert advanced_observation['observed_published_through'] == 2
        assert advanced_observation['source_ack_through'] == accepted['source_ack_through']
        assert not counts
        with pytest.raises(JournalFull):
            ingest(owner, dict(page, gap=gap, published_through=2, events=[event, dict(event, sequence=2)]))
        # 超额事务回滚，旧占额不变，重复页仍能返回原收据。
        assert ingest(owner, page) == advanced_observation
        assert not counts
        assert owner.events.state(session, deadline=end()) == advanced_observation
        retained = decode(owner.events.read(session, after_seq=0, limit=16, max_bytes=4096, deadline=end()))
        assert retained['events'] == [event]
    finally:
        owner.close()


def test_event_capacity_recovers_after_ambiguous_commit(tmp_path, monkeypatch):
    from guanheng_qmt_shm.trade_event_records import TradeEventRecords

    config = agent_config()
    config['operation_profiles']['account.trade_detail']['policy_version'] = '2.0'
    admitted = validate_trade_configuration(config)
    route = config['route']
    binding = admitted.trade_binding['binding_id']
    owner = HostTradingJournal(
        tmp_path / 'late.sqlite', route, max_records=32, max_result_bytes=16384,
        max_request_bytes=8192, max_journal_bytes=32*(8192+16384+16384),
        trade_binding=admitted.trade_binding, max_trade_commands=admitted.trade_binding['max_commands'],
        max_trade_bytes=160000, max_trade_result_bytes=admitted.profile['trade_profile']['limits']['max_call_result_bytes'],
        read_profile=admitted.profile, event_storage=dict(max_streams=4, max_events=1, max_bytes=12000, max_page_bytes=4096))
    session = 'ambiguous-commit'
    source = dict(session_id=session, host_binding=host_binding(
        route=route, generation='a'*32, host_instance_id='b'*32, journal_generation=None,
        observation_identity=None, capability_sha256=sha256(canonical(admitted.profile)).hexdigest(), schema_version='2.0'))

    def ingest(sequence):
        event = dict(schema_version='qmt.trade-event.v1', session_id=session, binding_id=binding,
                     sequence=sequence, kind='error', payload=dict(order_args={'accountID': 'SYNTHETIC'}, err_msg='original'))
        page = dict(schema_version='qmt.trade-event-page.v1', session_id=session, binding_id=binding,
                    acknowledged_through=0, published_through=sequence, gap=None, events=[event])
        return owner.events.ingest(source, canonical(page), after_seq=sequence-1, limit=16, max_bytes=4096, deadline=end())

    try:
        transaction = owner._trade_transaction

        @contextmanager
        def committed_but_late(deadline):
            with transaction(deadline) as db:
                yield db
            raise TimeoutError('simulated late commit')

        with monkeypatch.context() as patch:
            patch.setattr(owner, '_trade_transaction', committed_but_late)
            with pytest.raises(TimeoutError, match='simulated late commit'):
                ingest(1)
        assert owner.events.state(source, deadline=end())['durable_through'] == 1
        full_scan = TradeEventRecords._usage
        rebuilt = []

        def track_rebuild(records, db):
            value = full_scan(records, db)
            rebuilt.append(value[1])
            return value

        monkeypatch.setattr(TradeEventRecords, '_usage', track_rebuild)
        assert ingest(1)['durable_through'] == 1
        assert rebuilt == [1]
        with pytest.raises(JournalFull):
            ingest(2)
        assert owner.events.state(source, deadline=end())['durable_through'] == 1
    finally:
        owner.close()
