# -*- coding: utf-8 -*-
"""来源运行方式属于配对生命周期；金融能力及wire版本保持原所有者。"""
SCHEMA = 'qmt.source-runtime.v1'
TICK_PERIOD = '100nMilliSecond'


def source_runtime(value):
    if value is None:
        return None
    if (type(value) is not dict or set(value) != {'schema_version', 'mode'}
            or value['schema_version'] != SCHEMA or value['mode'] not in ('thread', 'strategy_tick')):
        raise ValueError('explicit versioned source runtime required')
    return dict(schema_version=SCHEMA, mode=value['mode'])
