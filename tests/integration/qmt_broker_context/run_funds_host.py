"""已安装原生股票执行器与首账户资金查询；仅隔离SDK替身。"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import threading

ROOT = Path(__file__).resolve().parents[3]
for relative in ('apps/guanheng', 'connectors/qmt_shm/host', 'connectors/qmt_shm/agent',
                 'tests/integration/qmt_shm_trading', 'tests/integration/qmt_standard_trader',
                 'tests/integration/qmt_query_submission_group'):
    sys.path.insert(0, str(ROOT / relative))
from test_submission_group import GapFixture
from event_query_fixture import _Child, _FixtureOwners, decode, canonical, write_new, uptime_ms


class FundsFixture(GapFixture):
    def __init__(self, directory, deadline, scenario):
        super().__init__(directory, deadline, 'query_first')
        self.scenario, self.account_queries = scenario, 0

    def configure_host(self, configuration, credentials):
        value = super().configure_host(configuration, credentials)
        value['max_records'] = 16
        value['max_journal_bytes'] = 16 * self.read_budget['unit_bytes']
        self.read_budget.update(max_records=16, expected_queries=None,
                               max_journal_bytes=value['max_journal_bytes'])
        return value

    def detail(self, account, account_type, datatype):
        assert threading.get_ident() == self.owner_thread and (account, account_type) == ('SYNTHETIC', 'stock')
        assert len(self.queries) < 16 and datatype in ('position', 'order', 'deal', 'account')
        entry = {'datatype': datatype, 'thread': threading.get_ident(), 'sequence_enter': self.mark(),
                 'entered_uptime_ms': uptime_ms(), 'sdk_calls_at_query': len(self.sdk)}
        self.queries.append(entry)
        rows = []
        if datatype == 'position' and self.scenario.startswith('sellable-'):
            rows = [{'m_strAccountID': account, 'm_strMoneyType': 'CNY', 'm_strInstrumentID': '000001',
                     'm_strExchangeID': 'SZ', 'm_nVolume': 1000,
                     'm_nCanUseVolume': 200 if self.scenario == 'sellable-200' else 0}]
        if datatype == 'account':
            self.account_queries += 1
            available = 2500 if self.account_queries > 1 or self.scenario == 'positive' else 1000
            if self.scenario in ('generic-refresh', 'negative') and self.account_queries > 1:
                available = 20000
            if self.scenario == 'negative' and self.account_queries == 1:
                available = -1
            if self.scenario == 'zero' and self.account_queries == 1:
                available = 0
            if self.scenario != 'unknown' or self.account_queries > 1:
                rows = [{'m_strAccountID': account, 'm_strMoneyType': 'CNY', 'm_dBalance': 10000.,
                         'm_dAvailable': float(available), 'm_dPreBalance': 10000., 'm_dCommission': 0.,
                         'm_dFrozenCash': 0., 'm_dFrozenMargin': 0., 'm_dFrozenCommission': 0.,
                         'm_dPositionProfit': 0., 'm_dFloatProfit': 0.}]
        entry.update(returned_rows=decode(canonical(rows)), sequence_return=self.mark(), returned_uptime_ms=uptime_ms())
        return rows

    def insert(self, *values):
        assert threading.get_ident() == self.owner_thread and len(self.sdk) < 2 and len(self.queries) >= 4
        assert values[3] == '000001.SZ' and values[5] == 10.01 and values[0] in (23, 24)
        assert values[9] and values[9] not in self.tokens
        self.tokens.append(values[9])
        self.sdk.append({'operation': 'insert', 'thread': threading.get_ident(), 'args': list(values[:-1]),
                         'sequence': self.mark(), 'returning_uptime_ms': uptime_ms()})
        # 显式停留于SDK返回/尚无券商订单观察，原提交组持有未决责任；不伪造成交。


def main():
    p = argparse.ArgumentParser()
    for name in ('exe', 'dll', 'factory', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--deadline-uptime-ms', type=int, required=True)
    p.add_argument('--scenario', choices=('low', 'zero', 'unknown', 'positive', 'sellable-zero', 'sellable-200', 'generic-refresh', 'negative'), required=True)
    args = p.parse_args()
    args.output.mkdir()
    (args.output / 'owners').mkdir()
    fixture = FundsFixture(args.output, args.deadline_uptime_ms, args.scenario)
    owners, report = _FixtureOwners(), None

    def persist():
        value = fixture.facts();value['native_report'] = report
        write_new(args.output / 'fixture.json', value, args.deadline_uptime_ms)
        child = fixture.child
        post = {'child_exit_code': None if child is None else child.exit_code,
                'managed_reaped': bool(child and child.reaped),
                'managed_eof': bool(child and all(child.eof.values())),
                'managed_readers_joined': bool(child and child.reaped),
                'forced': bool(child and child.forced),
                'host_resources_closed': bool(fixture.host and fixture.host._closed_complete and fixture.host._io_resources_closed),
                'source_resources_closed': bool(fixture.agent and fixture.agent._io_resources_closed),
                'source_close_confirmed': bool(fixture.agent and fixture.agent.trading_close_confirmed),
                'server_joined': fixture.server_joined, 'proxy_joined': bool(fixture.proxy and fixture.proxy.joined),
                'source_error_present': fixture.first.facts() is not None,
                'proxy_error_present': bool(fixture.proxy and fixture.proxy.first.facts() is not None),
                'native_report_passed': bool(report and report.get('passed'))}
        write_new(args.output / 'POSTFLIGHT.json', post, args.deadline_uptime_ms)

    with owners:
        owners.callback(persist);fixture.start(owners)
        trader = fixture.trader();trader['module'] = 'TraderQMTStandard'
        value = {'work': str(args.output / 'runtime'), 'candidate_dll': str(args.dll),
                 'execution_factory': str(args.factory), 'hmac_secret': fixture.secret, 'trader': trader,
                 'scenario': args.scenario, 'deadline_uptime_ms': args.deadline_uptime_ms}
        write_new(args.output / 'input.json', value, args.deadline_uptime_ms)
        fixture.child = _Child(fixture.total_deadline);owners.callback(fixture.child.close)
        fixture.child.start(args.exe, args.output / 'input.json', args.output / 'native-result.json', fixture.work_deadline)
        fixture.pump_until(lambda: fixture.child.job.poll() is not None and fixture.child.job.active_processes() == 0)
        fixture.child.close()
        if (args.output / 'native-result.json').is_file():
            report = decode((args.output / 'native-result.json').read_bytes())
        assert fixture.child.exit_code == 0 and report and report['passed'], 'funds native business result'
        expected = 0 if args.scenario in ('sellable-zero', 'unknown') else 1
        assert len(fixture.sdk) == report['inserts'] == expected
        if fixture.sdk:
            assert fixture.sdk[0]['args'][0] == (24 if args.scenario == 'sellable-200' else 23)
            assert fixture.sdk[0]['args'][6] == (1000 if args.scenario in ('generic-refresh', 'negative') else 200)
        if args.scenario == 'unknown':
            assert report['source_account_rejected'] and report['queries'] == 3 and len(fixture.queries) == 4
            assert fixture.queries[-1]['datatype'] == 'account' and fixture.queries[-1]['returned_rows'] == []
        else:
            assert len(fixture.queries) == report['queries'] == (4 if args.scenario.startswith('sellable-') or args.scenario == 'positive' else 5)
        assert fixture.first.facts() is None and fixture.proxy.first.facts() is None
        assert fixture.child.reaped and not fixture.child.forced and all(fixture.child.eof.values())
    assert not owners.failures and fixture.host._closed_complete and fixture.host._io_resources_closed
    assert fixture.agent._io_resources_closed and fixture.agent.trading_close_confirmed
    assert fixture.server_joined and fixture.proxy.joined
    result = {'passed': True, 'scenario': args.scenario, 'queries': len(fixture.queries),
              'sdk_calls': len(fixture.sdk), 'first_inserts': report['first_inserts'],
              'new_command_quantity': (1000 if args.scenario in ('generic-refresh', 'negative') else 200) if fixture.sdk else 0,
              'real_broker_calls': 0,
              'host_closed': True, 'source_closed': True, 'proxy_joined': True,
              'managed_reaped': True, 'managed_eof': True, 'managed_readers_joined': True,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'qualification': 'recorded executor host scenario only; no fills, clean recovery or CTA strategy qualification'}
    write_new(args.output / 'RESULT.json', result, args.deadline_uptime_ms)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
