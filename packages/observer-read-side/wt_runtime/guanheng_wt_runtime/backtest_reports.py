"""独立WT唯一1.2.1回放报告边界，复用已有业务validator。"""
import json

from guanheng_strategy_core.contracts import canonical_bytes
from .retained_replay import REPORT_SCHEMA, RetainedReplayInput
from .strategy_replay_facts import SessionError

ORIGINAL_INPUT_SCHEMA = 'guanheng.original-native-replay-input.v1'
ORIGINAL_REPORT_SCHEMA = 'guanheng.original-native-replay-report.v1'


def _original(value, kind):
    """原版WT族按固定schema分流，未知版本拒绝，保留原有retained准入。"""
    schema = value.get('schema') if type(value) is dict else None
    prefix = f'guanheng.original-native-replay-{kind}.'
    if type(schema) is str and schema.startswith(prefix):
        expected = ORIGINAL_INPUT_SCHEMA if kind == 'input' else ORIGINAL_REPORT_SCHEMA
        if schema != expected:
            raise SessionError('原版WT回放协议版本未通过准入')
        return True
    return False


def report_schema_for_input(value):
    if _original(value, 'input'):
        return ORIGINAL_REPORT_SCHEMA
    from .retained_per_date_replay import INPUT_SCHEMA, REPORT_SCHEMA as per_date_schema
    if type(value) is not dict:
        raise SessionError('独立WT回测只接受唯一正式1.2.1回放输入')
    if value.get('schema') == 'guanheng.retained-replay-input.v1':
        return REPORT_SCHEMA
    if value.get('schema') == INPUT_SCHEMA and set(value) == {'schema', 'session', 'source'}:
        return per_date_schema
    raise SessionError('独立WT回测只接受唯一正式1.2.1回放输入')


def normalize_session(value):
    if _original(value, 'input'):
        from .original_native_contracts import normalize_input
        return normalize_input(value)
    schema = report_schema_for_input(value)
    if schema == REPORT_SCHEMA:
        return json.loads(canonical_bytes(RetainedReplayInput.from_dict(value), max_bytes=8388608))
    from .retained_per_date_replay import INPUT_SCHEMA, normalize_source_binding
    result = dict(schema=INPUT_SCHEMA,
        session=json.loads(canonical_bytes(RetainedReplayInput.from_dict(value['session']), max_bytes=8388608)),
        source=normalize_source_binding(value['source']))
    return json.loads(canonical_bytes(result, max_bytes=16777216))


def validate_report_dict(value, *, check=None):
    if _original(value, 'report'):
        from .original_native_contracts import validate_report
        return validate_report(value, check=check)
    from .retained_report import validate_report, validate_per_date_report
    from .retained_per_date_replay import REPORT_SCHEMA as per_date_schema
    validator = (validate_per_date_report if type(value) is dict and value.get('schema') == per_date_schema
                 else validate_report)
    return validator(value, check=check)


def project_session_record(report, index, *, check=None):
    if (type(report).__module__ == 'guanheng_wt_runtime.original_native_contracts'
            and type(report).__name__ == 'ValidatedOriginalNativeReport') or _original(report, 'report'):
        from .original_native_contracts import project_record
        return project_record(report, index, check=check)
    from .retained_report import ValidatedRetainedReport, project_record
    if type(report) is not ValidatedRetainedReport:
        report = validate_report_dict(report, check=check)
    return project_record(report, index, check=check)


def project_business_diagnostics(report, *, check=None):
    """观衡和操作员共用WT只读诊断；历史原报告缺字段时保持未知。"""
    if (type(report).__module__ == 'guanheng_wt_runtime.original_native_contracts'
            and type(report).__name__ == 'ValidatedOriginalNativeReport') or _original(report, 'report'):
        if type(report) is dict:
            validate_report_dict(report, check=check)
        return None
    from .retained_report import ValidatedRetainedReport, project_diagnostics
    if type(report) is not ValidatedRetainedReport:
        report = validate_report_dict(report, check=check)
    return project_diagnostics(report, check=check)


def project_input_business_diagnostics(report, session, *, check=None):
    """沿已准入原报告和原冻结输入解释旧报告缺口，不重算或重写原回测。"""
    if (type(report).__module__ == 'guanheng_wt_runtime.original_native_contracts'
            and type(report).__name__ == 'ValidatedOriginalNativeReport') or _original(report, 'report'):
        if type(report) is dict:
            validate_report_dict(report, check=check)
        return None
    from .retained_report import ValidatedRetainedReport, project_input_diagnostics
    if type(report) is not ValidatedRetainedReport:
        report = validate_report_dict(report, check=check)
    return project_input_diagnostics(report, session, check=check)
