"""查询和实时回报只在显式账户3.0能力下增加费用字段。"""
from datetime import datetime, timezone

import pytest

from guanheng_qmt_shm_agent.account_query import AccountQueryAdapter


@pytest.mark.parametrize('alias', ['m_dCommission', 'm_dComission', 'm_dComssion'])
@pytest.mark.parametrize('value', [None, 0, 5.01403])
@pytest.mark.parametrize('version', [1, 2, 3])
def test_original_fee_precision_only_on_explicit_trade_projection(alias, value, version):
    calls = []
    source = {alias: value, 'm_strAccountID': 'SYNTHETIC'}
    limits = dict(schema_version='qmt.account-read.v1', account_binding=dict(
        account_id='SYNTHETIC', account_environment='live', currency='CNY',
        financial_profile='cny_cash_shsz_v1'), max_rows=4096, max_nodes=65536,
        max_scalar_chars=262144, max_data_bytes=8192)

    def read(*arguments):
        calls.append(arguments)
        return [source]

    adapter = AccountQueryAdapter(read, limits, 16384, clock=lambda: 0,
        utc_now=lambda: datetime(2026, 11, 24, tzinfo=timezone.utc), projection_version=version)
    result = adapter.execute(dict(account_type='stock', datatype='deal', scope='account'), 10)
    assert calls == [('SYNTHETIC', 'stock', 'deal')]
    assert source == {alias: value, 'm_strAccountID': 'SYNTHETIC'}
    if version == 3:
        assert alias in result['rows'][0] and result['rows'][0][alias] == value
    else:
        assert alias not in result['rows'][0]


@pytest.mark.parametrize('version', [1, 2, 3])
def test_callback_snapshot_uses_admitted_projection_and_keeps_original_alias(version):
    from guanheng_qmt_shm_agent.trade_events import TradeEventBuffer
    from guanheng_qmt_shm_agent.protocol import decode
    from guanheng_qmt_shm_agent.trading_kernel import snapshot_deal
    original = dict(m_strAccountID='SYNTHETIC', m_strTradeID='fill',
                    m_dComssion=5.01403, m_dCommission=5.01403, m_dComission=5.01403)
    expected = original if version == 3 else {k: v for k, v in original.items()
        if k not in ('m_dCommission', 'm_dComission')}
    assert snapshot_deal(original, projection_version=version) == expected
    buffer = TradeEventBuffer('session', 'binding', max_events=4, max_event_bytes=4096,
        max_total_bytes=16384, on_gap=lambda _: pytest.fail('unexpected gap'),
        account_id='SYNTHETIC', projection_version=version)
    buffer.capture('deal', original)
    assert decode(buffer._tickets[1])['payload'] == expected
