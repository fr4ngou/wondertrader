"""报告可视化保护真实日期、缺口与原生成交/持仓语义。"""
from hashlib import sha256
from pathlib import Path
import pytest

from guanheng_app.backtest_visuals import build_visuals, native_tables


def test_return_gap_and_drawdown_use_initial_capital_without_filling():
    value = {'run_id': 'a', 'receipt_sha256': 'b', 'report_sha256': 'c',
             'metrics': {'initial_capital_cny': '100'},
             'points': [[20240102, '110'], [20240103, '99'], [20240104, None], [20240105, '105']]}
    trades = [{'date': 20240103, 'side': 'buy'}, {'date': 20240103, 'side': 'sell'}]
    result = build_visuals(value, trades, check=lambda: None)
    assert result['points'][0] == [20240102, None, 0, 0, 0, 0]
    assert result['points'][1] == [20240103, -10, -10, 1, 1, 0]
    assert result['points'][2] == [20240104, None, None, 0, 0, 0]
    assert result['points'][3][1] is None
    assert result['points'][3][2] == pytest.approx(-4.545454545454546)
    assert not build_visuals(value, None, check=lambda: None)['trades_available']


class Read:
    """模拟归档已经核验过的原件读取，测试投影仍核固定摘要。"""
    def __init__(self, data):
        self.data = data
    def check(self):
        pass
    def raw(self, path, maximum):
        assert len(self.data[path.name]) <= maximum
        return self.data[path.name]


def tables(trades, positions):
    data = {'trades.csv': trades.encode(), 'positions.csv': positions.encode()}
    expected = {f'outputs/example/{name}': sha256(raw).hexdigest() for name, raw in data.items()}
    return Read(data), {'configuration': {'name': 'example'}}, {'native_outputs': expected}


def test_same_minute_multiple_fills_and_holdings_keep_original_profit():
    reader, receipt, result = tables('code,time,direct,action,price,qty,tag,fee,barno\n'
        'SSE.ETF.510500,202401031500,LONG,OPEN,7.01,200,x,5,1\n'
        'SSE.ETF.510500,202401031500,LONG,CLOSE,7.03,100,x,6,1\n',
        'date,code,volume,closeprofit,dynprofit\n20240103,SSE.ETF.510500,100,2.00,-1.25\n')
    trades, holdings = native_tables(reader, Path('root'), receipt, result)
    assert [t['side'] for t in trades] == ['buy', 'sell']
    assert [t['index'] for t in trades] == [0, 1]
    assert sum(float(t['fee_cny']) for t in trades) == 11
    assert holdings == [{'date': 20240103, 'symbol': 'SSE.ETF.510500', 'quantity': '100', 'realized_cny': '2.00', 'floating_cny': '-1.25'}]


def test_csv_change_during_projection_is_rejected():
    reader, receipt, result = tables('code,time,direct,action,price,qty,tag,fee,barno\n', 'date,code,volume,closeprofit,dynprofit\n')
    reader.data['trades.csv'] += b'changed'
    with pytest.raises(ValueError, match='改变'):
        native_tables(reader, Path('root'), receipt, result)


def test_unknown_csv_format_remains_unknown_instead_of_zero():
    reader, receipt, result = tables('another,format\n', 'another,format\n')
    assert native_tables(reader, Path('root'), receipt, result) == (None, None)


def test_duplicate_snapshot_does_not_double_profit():
    reader, receipt, result = tables('code,time,direct,action,price,qty,tag,fee,barno\n',
        'date,code,volume,closeprofit,dynprofit\n20240103,SSE.ETF.510500,100,2,3\n20240103,SSE.ETF.510500,100,2,3\n')
    with pytest.raises(ValueError, match='重复'):
        native_tables(reader, Path('root'), receipt, result)
