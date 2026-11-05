"""观衡报告边界：只读事实准入由WT公开读取接口唯一拥有。"""
from guanheng_wt_runtime.backtest_reports import validate_report_dict as _validate
from guanheng_wt_runtime.backtest_reports import project_session_record as _project
from guanheng_wt_runtime.backtest_reports import project_business_diagnostics as _diagnostics
from guanheng_wt_runtime.backtest_reports import project_input_business_diagnostics as _input_diagnostics
from guanheng_wt_runtime.retained_report import ValidatedRetainedReport
from guanheng_wt_runtime.strategy_replay_facts import SessionError as _WTSessionError

from .strategy_replay_facts import SessionError


def _read(operation, *args, check):
    control_error = None

    def guarded():
        nonlocal control_error
        try:
            check()
        except BaseException as error:
            control_error = error
            raise

    try:
        return operation(*args, check=None if check is None else guarded)
    except _WTSessionError as error:
        if error is control_error:
            raise
        raise SessionError('唯一策略报告未通过领域准入') from None


def validate_report(value, *, check=None):
    """固定/逐日来源共用WT准入；回调异常按原身份传播，领域错误转App类型。"""
    return _read(_validate, value, check=check)


def project_record(report, index, *, check=None):
    """返回独立值；不启动Porter、运行进程或任何原生会话。"""
    return _read(_project, report, index, check=check)


def project_business_diagnostics(report, *, check=None):
    """沿WT唯一只读结果读取整体诊断；旧报告的缺记录保持None。"""
    return _read(_diagnostics, report, check=check)


def project_input_business_diagnostics(report, session, *, check=None):
    return _read(_input_diagnostics, report, session, check=check)
