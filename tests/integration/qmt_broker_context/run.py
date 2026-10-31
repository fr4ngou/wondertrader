"""正式标准插件/Context的正向链；真实WinSHM运输，券商SDK为独立替身。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
for relative in ('apps/guanheng', 'connectors/qmt_shm/host', 'connectors/qmt_shm/agent',
                 'tests/integration/qmt_shm_trading', 'tests/integration/qmt_standard_trader',
                 'tests/integration/qmt_query_submission_group'):
    sys.path.insert(0, str(ROOT / relative))
from test_submission_group import GapFixture
from event_query_fixture import _Child, _FixtureOwners, write_new, decode, canonical, check_deadline, uptime_ms
import threading


class ActiveOrderFixture(GapFixture):
    """同一真实ORDER查询返回柜台余量；不制造成交事件或本地数量增减。"""
    def detail(self, account, account_type, datatype):
        rows = super().detail(account, account_type, datatype)
        if datatype == 'order' and self.tokens:
            rows = [self.row('order', self.tokens[0])]
            self.queries[-1]['returned_rows'] = decode(canonical(rows))
        return rows


class NativeCancelFixture(ActiveOrderFixture):
    """只在显式验收中允许 SDK 替身撤单；完整查询保持活动余量80。"""
    def configure_host(self, configuration, credentials):
        value = super().configure_host(configuration, credentials)
        value['max_records'] = max(value['max_records'], 11)
        value['max_journal_bytes'] = value['max_records'] * self.read_budget['unit_bytes']
        self.read_budget.update(max_records=value['max_records'], expected_queries=11,
                               max_journal_bytes=value['max_journal_bytes'])
        return value

    def detail(self, account, account_type, datatype):
        if len(self.queries) < 8:
            return super().detail(account, account_type, datatype)
        if (threading.get_ident() != self.owner_thread or (account, account_type) != ('SYNTHETIC', 'stock')
                or len(self.queries) >= 11 or datatype != ['account', 'order', 'position'][len(self.queries)-8]):
            raise AssertionError('late trade original account/order/position refresh')
        rows = next(item['returned_rows'] for item in reversed(self.queries) if item['datatype'] == datatype)
        self.queries.append({'datatype': datatype, 'thread': threading.get_ident(),
                             'sequence_enter': self.mark(), 'returned_rows': rows,
                             'sequence_return': self.mark(), 'sdk_calls_at_query': len(self.sdk),
                             'entered_uptime_ms': uptime_ms(), 'returned_uptime_ms': uptime_ms()})
        return rows

    def trader(self):
        value = super().trader()
        # 一笔订单重复查询四次仍应低于两笔门槛；原生检查公开入口验真。
        value['riskmon'] = {'active': True, 'policy': {'default': {
            'order_total_limits': 2, 'cancel_total_limits': 2,
            'order_times_boundary': 100, 'cancel_times_boundary': 100,
            'order_stat_timespan': 60, 'cancel_stat_timespan': 60}}}
        return value

    def cancel(self, *args):
        if (threading.get_ident() != self.owner_thread or len(args) != 4
                or args[:3] != ('broker.1', 'SYNTHETIC', 'STOCK')
                or any(item['operation'] == 'cancel' for item in self.sdk)):
            raise AssertionError('explicit original cancel owner/identity/once')
        self.sdk.append({'operation': 'cancel', 'thread': threading.get_ident(),
                         'args': list(args[:-1]), 'sequence': self.mark()})
        return True


class CycleFixture(GapFixture):
    def __init__(self, *args, cycle_mode, **kwargs):
        super().__init__(*args, **kwargs)
        self.cycle_mode = cycle_mode

    def detail(self, account, account_type, datatype):
        if threading.get_ident() != self.owner_thread or (account, account_type) != ('SYNTHETIC', 'stock'):
            raise AssertionError('cycle original SDK owner')
        sequence = ['position', 'order', 'deal', 'account', 'order', 'position', 'order', 'position']
        if len(self.queries) >= len(sequence) or sequence[len(self.queries)] != datatype:
            raise AssertionError('cycle order-terminal then position sequence')
        record = {'datatype': datatype, 'thread': threading.get_ident(), 'entered_uptime_ms': uptime_ms(),
                  'sdk_calls_at_query': len(self.sdk), 'sequence_enter': self.mark()}
        self.queries.append(record)
        if datatype == 'position':
            # 券商替身直接返回各轮完整持仓；产品代码不按成交重算该值。
            total = 100 + len(self.tokens) * (100 if self.cycle_mode == 'filled' else 20)
            rows = [{'m_strAccountID': account, 'm_strMoneyType': 'CNY', 'm_strInstrumentID': '000001',
                     'm_strExchangeID': 'SZ', 'm_nVolume': total, 'm_nCanUseVolume': 100}]
        elif datatype == 'order':
            rows = []
            for index, token in enumerate(self.tokens):
                row = self.row('order', token)
                row['m_strOrderSysID'] = 'broker.' + str(index + 1)
                if self.cycle_mode == 'filled':
                    row.update(m_nOrderStatus=56, m_nVolumeTraded=100, m_nVolumeTotal=0, m_dCancelAmount=0)
                else:
                    row.update(m_nOrderStatus=53, m_nVolumeTraded=20, m_nVolumeTotal=80, m_dCancelAmount=80)
                rows.append(row)
        elif datatype == 'deal':
            rows = []
        else:
            rows = [{'m_strAccountID': account, 'm_strMoneyType': 'CNY', 'm_dBalance': 10000.,
                     'm_dAvailable': 8000., 'm_dPreBalance': 10000., 'm_dCommission': 0.,
                     'm_dFrozenCash': 2000., 'm_dFrozenMargin': 0., 'm_dFrozenCommission': 0.,
                     'm_dPositionProfit': 0., 'm_dFloatProfit': 0.}]
        record['returned_rows'] = decode(canonical(rows))
        record['sequence_return'] = self.mark()
        record['returned_uptime_ms'] = uptime_ms()
        return rows


def run_case(options, mode, active_order=False, cycle_mode=None, verify_order_cache=False, owner_execution=False):
    directory = options.output / (mode + ('-active-order' if active_order else '') + ('-' + cycle_mode if cycle_mode else ''))
    directory.mkdir()
    (directory / 'owners').mkdir()
    fixture_type = NativeCancelFixture if verify_order_cache else CycleFixture if cycle_mode else ActiveOrderFixture if active_order else GapFixture
    fixture = fixture_type(directory, options.deadline_uptime_ms, mode, **({'cycle_mode': cycle_mode} if cycle_mode else {}))
    owners = _FixtureOwners()
    report = None

    def persist():
        facts = fixture.facts()
        facts['native_report'] = report
        write_new(directory / 'fixture.json', facts, options.deadline_uptime_ms)

    with owners:
        owners.callback(persist)
        fixture.start(owners)
        trader = fixture.trader()
        trader['module'] = 'TraderQMTStandard'
        native_input = {
            'work': str(directory / 'runtime'), 'candidate_dll': str(options.dll),
            'hmac_secret': fixture.secret, 'trader': trader,
            'order_context': mode, 'deadline_uptime_ms': options.deadline_uptime_ms,
            'active_order': active_order, 'verify_order_cache': verify_order_cache,
        }
        if owner_execution:
            native_input.update(owner_execution=True, execution_factory=str(options.factory))
        if cycle_mode:
            native_input['cycle_mode'] = cycle_mode
        write_new(directory / 'input.json', native_input, options.deadline_uptime_ms)
        fixture.child = _Child(fixture.total_deadline)
        owners.callback(fixture.child.close)
        fixture.child.start(options.exe, directory / 'input.json', directory / 'native-result.json', fixture.work_deadline)
        fixture.pump_until(lambda: fixture.child.job.poll() is not None and fixture.child.job.active_processes() == 0)
        fixture.child.close()
        if (directory / 'native-result.json').is_file():
            report = decode((directory / 'native-result.json').read_bytes())
        if fixture.child.exit_code != 0 or not report or not report['passed']:
            raise AssertionError({'native': report, 'exit_code': fixture.child.exit_code})
        expected = 2 if cycle_mode else 4 if mode == 'native' else 1
        if verify_order_cache:
            assert report['queried_active_orders'] == 1 and report['native_cached_orders'] == 1
            assert report['native_cancel_returned'] is True and report['cancel_transport_calls'] == 1
            assert report['repeated_query_statistics_stable'] is True
            assert report['late_trade_quantity'] == 20 and report['late_trade_remaining_quantity'] == 80
        assert report['inserts'] == sum(item['operation'] == 'insert' for item in fixture.sdk) == expected
        assert sum(item['operation'] == 'cancel' for item in fixture.sdk) == (1 if verify_order_cache else 0)
        assert report['queries'] == len(fixture.queries) == (11 if verify_order_cache else 8)
        expected_position = 300 if cycle_mode == 'filled' else 140 if cycle_mode else 100
        assert report['position'] == expected_position and report['closed'] and report['deleted']
        assert report['remaining_quantity'] == (80 if active_order else 0)
        assert [c['new_order_ids'] for c in report['calls']] == ([1, 1] if cycle_mode else [1] * 4 if mode == 'native' else [1, 0, 0, 0])
        if mode == 'query_first' and not cycle_mode and not owner_execution:
            assert [c['decision'] for c in report['calls']] == [0, 1, 1, 1]
        assert all(item['thread'] == fixture.owner_thread for item in fixture.sdk + fixture.queries)
        assert all(item['operation'] in ('insert', 'cancel') for item in fixture.sdk)
        if not active_order and not cycle_mode:
            assert all(query['returned_rows'] == [] for query in fixture.queries if query['datatype'] in ('order', 'deal'))
        assert fixture.first.facts() is None and fixture.proxy.first.facts() is None
        assert fixture.child.reaped and not fixture.child.forced and all(fixture.child.eof.values())
        assert hashlib.sha256((directory / 'runtime/traders/TraderQMTStandard.dll').read_bytes()).hexdigest() == hashlib.sha256(options.dll.read_bytes()).hexdigest()
    assert owners.failures == []
    assert fixture.host._closed_complete and fixture.host._io_resources_closed
    assert fixture.agent._io_resources_closed and fixture.agent.trading_close_confirmed
    assert fixture.server_joined and fixture.proxy.joined
    check_deadline(options.deadline_uptime_ms)
    return {'mode': mode, 'passed': True, 'queries': report['queries'], 'sdk_substitute_calls': report['inserts'],
            'broker_position': report['position'], 'remaining_quantity': report['remaining_quantity'],
            'active_order': active_order, 'cycle_mode': cycle_mode, 'owner_execution': owner_execution, 'closed': True, 'real_broker_calls': 0,
            'order_cache_sync': {key: report[key] for key in ('queried_active_orders', 'native_cached_orders',
                'native_cancel_returned', 'cancel_transport_calls')} if verify_order_cache else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--dll', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deadline-uptime-ms', type=int, required=True)
    parser.add_argument('--verify-order-cache', action='store_true')
    parser.add_argument('--execution-owner', action='store_true')
    parser.add_argument('--factory', type=Path)
    options = parser.parse_args()
    if not options.exe.is_file() or not options.dll.is_file() or not options.output.is_dir():
        raise ValueError('explicit artifacts and new existing output directory required')
    if options.execution_owner:
        if options.factory is None or not options.factory.is_file() or options.verify_order_cache:
            raise ValueError('explicit original execution factory required')
        results = [run_case(options, 'query_first', owner_execution=True),
                   run_case(options, 'query_first', active_order=True, owner_execution=True)]
    elif options.verify_order_cache:
        results = [run_case(options, 'query_first', active_order=True, verify_order_cache=True)]
    else:
        results = [run_case(options, mode) for mode in ('native', 'query_first')]
        results.append(run_case(options, 'query_first', active_order=True))
        results.append(run_case(options, 'query_first', cycle_mode='filled'))
        results.append(run_case(options, 'query_first', cycle_mode='partial-canceled'))
    write_new(options.output / 'RESULT.json', {'passed': True, 'cases': results,
        'scope': 'positive main path; no real broker orders or production qualification'}, options.deadline_uptime_ms)
    print(json.dumps(results))


if __name__ == '__main__':
    main()
