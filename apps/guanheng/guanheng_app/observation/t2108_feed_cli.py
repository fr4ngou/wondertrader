"""来源owner显式发布已封存包；本入口没有SDK、网络或业务current写入。"""
import argparse
from datetime import date
import json
from time import monotonic
from types import SimpleNamespace

from .collection_config import load_configuration
from .contracts import ObservationError
from .source_fetch import CollectionBudget,SourceFailure
from .storage import ContentStore
from .t2108_feed import publish_ready


def main(argv=None):
    """按已固定配置发布一个包；root仅保存原件对象，不创建观察快照。"""
    parser=argparse.ArgumentParser(description='发布T2108已封存原件的定日标记')
    for name in ('root','config','config-sha256','source-id','input-manifest','input-sha256','as-of'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--seconds',type=float,default=600)
    args=parser.parse_args(argv)
    if not 0<args.seconds<=600:parser.error('seconds需要在0至600之间')
    try:
        if date.fromisoformat(args.as_of).isoformat()!=args.as_of:raise ValueError()
    except ValueError:parser.error('as-of需要YYYY-MM-DD')
    try:
        config=load_configuration(args.config,args.config_sha256)
        source=next((item for item in config['sources'] if item['id']==args.source_id),None)
        if source is None or source['kind']!='qmt_t2108' or 'input_directory' not in source:
            raise ObservationError('invalid_source_selection','需要显式T2108原件目录来源',422)
        limits=config['budget'];calendar=config['models']['calendars']['cn']
        context=SimpleNamespace(objects=ContentStore(args.root),records=[],
            budget=CollectionBudget(monotonic()+min(args.seconds,limits['seconds']),
                max_requests=limits['max_requests'],max_bytes=limits['max_bytes'],response_bytes=limits['response_bytes']))
        result=publish_ready(context,source['input_directory'],args.input_manifest,args.input_sha256,
            calendar=calendar,start=calendar['coverage_start'],end=args.as_of)
        result.update(captured_bytes=context.budget.captured_bytes,decoded_bytes=context.budget.decoded_bytes,
            http_requests=0,sdk_requests=0)
    except (ObservationError,SourceFailure) as exc:
        print(json.dumps(dict(status='failed',error_code=exc.code),ensure_ascii=False));return 1
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
