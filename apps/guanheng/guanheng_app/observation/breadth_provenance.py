"""历史来源由数据生产者持有，同方法更新及派生定义重建保留该事实。"""
import copy
from datetime import date
import re

from .contracts import ObservationError


def retain_history_provenance(definition, previous, method):
    """组合当前方法说明及生产者冻结的历史来源，保留原历史区间。

    历史描述存在时返回独立副本；缺省沿用当前定义。方法升级清除旧方法的
    资格，新历史由生产者重新确认。结构错误抛ObservationError，由原更新
    owner决定写入结果；本函数仅作字典纯计算，输入保持原状。
    """
    if previous is None or previous.get('history_extension') is None:
        return definition
    history=previous['history_extension']
    fields={'schema','recipe_sha256','definition_version','interval','source','source_url','point_in_time','limitations'}
    try:
        if type(history) is not dict or set(history)!=fields:
            raise ValueError('history fields')
        if (history['schema']!='observation-history-extension/1'
                or type(history['recipe_sha256']) is not str
                or re.fullmatch('[a-f0-9]{64}',history['recipe_sha256']) is None
                or history['definition_version']!=previous['definition_version']
                or type(history['point_in_time']) is not bool):
            raise ValueError('history identity')
        interval=history['interval']
        if (type(interval) is not list or len(interval)!=2
                or any(type(day) is not str or date.fromisoformat(day).isoformat()!=day for day in interval)
                or interval[0]>interval[1]):
            raise ValueError('history interval')
        if any(type(history[key]) is not str or not history[key].strip() for key in ('source','source_url')):
            raise ValueError('history source')
        if type(history['limitations']) is not list or any(type(line) is not str or not line.strip() for line in history['limitations']):
            raise ValueError('history notes')
    except (KeyError,TypeError,ValueError,OverflowError):
        raise ObservationError('invalid_history_provenance','历史来源描述无效；保留上一冻结版本并核对生产者资料',422) from None
    if definition['definition_version']!=previous['definition_version']:
        result=copy.deepcopy(definition)
        result.pop('history_extension',None)
        result['source']=method['source']
        result['limitations']=copy.deepcopy(method['limitations'])
        return result
    result=copy.deepcopy(definition)
    result['history_extension']=copy.deepcopy(history)
    result['limitations']=list(dict.fromkeys([*method['limitations'],*history['limitations']]))
    result['source']=method['source']+'；历史补齐：'+history['source']
    return result
