# -*- coding: utf-8 -*-
"""BP1纯配置入口，完整页封套与原运输额度联合准入。"""
from .protocol import canonical, decode
from .read_configuration import _REQUIRED, _admit_configuration, ReadConfiguration
from .bulk_capabilities import build_bulk_read_profile, page_reply_size


def _build(value, control):
    return build_bulk_read_profile(value['allowed_operations'], value['execution_timeout_ms'], control,
        value['operation_profiles'], value['bulk_profile'], max_result_bytes=value['max_result_bytes'])


def _require(profile, control):
    descriptor = profile['bulk_profile']
    if descriptor['total_timeout_ms']/1000.0 + control.io_seconds > control.max_call_seconds:
        raise ValueError('bulk original total and IO exceed control lifetime')
    control.require_directions(2)
    maximum = page_reply_size(descriptor['limits']['max_page_bytes'], descriptor['limits']['max_pages'])
    if maximum > control.max_reply_bytes:
        raise ValueError('bulk complete base64 reply exceeds control budget')


def validate_bulk_configuration(trusted_bootstrap):
    fields = _REQUIRED | frozenset(('read_profile_version', 'operation_profiles', 'bulk_profile'))
    if type(trusted_bootstrap) is not dict or set(trusted_bootstrap) != fields:
        raise ValueError('bulk bootstrap fields differ')
    secret = trusted_bootstrap['secret']
    if type(secret) is not bytes or len(secret) < 32:
        raise ValueError('bulk trusted secret is missing')
    value = decode(canonical({key:item for key,item in trusted_bootstrap.items() if key != 'secret'}))
    from .read_capabilities import BULK_READ_PROFILE_VERSION
    if value['read_profile_version'] != BULK_READ_PROFILE_VERSION:
        raise ValueError('explicit bulk version required')
    if type(value['transport']) is not dict or value['transport'].get('kind') != 'builtin-shm':
        raise ValueError('bulk requires builtin SHM')
    route, budget, control, profile = _admit_configuration(value, _build, _require)
    return ReadConfiguration(value, route, budget, control, profile, secret)
