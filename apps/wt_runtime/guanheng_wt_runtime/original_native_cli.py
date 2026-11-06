"""将两份冻结原版输入/报告构造独立WT会话；实际回测沿原backtest_cli。"""
import argparse
import json
from pathlib import Path
import sys
import time
from .original_native_replay import build_input, _encode
from .strategy_host import _bytes, _json


class _Parser(argparse.ArgumentParser):
    def error(self,message):
        raise ValueError('argument_admission_failed')


def main(argv=None):
    """只准备新会话文件，不联网、不加载DLL、不启动服务；已有输出保持。"""
    parser=_Parser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--snapshot',required=True,type=Path)
    parser.add_argument('--reference-report',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--fee-reserve-cny',default='5000')
    try:
        args=parser.parse_args(argv);deadline=time.monotonic()+60
        snapshot=_json(_bytes(args.snapshot,32*1024*1024,deadline),32*1024*1024,deadline)
        report=_json(_bytes(args.reference_report,16*1024*1024,deadline),16*1024*1024,deadline)
        value=build_input(snapshot,report,fee_reserve_cny=args.fee_reserve_cny)
        raw=_encode(value)
        with args.output.open('xb') as stream:stream.write(raw)
        print(json.dumps({'schema':'guanheng.original-native-preparation.v1','status':'prepared',
            'input_sha256':__import__('hashlib').sha256(raw).hexdigest(),'bytes':len(raw)},ensure_ascii=True))
        return 0
    except Exception:
        print(json.dumps({'schema':'guanheng.original-native-preparation.v1','status':'failed','reason':'frozen input or output admission failed'}))
        return 2


if __name__=='__main__':sys.exit(main())
