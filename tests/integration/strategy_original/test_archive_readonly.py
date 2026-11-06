"""非WT原组合公开能力撤回；WT及内部信号参考继续由各自owner拥有。"""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from time import monotonic

import pytest
from fastapi.testclient import TestClient
from guanheng_app.backtest_archive import BacktestArchive,ArchiveError
from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app.strategy_catalog import strategy_catalog,ORIGINAL_WT_ID

RETIRED_ID='resonance-original-351f9d5-stable'


def retired(tmp_path):
    root=tmp_path/'archive';root.mkdir();run=root/('d'*32);run.mkdir()
    raw=json.dumps(dict(schema='orr-completed-archive-v1',run_id=run.name,report_family='resonance-original',
        report_sha256='a'*64,record_count=3,private_marker='retired-equity-must-not-project')).encode()
    (run/'completed-archive.json').write_bytes(raw)
    return root,run.name,sha256(raw).hexdigest()


def test_catalog_keeps_dynamic_wt_identity_and_only_wt_original_registration():
    result=strategy_catalog([dict(strategy_id='resonance-regime-v1',strategy_version=None),
        dict(strategy_id=RETIRED_ID,strategy_version='0.1.0a1'),dict(strategy_id='other-WT',strategy_version='7.1')])
    values=result['strategies']
    assert [r['strategy_id']for r in values]==['resonance-regime-v1','other-WT',ORIGINAL_WT_ID]
    assert values[0]['strategy_version'] is None and values[1]['strategy_version']=='7.1'
    assert len(strategy_catalog()['strategies'])==1


def test_retired_orr_is_absent_from_both_indices_and_direct_reads_are_explicitly_gone(tmp_path):
    root,run,digest=retired(tmp_path);owner=BacktestArchive(root)
    before=(root/run/'completed-archive.json').read_bytes()
    for summaries in (False,True):
        value=owner.list(monotonic()+5,summaries=summaries)
        assert value['runs']==[] and value['invalid_receipts']==0 and value['unarchived_runs']==0
    for operation in (lambda:owner.read(run,digest,monotonic()+5,configuration=True),
                      lambda:owner.read(run,digest,monotonic()+5,performance=True),
                      lambda:owner.visual(run,digest,monotonic()+5,ledger=True)):
        with pytest.raises(ArchiveError) as failure:operation()
        assert failure.value.code==410 and '已移出' in str(failure.value)
    assert (root/run/'completed-archive.json').read_bytes()==before


def test_http_retired_financial_projections_and_orr_signals_are_not_public(tmp_path):
    root,run,digest=retired(tmp_path)
    with TestClient(create_app(ConsoleSettings(backtest_archive_root=str(root)))) as client:
        for suffix in ('','/performance','/visuals','/ledger','/records','/records/0'):
            response=client.get(f'/v1/ui/backtest/archive/{run}{suffix}',params={'receipt_sha256':digest})
            assert response.status_code==410,response.text
            assert 'retired-equity-must-not-project' not in response.text and 'orr-' not in response.text
        assert client.get(f'/v1/ui/backtest/archive/{run}/signals',params={'receipt_sha256':digest}).status_code==404
        assert client.post(f'/v1/ui/backtest/archive/{run}').status_code==405


def test_public_importer_removed_but_wt_internal_reference_contract_remains():
    assert importlib.util.find_spec('guanheng_app.original_report_import') is None
    assert importlib.util.find_spec('guanheng_app.original_reports') is None
    from guanheng_wt_runtime.original_native_contracts import INPUT_FIELDS,ALGORITHM_ID
    assert ALGORITHM_ID==RETIRED_ID and 'reference_report' in INPUT_FIELDS


def test_unknown_native_receipt_is_still_invalid_not_silently_retired(tmp_path):
    root=tmp_path/'archive';root.mkdir();run=root/('a'*32);run.mkdir()
    (run/'completed-archive.json').write_text('{"schema":"unknown-native.v99"}',encoding='utf8')
    value=BacktestArchive(root).list(monotonic()+5)
    assert value['invalid_receipts']==1 and value['runs']==[]


def test_original_native_unknown_versions_never_fall_through_legacy():
    from guanheng_app import backtest_reports as dispatch
    from guanheng_app.strategy_replay_facts import SessionError
    with pytest.raises(SessionError):dispatch.report_schema_for_input(dict(schema='guanheng.original-native-replay-input.v2'))
    with pytest.raises(SessionError):dispatch.validate_report_dict(dict(schema='guanheng.original-native-replay-report.v2'))
