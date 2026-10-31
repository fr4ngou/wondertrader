"""唯一1.1.2固定JSON样本，只消费已安装产品公共入口。"""
from pathlib import Path
import json
import sys

from guanheng_strategy_core.contracts import canonical_bytes
from guanheng_strategy_v1 import (RetainedHistoricalModel, RetainedInput,
    evaluate_current_view, evaluate_historical_model)


def replay(value):
    if (type(value) is not dict or set(value) != {'schema', 'cases'}
            or value['schema'] != 'guanheng.retained-samples.v1'
            or type(value['cases']) is not list or len(value['cases']) != 2):
        raise ValueError('需要唯一1.1.2固定样本集合')
    results = []
    for case in value['cases']:
        if type(case) is not dict or case.get('kind') not in ('current-view', 'historical-model'):
            raise ValueError('样本入口无效')
        historical = case['kind'] == 'historical-model'
        if set(case) != ({'kind', 'request', 'model'} if historical else {'kind', 'request'}):
            raise ValueError('样本字段无效')
        request = RetainedInput.from_dict(case['request'])
        result = (evaluate_historical_model(request, RetainedHistoricalModel.from_dict(case['model']))
            if historical else evaluate_current_view(request)).to_dict()
        assert result['strategy_version'] == '1.1.2'
        assert not result['source_qualified'] and not result['execution_qualified']
        assert len(result['targets']) == 8
        results.append(result)
    return dict(schema='guanheng.retained-sample-results.v1', results=results)


if __name__ == '__main__':
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('INPUT.json')
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_name('ACTUAL.json')
    with source.open('rb') as stream:
        raw = stream.read(8388609)
    if len(raw) > 8388608:
        raise ValueError('样本超过输入容量')
    result = replay(json.loads(raw))
    with target.open('xb') as stream:
        stream.write(canonical_bytes(result))
    print(json.dumps(dict(passed=True, cases=len(result['results']), strategy_version='1.1.2')))
