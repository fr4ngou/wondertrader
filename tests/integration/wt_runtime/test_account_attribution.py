"""原C ABI真实ctypes回调：完整复制、时限及失败保持关闭，不连接账户。"""
import ctypes as C
import hashlib
import json

import pytest

from guanheng_wt_runtime.account_attribution import AttributionBridge, NativeEvent, NativeReply


def invoke(bridge, body, *, kind=4, role=2, epoch=0, remaining=0, raw=None):
    data = raw if raw is not None else json.dumps(body).encode()
    buffer = C.create_string_buffer(data)
    event = NativeEvent(C.sizeof(NativeEvent), 1, kind, role, epoch, remaining,
                        len(data), 0, C.cast(buffer, C.c_void_p))
    reply = NativeReply(C.sizeof(NativeReply), 1, -1, 0, 0)
    result = bridge._callback(C.byref(event), C.byref(reply), None)
    C.memset(buffer, 0, len(data))  # Native结束即失效；handler取得值应独立保存。
    return result, reply


def test_real_callback_copies_body_and_keeps_original_deadline():
    seen = []
    def handler(event):
        seen.append(event)
        return 100
    bridge = AttributionBridge(handler, callback_seconds=5, clock=lambda: 10)
    body = {'requested_quantity': 200, 'side': 'buy', 'limit_price_cny': '2.03'}
    result, reply = invoke(bridge, body, remaining=350)
    assert result == 0 and reply.decision == 0 and reply.authorized_quantity == 100
    assert seen[0].body == body and seen[0].deadline == 10.35
    assert seen[0].sha256 == hashlib.sha256(seen[0].raw).hexdigest()
    assert json.loads(seen[0].raw) == body


def test_zero_means_wait_and_does_not_create_group():
    calls = []
    def handler(event):
        calls.append(event.kind)
        return 0
    result, reply = invoke(AttributionBridge(handler, callback_seconds=1),
                           {'requested_quantity': 100, 'side': 'buy'})
    assert result == 0 and reply.decision == 1 and reply.authorized_quantity == 0
    assert calls == [4]


@pytest.mark.parametrize('value', [True, None, 101, 300, -100, 100.0])
def test_invalid_authorization_fails_closed(value):
    result, reply = invoke(AttributionBridge(lambda event: value, callback_seconds=1),
                           {'requested_quantity': 200, 'side': 'buy'})
    assert result == -1 and reply.decision == -1 and reply.authorized_quantity == 0


def test_sell_integer_odd_lot_remains_legal():
    result, reply = invoke(AttributionBridge(lambda event: 17, callback_seconds=1),
                           {'requested_quantity': 19, 'side': 'sell'})
    assert result == 0 and reply.authorized_quantity == 17


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e309}', b'[]'])
def test_invalid_json_never_enters_fact_owner(raw):
    seen = []
    bridge = AttributionBridge(lambda event: seen.append(event), callback_seconds=1)
    result, reply = invoke(bridge, {}, kind=8, raw=raw, remaining=1000)
    assert result == -1 and reply.decision == -1 and seen == []


def test_post_persistence_timeout_is_failure_without_rollback_or_resubmit():
    now, persisted = [10.0], []
    def handler(event):
        persisted.append(event.sha256)
        now[0] = 10.501
    bridge = AttributionBridge(handler, callback_seconds=2, clock=lambda: now[0])
    result, reply = invoke(bridge, {'command_id': 'original'}, kind=7, role=3, remaining=500)
    assert result == -1 and reply.decision == -1
    assert len(persisted) == 1 and str(bridge.failure) == 'attribution_deadline'


def test_notify_exception_stays_in_python_and_reply_closed():
    def handler(event):
        raise RuntimeError('owner_lost')
    bridge = AttributionBridge(handler, callback_seconds=1)
    result, reply = invoke(bridge, {}, kind=1, role=1, epoch=17)
    assert result == -1 and reply.decision == -1 and str(bridge.failure) == 'owner_lost'


def test_notify_must_explicitly_return_none():
    result, reply = invoke(AttributionBridge(lambda event: 0, callback_seconds=1), {}, kind=10)
    assert result == -1 and reply.decision == -1


@pytest.mark.parametrize('kind', [7, 8, 9, 12])
def test_original_deadline_phase_cannot_convert_zero_to_new_budget(kind):
    seen = []
    bridge = AttributionBridge(lambda event: seen.append(event), callback_seconds=5)
    result, reply = invoke(bridge, {}, kind=kind, role=3 if kind == 7 else 2, remaining=0)
    assert result == -1 and reply.decision == -1 and seen == []
    assert str(bridge.failure) == 'attribution_original_deadline'
