# -*- coding: utf-8 -*-
"""已确认读责任的纯身份合同；终端内只处理普通值和原共享时钟。"""
import re
from uuid import UUID, uuid5
from .protocol import canonical, decode
from .security_reference import OPERATIONS as REFERENCE_OPERATIONS, CONFIRMED_ERRORS as REFERENCE_ERRORS

SCHEMA = 'qmt.read-retention.v1'
TICKET = 'qmt.read-ticket.v1'
ENVELOPE = 'qmt.bound-retained-read.v1'
LOOKUP = 'qmt.read-lookup.v1'
CONSUMED = 'qmt.read-consumed.v1'


class ReadTicketEnded(ValueError):
    """原票据已结束，Host 明确拒绝本次新准入；不描述原 ID 的既往执行。"""


def result_confirmed(result):
    """成功或固定调用前拒绝可交接；未登记失败保留未知责任和原 ID。

    Host 回收和外部消费者使用同一分类，避免外部把未知当作下一轮读取。
    本函数只适用于独立读取/HPR，金融写命令不进入该合同。
    """
    return (result.get('operation_id') in REFERENCE_OPERATIONS
            and result.get('error_code') in REFERENCE_ERRORS) or result.get('ok') is True or result.get('error_code') in (
        'preparation_not_executed', 'queue_timeout', 'source_binding_changed',
        'queue_full', 'invalid_arguments', 'capability_unavailable')


def retention(value):
    """唯一可变保留预算；不授来源操作或交易能力。"""
    if (type(value) is not dict or set(value) != {'schema', 'max_lifetime_ms'}
            or value['schema'] != SCHEMA or type(value['max_lifetime_ms']) is not int
            or not 100 <= value['max_lifetime_ms'] <= 300000):
        raise ValueError('invalid explicit read retention capability')
    return decode(canonical(value))


def ticket(value):
    if (type(value) is not dict or set(value) != {'schema', 'epoch', 'expires_ms'}
            or value['schema'] != TICKET or type(value['epoch']) is not str
            or re.fullmatch(r'[0-9a-f]{32}', value['epoch']) is None
            or type(value['expires_ms']) is not int or not 0 < value['expires_ms'] < 2**53):
        raise ValueError('invalid read ticket')
    return decode(canonical(value))


def content_id(request, value):
    """UUIDv5 绑定所有八字段语义和原期限；相关 ID 为每次新观察的 nonce。"""
    value = ticket(value)
    body = dict(request)
    body.pop('request_id', None)
    return str(uuid5(UUID(value['epoch']), canonical({'ticket': value, 'request': body}).decode('utf8')))


def validate_identity(request, value):
    value = ticket(value)
    if request.get('request_id') != content_id(request, value):
        raise ValueError('read request is not bound to its original ticket and content')
    if (request.get('operation_id') == 'market.history_prepare'
            and request.get('arguments', {}).get('deadline_ms') != value['expires_ms']):
        raise ValueError('preparation ticket differs from original deadline')
    return value


def now_ms(clock):
    # 与 HPR 和交易时钟共用已验证的 GetTickCount64 标量准入；不引入新时钟。
    from .history_preparation import now_ms as original_now
    return original_now(clock)


def ended(value, epoch, clock):
    value = ticket(value)
    return value['epoch'] != epoch or now_ms(clock) >= value['expires_ms']


def require_live(request, value, capability, epoch, clock):
    value = validate_identity(request, value)
    remaining = value['expires_ms'] - now_ms(clock)
    if value['epoch'] != epoch or remaining <= 0:
        raise ReadTicketEnded('read ticket admission window ended')
    if remaining > retention(capability)['max_lifetime_ms']:
        raise ValueError('read ticket exceeds explicit admission lifetime')
    return value
