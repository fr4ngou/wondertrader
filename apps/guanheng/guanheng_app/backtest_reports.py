"""回测报告族的唯一选择入口，任务、归档和绩效共享相同准入/投影。"""
from .retained_replay import REPORT_SCHEMA as RETAINED_REPORT_SCHEMA

PER_DATE_REPORT_SCHEMA = 'guanheng.retained-per-date-replay-report.v1'
RETAINED_REPORT_SCHEMAS = (RETAINED_REPORT_SCHEMA, PER_DATE_REPORT_SCHEMA)
PER_DATE_INPUT_SCHEMA = 'guanheng.retained-per-date-replay-input.v1'


def _per_date_input(value):
    schema=value.get('schema') if type(value) is dict else None
    if type(schema) is str and schema.startswith('guanheng.retained-per-date-replay-input.'):
        from .strategy_replay_facts import SessionError
        if schema!=PER_DATE_INPUT_SCHEMA:
            raise SessionError('逐日回放输入版本未通过准入')
        return True
    return False


def _normalize_per_date(value):
    """WT拥有纯值准入；C只适配领域异常，不复制日期、因子或数量规则。"""
    from guanheng_wt_runtime.backtest_reports import normalize_session as normalize
    from guanheng_wt_runtime.strategy_replay_facts import SessionError as WTSessionError
    from .strategy_replay_facts import SessionError
    if type(value.get('session')) is not dict or value['session'].get('schema')!='guanheng.retained-replay-input.v1':
        raise SessionError('逐日回放内层输入版本未通过准入')
    try:
        return normalize(value)
    except WTSessionError:
        raise SessionError('逐日回放输入未通过领域准入') from None


def report_schema_for_input(value):
    if _per_date_input(value):
        from guanheng_wt_runtime.backtest_reports import report_schema_for_input as select
        from guanheng_wt_runtime.strategy_replay_facts import SessionError as WTSessionError
        from .strategy_replay_facts import SessionError
        try:
            return select(value)
        except WTSessionError:
            raise SessionError('逐日回放外层输入未通过准入') from None
    if type(value) is dict and value.get('schema') == 'guanheng.retained-replay-input.v1':
        return RETAINED_REPORT_SCHEMA
    from .strategy_session import report_schema_for_input as legacy
    return legacy(value)


def normalize_session(value):
    if _per_date_input(value):
        return _normalize_per_date(value)
    if report_schema_for_input(value) == RETAINED_REPORT_SCHEMA:
        import json
        from guanheng_strategy_core.contracts import canonical_bytes
        from .retained_replay import RetainedReplayInput
        return json.loads(canonical_bytes(RetainedReplayInput.from_dict(value), max_bytes=8388608))
    return value


def session_for_projection(value):
    """配置和绩效只读同一原内层；原外层及source摘要由请求/归档继续绑定。"""
    return _normalize_per_date(value)['session'] if _per_date_input(value) else value


def validate_report_dict(value, *, check=None):
    if type(value) is dict and value.get('schema') in RETAINED_REPORT_SCHEMAS:
        from .retained_report import validate_report
        return validate_report(value, check=check)
    from .strategy_session import validate_report_dict as legacy
    return legacy(value, check=check)


def project_session_record(report, index, *, check=None):
    from .retained_report import ValidatedRetainedReport, project_record
    if type(report) is ValidatedRetainedReport:
        return project_record(report, index, check=check)
    if type(report) is dict and report.get('schema') in RETAINED_REPORT_SCHEMAS:
        return project_record(validate_report_dict(report, check=check), index, check=check)
    from .strategy_session import project_session_record as legacy
    return legacy(report, index, check=check)
