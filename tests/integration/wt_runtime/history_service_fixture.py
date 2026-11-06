"""SMP协议替身：真实父Runtime/Job监督，来源不联网、不创建Reader或账户。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time


def main():
    parser=argparse.ArgumentParser()
    for name in ('config','config-sha256','control-directory','control-id'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    raw=Path(args.config).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.config_sha256
    config=json.loads(raw);root=Path(args.control_directory);root.mkdir()
    identity=dict(control_id=args.control_id,pid=os.getpid(),configuration_sha256=args.config_sha256)
    def publish(name,value):
        temporary=root/('.'+name)
        temporary.write_text(json.dumps(value),encoding='utf8');temporary.replace(root/name)
    publish('seen.json',dict(fixture_version=config['fixture_version'],**identity))
    publish('ready.json',dict(schema='guanheng.source-market-ready.v1',**identity,
        listen_host=config['listen']['host'],listen_port=config['listen']['port']))
    while not (root/'stop.json').exists():time.sleep(.02)
    stop=json.loads((root/'stop.json').read_bytes())
    assert stop['schema']=='guanheng.source-market-stop.v1' and stop['control_id']==args.control_id
    assert time.monotonic()<stop['deadline']
    publish('closed.json',dict(schema='guanheng.source-market-closed.v1',**identity,
        status='stopped',server_closed=True,native_closed=True,error_code=None))


if __name__=='__main__':main()
