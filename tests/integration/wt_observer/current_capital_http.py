"""普通只读安装经真实WRI/NRT文件到ASGI GET；来源由隔离SDK主链提供。"""
import argparse
from datetime import datetime, timezone, timedelta
from fractions import Fraction as Decimal
import importlib.metadata
import json
from pathlib import Path
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ready',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expect-closed',action='store_true')
    args=parser.parse_args()
    from fastapi.testclient import TestClient
    from guanheng_app.app import create_app
    from guanheng_app.settings import ConsoleSettings
    from guanheng_app.strategy_capital_projection import project_capital
    import guanheng_app.strategy_capital_projection as projection
    ready=json.loads(args.ready.read_bytes())
    settings=ConsoleSettings(wt_status_file=ready['status_file'],wt_control_id=ready['control_id'],
        wt_instance_id=ready['instance_id'],wt_configuration_sha256=ready['configuration_sha256'],
        account_source='wt_account_publication')
    app=create_app(settings)
    source_values=[]
    def observed_projection(value,origin,**kwargs):
        if value is not None:source_values.append(dict(value))
        return project_capital(value,origin,**kwargs)
    with patch.object(projection,'project_capital',side_effect=observed_projection), TestClient(app) as client:
        r=client.get('/v1/ui/strategy-details')
        if r.status_code!=200:
            raise AssertionError('strategy details GET failed:'+str(r.status_code))
        details=r.json();assert details['budget_cny']['value']=='1000000'
        cap=details['capital'];assert cap is not None
        assert cap['baseline']['total_cny']=='1000000' and cap['baseline']['historical_initial_capital_cny']is None
        assert cap['historical_return_pct']is None
        assert Decimal(cap['nav_cny'])==Decimal(1000000)+Decimal(cap['native_pnl_cny'])
        # 各GET消费当次发布；行情继续到达时，旧ready样本与后继GET可属不同轮。
        assert cap['observed_at']==source_values[-1]['observed_at']
        assert cap['account_observed_at']==source_values[-1]['account_observed_at']
        assert cap['position_observed_at']==source_values[-1]['position_observed_at']
        if args.expect_closed:
            assert not cap['account_observation_qualified'] and cap['spendable_cash_cny'] is None
        else:
            assert cap['account_observation_qualified'] and cap['spendable_cash_cny'] is not None
        r=client.get('/v1/ui/strategy-runtime');assert r.status_code==200
        runtime_capital=r.json()['strategy']['capital']
        for field in ('observed_at','account_observed_at','position_observed_at','nav_cny','cash_balance_cny','market_value_cny'):
            assert runtime_capital[field]==source_values[-1][field]
        r=client.get('/v1/ui/account/overview');assert r.status_code==200
        account=r.json();asset=account['groups']['account']['rows'][0]['fields']['total_asset']['value']
        assert abs(Decimal(str(asset))-Decimal(200000000))<Decimal('.000001')
        assert Decimal(cap['nav_cny'])<Decimal(2000000)
        assert client.post('/v1/ui/strategy-details').status_code==405
    assert app.state.shutdown_complete
    # 停止、过期及缺当前账户约束分别保持原时间；当前可用资格不会随GET恢复。
    stopped=project_capital(ready['capital'],ready['capital']['baseline'],runtime_state='closed')
    assert stopped['account_observed_at']==ready['capital']['account_observed_at']
    assert stopped['spendable_cash_cny']is None and not stopped['account_observation_qualified']
    expired=dict(ready['capital'])
    stamp=datetime.now(timezone.utc)-timedelta(seconds=120)
    expired.update(account_observed_at=stamp.isoformat(),account_valid_until=(stamp+timedelta(seconds=60)).isoformat())
    old=project_capital(expired,expired['baseline'])
    assert old['account_observed_at']==stamp.isoformat() and old['spendable_cash_cny']is None
    result=dict(passed=True,App=importlib.metadata.version('guanheng-app'),GETs=3,POST_status=405,
        budget_cny=details['budget_cny'],capital=cap,account_asset_separate=True,
        current_source_qualified=cap['account_observation_qualified'],expected_closed=args.expect_closed,
        source_times_preserved_per_GET=True,runtime_capital=runtime_capital,
        stopped_and_expired_keep_original_time=True,read_pool_closed=app.state.shutdown_complete,QMT_calls=0)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    args.ready.with_name('READER-DONE.json').write_text(json.dumps(dict(passed=True)),encoding='utf8')
    print(json.dumps(dict(passed=True,GETs=3,budget='1000000',QMT_calls=0)))


if __name__=='__main__':
    main()
