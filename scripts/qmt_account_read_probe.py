"""Run four read-only queries against the paired loopback Host."""
import argparse
import http.client
import json
import re
import time
from pathlib import Path
from uuid import uuid4

from guanheng_qmt_shm import bound
from guanheng_qmt_shm.auth import sign_request
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_capabilities import validate_read_request


def check(config, secret):
    if (config['listen_host'] != '127.0.0.1' or config['writes_enabled'] is not False
            or config['read_operations'] != ['account.trade_detail']):
        raise SystemExit('Expected the loopback, account-read-only deployment')

    def exchange(method, target, deadline, body=b''):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Account query deadline expired')
        stamp, nonce, digest = str(time.time()), str(uuid4()), bound.digest(body)
        headers = {
            'X-QMT-Key-Id': config['http_key_id'], 'X-QMT-Timestamp': stamp,
            'X-QMT-Nonce': nonce, 'X-QMT-Content-SHA256': digest,
            'X-QMT-Signature': sign_request(secret, method, target, stamp, nonce, digest),
            'Content-Type': 'application/json',
        }
        conn = http.client.HTTPConnection('127.0.0.1', config['listen_port'], timeout=remaining)
        try:
            conn.request(method, target, body=body, headers=headers)
            reply = conn.getresponse()
            if reply.status not in (200, 202):
                error_code = 'unknown'
                try:
                    candidate = decode(reply.read(4097)).get('error_code')
                    if isinstance(candidate, str) and re.fullmatch(r'[a-z_]{1,64}', candidate):
                        error_code = candidate
                except (ValueError, AttributeError):
                    pass
                raise RuntimeError('{} {} returned HTTP {} ({})'.format(method, target, reply.status, error_code))
            raw = reply.read(1048577)
            if len(raw) > 1048576:
                raise ValueError('Response exceeds verification budget')
            return decode(raw)
        finally:
            conn.close()

    metadata = exchange('GET', '/internal/v1/read-binding', time.monotonic() + 10)
    profile_raw = bound.unb64(metadata['read_profile_body_b64'], 4096)
    binding = metadata['binding']
    if (bound.digest(profile_raw) != metadata['read_profile_body_sha256']
            or bound.digest(profile_raw) != binding['capability_sha256']
            or bound.digest(canonical(binding)) != metadata['binding_sha256']):
        raise ValueError('Host binding or profile digest differs')
    profile = decode(profile_raw)
    operation = 'account.trade_detail'
    policy = config['operation_profiles'][operation]
    for datatype in ('account', 'position', 'order', 'deal'):
        deadline = time.monotonic() + 12
        request_id = str(uuid4())
        request = dict(
            request_id=request_id, correlation_id=str(uuid4()), operation_id=operation,
            arguments=dict(account_type='stock', datatype=datatype, scope='account'),
            timeout_ms=policy['execution_timeout_ms'], policy_id=policy['policy_id'],
            policy_version=policy['policy_version'], priority_class='normal',
        )
        limit = metadata['limits']['max_result_bytes']
        validate_read_request(request, profile, max_result_bytes=limit)
        raw = canonical(request)
        body = canonical(dict(schema_version=bound.SCHEMA, binding_sha256=metadata['binding_sha256'],
                              request_body_b64=bound.b64(raw), request_body_sha256=bound.digest(raw)))
        print('{} request_id={}'.format(datatype, request_id), flush=True)
        result = exchange('POST', '/internal/v1/bound-operations/' + operation, deadline, body)
        while result['state'] != 'terminal':
            if result['request_id'] != request_id:
                raise ValueError('Pending response has a different request identity')
            time.sleep(0.1)
            result = exchange('GET', '/internal/v1/bound-results/' + request_id, deadline)
        bound.validate_response(result, max_result_bytes=limit,
                                control_version=profile['control_profile']['schema_version'])
        if (result['request_id'] != request_id or result['request_body_sha256'] != bound.digest(raw)
                or result['admitted_binding'] != binding):
            raise ValueError('Terminal response has a different request identity')
        payload = decode(bound.unb64(result['result_body_b64'], limit))
        if not payload['ok']:
            raise RuntimeError('{} failed: {}'.format(datatype, payload['error_code']))
        data = payload['data']
        complete = data['completeness']
        if (data['query']['datatype'] != datatype or complete['complete'] is not True
                or complete['truncated'] is not False or complete['row_count'] != len(data['rows'])
                or result['result_binding'] != binding
                or data['account_binding']['account_id'] != config['trade_binding']['account_id']):
            raise ValueError('Account result is incomplete or belongs to a different source')
        print('{} OK rows={} completed_at={}'.format(
            datatype, complete['row_count'], data['execution']['completed_at']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pair_directory', type=Path)
    args = parser.parse_args()
    if not args.pair_directory.is_absolute():
        parser.error('pair_directory must be absolute')
    deployment = json.loads((args.pair_directory / 'deployment.json').read_text(encoding='utf-8'))
    config = deployment['host']
    check(config, deployment['credentials']['http_keys'][config['http_key_id']])
