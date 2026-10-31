# -*- coding: utf-8 -*-
"""BP1显式长窗能力准入；旧操作继续使用原唯一校验。"""
from . import read_capabilities as read
from .protocol import canonical, decode
from .trade_clock import CLOCK_SCHEMA

BULK_OPERATION = 'market.history_1m.bulk'
PROFILE_SCHEMA = 'qmt.history-bulk-profile.v1'
POLICY_ID = 'qmt.history-bulk-read.v1'
POLICY_VERSION = '1.0'


def page_reply_size(max_page_bytes, max_pages):
    """最长已准入身份的完整REPLY上界，包含精确base64膨胀。"""
    read._integer(max_page_bytes, 1, 2097152)
    read._integer(max_pages, 1, 10000)
    uuid = 'ffffffff-ffff-ffff-ffff-ffffffffffff'
    identity = dict(range_id=uuid, session_id='f'*32, snapshot_id=uuid, symbol='000001.SZ',
                    start_time='20211101000000', end_time='20991231235900')
    page = dict(schema='qmt.history-bulk-delivery.v1', request_id=uuid, identity=identity,
                page_index=max_pages-1, page_sha256='f'*64, body='')
    reply = dict(kind='REPLY', call_seq=2**64-1, request_sha256='f'*64, ok=True, payload=page, error=None)
    return len(canonical(reply)) + 4*((max_page_bytes+2)//3)


def validate_bulk_read_profile(profile, *, max_result_bytes=None):
    read._fields(profile, ('read_profile_version', 'read_operations', 'execution_timeout_ms',
                           'control_profile', 'operation_profiles', 'bulk_profile'))
    if type(profile['read_profile_version']) is not str or profile['read_profile_version'] != read.BULK_READ_PROFILE_VERSION:
        read._reject()
    operations = profile['read_operations']
    if (type(operations) is not list or not 2 <= len(operations) <= 4
            or any(type(op) is not str or not (op == BULK_OPERATION or (read.known_operation(op) and op != read.PREPARATION))
                   for op in operations)
            or operations != sorted(set(operations)) or BULK_OPERATION not in operations):
        read._reject()
    ordinary = [op for op in operations if op != BULK_OPERATION]
    read._integer(profile['execution_timeout_ms'], 100, 30000)
    read._control(profile['control_profile'], '3.0')
    read._operation_profiles(profile, ordinary, max_result_bytes)
    descriptor = profile['bulk_profile']
    read._fields(descriptor, ('schema_version', 'policy_id', 'policy_version', 'clock_schema',
                             'queue_timeout_ms', 'total_timeout_ms', 'limits'))
    for key, value in (('schema_version', PROFILE_SCHEMA), ('policy_id', POLICY_ID),
                       ('policy_version', POLICY_VERSION), ('clock_schema', CLOCK_SCHEMA)):
        if type(descriptor[key]) is not str or descriptor[key] != value:
            read._reject()
    read._integer(descriptor['queue_timeout_ms'], 100, 300000)
    read._integer(descriptor['total_timeout_ms'], 100, 360000)
    if descriptor['queue_timeout_ms'] > descriptor['total_timeout_ms']:
        read._reject()
    limits = descriptor['limits']
    read._fields(limits, ('max_calendar_days', 'max_rows', 'max_row_bytes', 'max_snapshot_bytes',
                         'max_page_rows', 'max_page_bytes', 'max_total_bytes', 'max_pages', 'max_ranges'))
    bounds = {'max_calendar_days':36600, 'max_rows':1000000, 'max_page_rows':1000000,
              'max_row_bytes':2097152, 'max_page_bytes':2097152,
              'max_snapshot_bytes':1073741824, 'max_total_bytes':1073741824,
              'max_pages':10000, 'max_ranges':10000}
    for key, maximum in bounds.items():
        read._integer(limits[key], 1, maximum)
    if (not limits['max_row_bytes'] <= limits['max_page_bytes'] <= limits['max_total_bytes']
            or limits['max_snapshot_bytes'] > limits['max_total_bytes']
            or limits['max_page_rows'] > limits['max_rows']
            or (limits['max_rows']+limits['max_page_rows']-1)//limits['max_page_rows'] > limits['max_pages']):
        read._reject()
    raw = canonical(profile)
    if len(raw) > 4096:
        read._reject()
    return decode(raw)


def build_bulk_read_profile(operations, execution_ms, control, operation_profiles, bulk_profile, *, max_result_bytes):
    return validate_bulk_read_profile({'read_profile_version':read.BULK_READ_PROFILE_VERSION,
        'read_operations':operations, 'execution_timeout_ms':execution_ms, 'control_profile':control,
        'operation_profiles':operation_profiles, 'bulk_profile':bulk_profile}, max_result_bytes=max_result_bytes)


def profile_descriptor(profile, *, max_result_bytes=None):
    return validate_bulk_read_profile(profile, max_result_bytes=max_result_bytes)['bulk_profile']
