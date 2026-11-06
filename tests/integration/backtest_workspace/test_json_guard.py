"""结构标记扫描保持原深度/转义/截止；跨64KiB窗口不能改变字符串语义。"""
import json
from time import monotonic

import pytest

from guanheng_app import strategy_host as host


@pytest.mark.parametrize('slashes',range(1,9))
def test_quoted_markers_and_escape_parity_cross_window(slashes):
    prefix=b'"'+b'a'*(65534-slashes//2)+b'\\'*slashes
    raw=prefix+b'"'+(b'['*30+b'"' if slashes%2 else b'')
    assert host._json(raw,1024*1024,monotonic()+5)==json.loads(raw)


def test_depth_rejection_precedes_standard_decoder(monkeypatch):
    monkeypatch.setattr(host.json,'loads',lambda *_args,**_kwargs:pytest.fail('deep input reached parser'))
    with pytest.raises(host.HostError,match='嵌套'):
        host._json(b'['*25+b'0'+b']'*25,1024,monotonic()+5)


def test_plain_large_string_still_checks_each_original_byte_window(monkeypatch):
    checks=[]
    class Stop(Exception):pass
    stop=Stop()
    def check(_deadline):
        checks.append(True)
        if len(checks)==3:raise stop
    monkeypatch.setattr(host,'_check',check)
    monkeypatch.setattr(host.json,'loads',lambda *_args,**_kwargs:pytest.fail('cancelled input reached parser'))
    with pytest.raises(Stop) as caught:host._json(b'"'+b'a'*200000+b'"',300000,monotonic()+5)
    assert caught.value is stop and len(checks)==3


@pytest.mark.parametrize('raw',[b'{"a":1,"a":2}',b'NaN',b'1e9999',b'\xff',b'"unterminated',b'[1,]'])
def test_original_invalid_json_categories_remain_rejected(raw):
    with pytest.raises(host.HostError):host._json(raw,1024,monotonic()+5)


@pytest.mark.parametrize('offset', [65533, 65534, 65535, 65536, 131070, 131071])
@pytest.mark.parametrize('text', ['\\\\\\"[{}]中文', '\\\\"', '"[]{}', '\\\\\\\\'])
def test_complete_string_skip_preserves_long_utf8_and_escape_boundaries(offset, text):
    value = ['x' * offset + text, {'value': [1, 2, 3]}]
    raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
    assert host._json(raw, 300000, monotonic()+5) == value


def test_node_budget_counts_scalar_children_and_container_roots():
    maximum = 2097152
    raw = b'[' + b'0,' * (maximum-2) + b'0]'
    assert len(host._json(raw, 5*1024*1024, monotonic()+15)) == maximum-1
    with pytest.raises(host.HostError, match='节点'):
        host._json(raw[:-1] + b',0]', 5*1024*1024, monotonic()+15)


def test_scalar_walk_observes_original_cancellation_object(monkeypatch):
    original = host.json.loads
    decoded = False
    stop = RuntimeError('original cancellation')
    def loads(*args, **kwargs):
        nonlocal decoded
        value = original(*args, **kwargs)
        decoded = True
        return value
    def check(_deadline):
        if decoded:
            raise stop
    monkeypatch.setattr(host.json, 'loads', loads)
    monkeypatch.setattr(host, '_check', check)
    with pytest.raises(RuntimeError) as caught:
        host._json(b'[' + b'0,'*10000 + b'0]', 30000, monotonic()+5)
    assert caught.value is stop


def test_long_escaped_quote_string_keeps_linear_window_progress():
    value = '"'*80000+'\\'
    raw = json.dumps([value, {'value': 1}]).encode('ascii')
    assert host._json(raw, 300000, monotonic()+5) == [value, {'value': 1}]


def test_deep_structure_after_cross_window_quoted_markers_stays_preparse_guarded(monkeypatch):
    prefix = json.dumps('['*65530+'"'*30).encode('ascii')
    raw = b'['+prefix+b','+b'['*24+b'0'+b']'*24+b']'
    monkeypatch.setattr(host.json, 'loads', lambda *_args, **_kwargs: pytest.fail('deep input reached decoder'))
    with pytest.raises(host.HostError, match='嵌套'):
        host._json(raw, 300000, monotonic()+5)


def test_node_limit_rejection_precedes_object_allocation(monkeypatch):
    maximum = 2097152
    # 合法数组的根和2097152个标量超过原节点上限，先拒绝再进入C分配。
    raw = b'[' + b'0,' * (maximum-1) + b'0]'
    monkeypatch.setattr(host.json, 'loads', lambda *_args, **_kwargs: pytest.fail('over-budget input reached decoder'))
    with pytest.raises(host.HostError, match='节点'):
        host._json(raw, 5*1024*1024, monotonic()+15)


@pytest.mark.parametrize('first', [b'[]', b'{}', b'[\t\r\n]', b'{\t\r\n}', b'"[,{}]"'])
def test_exact_node_limit_across_window_empty_containers_and_string_markers(first):
    maximum = 2097152
    # 第一个子值起于65535：空容器闭合或字符串主体跨原64KiB窗口。
    # 节点严格为根1 + 首值1 + 剩余2097150个标量；窗口暂记不能误拒。
    raw = b'[' + b' '*65534 + first + b',' + b'0,'*(maximum-3) + b'0]'
    value = host._json(raw, 5*1024*1024, monotonic()+15)
    assert len(value) == maximum-1
    assert value[0] == json.loads(first)


def test_exact_node_limit_preserves_mixed_nonempty_container_children():
    maximum = 2097152
    # 尾部5个子值包含2个额外嵌套标量，合计节点为1+n+5+2。
    raw = b'[' + b'0,'*(maximum-8) + b'[],{},[0],{"k":0},"[,]{}"]'
    value = host._json(raw, 5*1024*1024, monotonic()+15)
    assert value[-5:] == [[], {}, [0], {'k': 0}, '[,]{}']
    with pytest.raises(host.HostError, match='节点'):
        host._json(raw[:-1] + b',0]', 5*1024*1024, monotonic()+15)


@pytest.mark.parametrize('raw', [b'{"unused":[1e9999]}', b'[-1e9999]', b'{"a":{"\\u0062":1,"b":2}}'])
def test_nonfinite_and_escaped_duplicate_values_still_reject(raw):
    with pytest.raises(host.HostError):
        host._json(raw, 1024, monotonic()+5)


def test_c_decoder_float_semantics_preserve_finite_extremes_and_underflow():
    raw = b'[1.7976931348623157e308,-0.0,5e-324,1e-9999]'
    assert host._json(raw, 1024, monotonic()+5) == json.loads(raw)
