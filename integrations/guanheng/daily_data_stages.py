"""不可变输出阶段的持久构建事务；未完成输出保留，后继采用独立的新尝试根。"""
from pathlib import Path
import uuid

from ..guanheng_market_client import strict_json
from .market_generation import read_fixed


def prepare_directory(root, name, marker, build, restore):
    """调用者持任务写锁且已固定INPUTS/REQUEST；成功描述符保存后才算提交。

    builder沿原准备器独占创建output。中断前已完成marker则完整复核并采用；
    缺失或不完整marker的原尝试保留，新尝试不触碰原HPR槽/已提交数据。
    同阶段最多16个尝试，防止持续故障无限积累目录；超限保留当前版本。
    """
    from .daily_data_update import _save
    if name not in ('facts', 'gap-plan', 'snapshot') or type(marker) is not str or Path(marker).name != marker:
        raise ValueError('daily immutable stage name invalid')
    root = Path(root).absolute()
    path = root / ('PHASE-' + name + '.json')
    state = strict_json(read_fixed(path, maximum=65536)) if path.exists() else dict(
        schema='guanheng.daily-immutable-stage.v1',  # 固定任务内的输出尝试事务；不拥有来源请求身份。
        name=name,  # facts/gap-plan/snapshot，映射不同不可变准备器。
        attempts=[],  # 最多16个本任务创建的输出目录，未完成目录保留供核查。
        result=None)  # 已提交结果描述符；None表示成功输出尚未登记。
    if (type(state) is not dict or set(state) != {'schema', 'name', 'attempts', 'result'}
            or state.get('schema') != 'guanheng.daily-immutable-stage.v1' or state.get('name') != name
            or type(state['attempts']) is not list or len(state['attempts']) > 16
            or len(set(state['attempts'])) != len(state['attempts'])
            or (state['result'] is not None and not state['attempts'])):
        raise ValueError('daily immutable stage identity differs')

    def output(attempt):
        if type(attempt) is not str or uuid.UUID(attempt).hex != attempt:
            raise ValueError('daily immutable stage attempt invalid')
        return root / (name + '-' + attempt)

    if state['result'] is not None:
        restored = restore(output(state['attempts'][-1]))
        if restored != state['result']:
            raise ValueError('daily immutable committed output differs')
        return restored
    if state['attempts']:
        previous = output(state['attempts'][-1])
        if (previous / marker).exists():
            try:
                result = restore(previous)
            except (ValueError, OSError, KeyError, TypeError) as error:
                if isinstance(error, (InterruptedError, TimeoutError)):
                    raise
                # 尚未提交的半份marker保留；已提交结果损坏在上面的分支明确失败。
            else:
                state['result'] = result
                _save(path, state)
                return result
    if len(state['attempts']) >= 16:
        raise ValueError('daily immutable stage attempt capacity')
    attempt = uuid.uuid4().hex
    state['attempts'].append(attempt)
    _save(path, state)
    result = build(output(attempt))
    if restore(output(attempt)) != result:
        raise ValueError('daily immutable built output differs')
    state['result'] = result
    _save(path, state)
    return result
