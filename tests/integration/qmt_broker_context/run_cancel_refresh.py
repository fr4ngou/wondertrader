"""真实WinSHM/Host/WT执行链，券商SDK为隔离替身；旧夹具根须显式传入。"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import threading

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--legacy-fixtures', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--dll', type=Path, required=True)
    parser.add_argument('--factory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scenario', choices=('cancel-false', 'cancel-error', 'partial', 'missing-current'), required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    # 显式旧测试依赖只提供夹具；产品模块始终从当前源码加载。
    for part in ('qmt_shm_trading', 'qmt_standard_trader', 'qmt_query_submission_group'):
        sys.path.insert(0, str(args.legacy_fixtures / part))
    for part in ('apps/guanheng', 'connectors/qmt_shm/host', 'connectors/qmt_shm/agent'):
        sys.path.insert(0, str(ROOT / part))
    from test_submission_group import GapFixture
    from event_query_fixture import _Child, _FixtureOwners, canonical, decode, write_new, uptime_ms

    class Fixture(GapFixture):
        def __init__(self, *values):
            super().__init__(*values)
            self.cancelled = False  # 替身柜台的真实状态，与客户端撤单请求分别保存。

        def configure_host(self, configuration, credentials):
            value = super().configure_host(configuration, credentials)
            value['max_records'] = 64
            value['max_journal_bytes'] = 64 * self.read_budget['unit_bytes']
            return value

        def trader(self):
            value = super().trader()
            value.update(module='TraderQMTStandard', observation_refresh_ms=1000)
            return value

        def insert(self, *values):
            assert threading.get_ident() == self.owner_thread
            assert values[3] == '000001.SZ' and values[5] == 10.01
            expected = 800 if args.scenario == 'partial' and self.tokens else 1000
            assert values[6] == expected and len(self.tokens) < 2
            assert values[9] not in self.tokens
            self.tokens.append(values[9])
            self.sdk.append({'operation': 'insert', 'thread': threading.get_ident(), 'quantity': values[6], 'sequence': self.mark()})

        def cancel(self, *values):
            assert threading.get_ident() == self.owner_thread
            assert values[:3] == ('broker.1', 'SYNTHETIC', 'STOCK')
            self.sdk.append({'operation': 'cancel', 'thread': threading.get_ident(), 'sequence': self.mark()})
            self.cancelled = True
            # 不发送order/deal终态回报，必须由实际查询发现状态变化。
            if args.scenario == 'cancel-error':
                self.agent.on_error(self.context, {'accountID': 'SYNTHETIC', 'orderCode': '000001.SZ', 'opType': -1}, 'SYNTHETIC cancel rejected; inspect original order')
                return True
            return False

        def detail(self, account, account_type, datatype):
            assert threading.get_ident() == self.owner_thread and (account, account_type) == ('SYNTHETIC', 'stock')
            partial = args.scenario == 'partial' and bool(self.tokens)
            filled = 200 if partial else 0
            if datatype == 'position':
                rows = [{'m_strAccountID': account, 'm_strMoneyType': 'CNY', 'm_strInstrumentID': '000001',
                         'm_strExchangeID': 'SZ', 'm_nVolume': 100 + filled, 'm_nCanUseVolume': 100}]
            elif datatype == 'account':
                cash = 100000. - filled * 10.01
                frozen = (1000 - filled) * 10.01 if self.tokens and not self.cancelled else 0.
                rows = [{'m_strAccountID': account, 'm_strMoneyType': 'CNY', 'm_dBalance': cash,
                         'm_dAvailable': cash - frozen, 'm_dPreBalance': 100000., 'm_dCommission': 0.,
                         'm_dFrozenCash': frozen, 'm_dFrozenMargin': 0., 'm_dFrozenCommission': 0.,
                         'm_dPositionProfit': 0., 'm_dFloatProfit': 0.}]
            elif datatype == 'order':
                rows = []
                for index, token in enumerate(self.tokens):
                    if index == 0 and self.cancelled and args.scenario == 'missing-current':
                        continue
                    row = self.row('order', token)
                    done = filled if index == 0 else 0
                    ended = index == 0 and self.cancelled
                    row.update(m_strOrderSysID='broker.' + str(index + 1), m_nVolumeTotalOriginal=1000 if index == 0 else (800 if partial else 1000),
                               m_nVolumeTraded=done, m_nVolumeTotal=(1000 - done) if index == 0 else (800 if partial else 1000),
                               m_nOrderStatus=(53 if done else 54) if ended else (55 if done else 50),
                               m_dCancelAmount=(1000 - done) if ended else 0)
                    rows.append(row)
            elif datatype == 'deal':
                rows = []
            else:
                raise AssertionError('unexpected datatype')
            self.queries.append({'datatype': datatype, 'thread': threading.get_ident(), 'sequence': self.mark(),
                                 'cancelled': self.cancelled, 'returned_rows': decode(canonical(rows))})
            return rows

    total = uptime_ms() + 55000
    (args.output / 'owners').mkdir()
    fixture = Fixture(args.output, total, 'query_first')
    owners, report = _FixtureOwners(), None

    def persist():
        # 测试失败同样保留SDK调用、真实查询和子进程诊断；避免整份代理报文挤满证据预算。
        facts = {'native_report': report, 'sdk': fixture.sdk, 'queries': fixture.queries,
                 'first_error': fixture.first.facts(),
                 'proxy_first_error': None if fixture.proxy is None else fixture.proxy.first.facts(),
                 'owner_failures': [type(value).__name__ + ': ' + str(value)[:512] for value in owners.failures],
                 'child_output': {} if fixture.child is None else {
                     key: bytes(value).decode('utf-8', 'replace')[-16384:]
                     for key, value in fixture.child.output.items()}}
        write_new(args.output / 'fixture.json', facts, total)

    with owners:
        owners.callback(persist)
        fixture.start(owners)
        fixture.proxy.max_requests = 2048
        fixture.proxy.query_progress_capacity = 256
        value = {'work': str(args.output / 'runtime'), 'candidate_dll': str(args.dll),
                 'execution_factory': str(args.factory), 'hmac_secret': fixture.secret, 'trader': fixture.trader(),
                 'scenario': args.scenario, 'deadline_uptime_ms': total}
        write_new(args.output / 'input.json', value, total)
        fixture.child = _Child(fixture.total_deadline)
        owners.callback(fixture.child.close)
        fixture.child.start(args.exe, args.output / 'input.json', args.output / 'native-result.json', fixture.work_deadline)
        fixture.pump_until(lambda: fixture.child.job.poll() is not None and fixture.child.job.active_processes() == 0)
        fixture.child.close()
        if (args.output / 'native-result.json').is_file():
            report = decode((args.output / 'native-result.json').read_bytes())
        assert fixture.child.exit_code == 0 and report and report['passed'], report
        assert len(fixture.tokens) == (1 if args.scenario == 'missing-current' else 2)
        assert any(x['operation'] == 'cancel' for x in fixture.sdk)
        assert not fixture.callbacks  # 零订单终态推送；查询实际负责收敛。
        assert fixture.first.facts() is None and fixture.proxy.first.facts() is None
        assert fixture.child.reaped and not fixture.child.forced and all(fixture.child.eof.values())
    assert not owners.failures and fixture.host._closed_complete and fixture.agent._io_resources_closed
    result = {'passed': True, 'scenario': args.scenario, 'native': report, 'sdk_substitute_calls': fixture.sdk,
              'query_sequence': [x['datatype'] for x in fixture.queries], 'real_broker_calls': 0,
              'order_terminal_pushes': 0, 'resource_owners_closed': True,
              'case_outcome': ('identity_retained_with_inserts_paused' if args.scenario == 'missing-current'
                               else 'original_order_reconciled_executor_resumed'),
              'reconciliation_complete': args.scenario != 'missing-current',
              'qualification': 'real Host/WinSHM/standard plugin/WT order table and stock executor; synthetic broker; no CTA business strategy qualification',
              'dll_sha256': hashlib.sha256(args.dll.read_bytes()).hexdigest(),
              'exe_sha256': hashlib.sha256(args.exe.read_bytes()).hexdigest(),
              'factory_sha256': hashlib.sha256(args.factory.read_bytes()).hexdigest(),
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'legacy_fixture_sha256': {
                  str(Path(module.__file__).resolve().relative_to(args.legacy_fixtures.resolve())):
                      hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                  for module in tuple(sys.modules.values())
                  if getattr(module, '__file__', None)
                  and Path(module.__file__).resolve().is_relative_to(args.legacy_fixtures.resolve())
                  and Path(module.__file__).is_file()}}
    write_new(args.output / 'RESULT.json', result, total)
    print(json.dumps({'passed': True, 'scenario': args.scenario, 'queries': len(fixture.queries),
                      'inserts': len(fixture.tokens), 'terminal_confirmed': report['original_order_terminal'], 'real_broker_calls': 0}))


if __name__ == '__main__':
    main()
