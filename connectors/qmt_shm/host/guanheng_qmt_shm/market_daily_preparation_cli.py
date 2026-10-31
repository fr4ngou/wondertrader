"""外部有界工作流入口；连接由WT持有，不启动QMT或Host。"""
import argparse
import json
from pathlib import Path
import time

from .market_daily_preparation import MarketDailyPreparation
from .read_retention_client import RetainedReadPending, RetainedReadFailure


def _reason_code(error):
    """仅发布固定协议原因码；未知异常正文可能含来源信息，统一收敛。"""
    known = {
        'market_daily_workflow_deadline', 'market_daily_source_binding_changed',
        'read_source_waiting', 'read_retention_capacity_unavailable',
        'read_retention_held_responsibility', 'read_retention_awaiting_ticket_end',
        'read_source_binding_changed', 'read_admission_rejected',
        'read_retention_capacity_rejected', 'read_original_request_unresolved',
        'read_original_request_pending', 'read_consumption_unconfirmed',
        'read_original_terminal_unknown', 'read_original_terminal_failure',
        'read_transport_unresolved'}
    value = str(error)
    return value if value in known else 'read_pending_unspecified' if isinstance(error, RetainedReadPending) else 'read_failure_unspecified'


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--configuration', required=True, type=Path)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--seconds', required=True, type=float)
    parser.add_argument('--max-preparations', type=int)
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 86400:
        raise ValueError('market_daily_finite_workflow_budget')
    configuration = json.loads(args.configuration.read_bytes())
    if set(configuration) != {'schema','hpr','batch','concurrency'} or configuration['schema'] != 'guanheng.market-daily-connections.v1':
        raise ValueError('market_daily_connections')
    # 原外部HTTP运输属于WT侧；QMT内只执行正式SHM正文。
    from integrations.guanheng.source_history_transport import BoundHistorySource
    provider = MarketDailyPreparation(lambda:BoundHistorySource(configuration['hpr'], reuse_connections=True),
        BoundHistorySource(configuration['batch'], reuse_connections=True),concurrency=configuration['concurrency'])
    request = json.loads(args.request.read_bytes())
    try:
        result = provider.run(request,args.directory,deadline=time.monotonic()+args.seconds,
            max_preparations=args.max_preparations, connection_identity=configuration)
    except RetainedReadPending as error:
        print(json.dumps(dict(state='pending',reason_code=_reason_code(error),original_identity_preserved=True)))
        return 2
    except RetainedReadFailure as error:
        print(json.dumps(dict(state='source_unavailable',reason_code=_reason_code(error),original_identity_preserved=True)))
        return 3
    print(json.dumps(dict(state=result['state'],securities=result.get('securities'),
        confirmed=len(result['preparations']),actual_coverage_qualified=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
