"""原融资表目标日空结果与结构损坏区分；不补造余额、不联网。"""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import ContentStore,DAYS,FrozenFetch,QmtTransport,plan
from test_capture_flow import collect
from integrations.guanheng.market_supplement_sources import collect_external,SourceUnavailable


def get_response(value):
    raw=json.dumps(value).encode()
    def get(url,params,referer):
        assert params['reportName']=='RPTA_WEB_MARGIN_DAILYTRADE'
        assert params['filter']=="(STATISTICS_DATE='2026-11-06')"
        return dict(body=raw,sha256=hashlib.sha256(raw).hexdigest(),received_at='2026-11-06T14:57:30+00:00')
    return get


def test_official_empty_date_result_is_missing_record_not_schema_failure():
    empty=dict(success=False,code=9201,result=None,message='empty')
    with pytest.raises(SourceUnavailable)as failure:
        collect_external('margin_balance','CN.MARGIN_REPORT','2026-11-06',get_response(empty))
    assert failure.value.code=='source_record_missing'


@pytest.mark.parametrize('value',[
    dict(success=False,code=9202,result=None),
    dict(success=False,code=9201),
    dict(success=True,code=9201,result=None),
    dict(success=False,code='9201',result=None),
    dict(success=False,code=9201,result={}),
])
def test_other_vendor_errors_or_malformed_empty_envelopes_remain_schema_failure(value):
    with pytest.raises(SourceUnavailable)as failure:
        collect_external('margin_balance','CN.MARGIN_REPORT','2026-11-06',get_response(value))
    assert failure.value.code=='source_schema_invalid'


def test_empty_latest_date_preserves_previous_fact_and_publishes_explicit_gap(tmp_path):
    class MissingLatest(FrozenFetch):
        def get(self,url,params=None,referer=None):
            raw=super().get(url,params,referer)
            if (params.get('reportName')=='RPTA_WEB_MARGIN_DAILYTRADE'
                    and DAYS[-1]in params.get('filter','')):
                return json.dumps(dict(success=False,code=9201,result=None)).encode()
            return raw
    descriptor=collect(tmp_path,plan(('margin_balance','CN.MARGIN_REPORT'),required=False),MissingLatest(),QmtTransport())
    catalog=json.loads(Path(descriptor['path']).read_bytes())
    assert [row['date']for row in catalog['rows']]==[DAYS[0]]
    assert catalog['rows'][0]['value']=='12345678900'
    assert catalog['gaps']==[dict(date=DAYS[-1],metric='margin_balance',symbol='CN.MARGIN_REPORT',reason='source_record_missing')]
    assert catalog['complete'] is False
