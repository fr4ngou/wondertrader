"""独立观察只读HTTP：应用有界读池拥有计算和完整导出生命周期。"""

import asyncio
import base64
import csv
import io
import re
from time import monotonic

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from ..reading import ReadCapacityError
from .contracts import API_PREFIX, UI_PREFIX, ExportQuery, ObservationError, SeriesQuery, USAGE
from .publication import check_deadline
from .storage import encode, valid_sha

RESPONSE_BYTES = 16 * 1024 * 1024
REQUEST_SECONDS = 15.0


def observation_error(_request, exc):
    return JSONResponse(dict(code=exc.code, detail=exc.detail), status_code=exc.status,
                        headers={'Cache-Control': 'no-store'})


def _query(path, query):
    if path in ('series', 'exports'):
        return (ExportQuery if path == 'exports' else SeriesQuery).model_validate(query)
    allowed = set() if path == 'updates' or path.startswith('snapshots/') else {'snapshot_id'}
    if path == 'assets':
        allowed |= {'cursor', 'limit', 'q', 'group'}
    if path.startswith('assets/'):
        allowed.add('download')
    if set(query) - allowed:
        raise ObservationError('invalid_query', '观察查询参数未登记', 422)
    if query.get('snapshot_id') is not None:
        valid_sha(query['snapshot_id'])
    if path == 'assets':
        cursor, limit = int(query.get('cursor', '0')), int(query.get('limit', '100'))
        if not 0 <= cursor <= 1000000 or not 1 <= limit <= 200:
            raise ObservationError('invalid_query', '观察资产分页参数无效', 422)
    return query


def _dispatch(owner, path, query, deadline, *, ui):
    check_deadline(deadline)
    fixed = query.get('snapshot_id') if isinstance(query, dict) else query.snapshot_id
    if path == 'catalog':
        return owner.catalog(fixed)
    if path == 'updates':
        status=owner.repository.scheduler_status()
        return dict(runs=owner.repository.runs(),scheduler=status,schedule=status.get('schedule'))
    if path in ('series', 'exports'):
        if path == 'series':
            return owner.series(query, deadline)
        page = owner.series(SeriesQuery.model_validate(query.model_dump(exclude={'format'})), deadline)
        pinned = SeriesQuery.model_validate(query.model_dump(exclude={'format'}, mode='json')).model_copy(
            update={'snapshot_id': page['snapshot_id'], 'cursor': None})
        columns = list(dict.fromkeys(['date', *(pinned.fields.split(',') if pinned.fields else page['definition']['field_schema'])]))
        output = bytearray(b'\xef\xbb\xbf' if query.format == 'csv' else b'[' if query.format == 'json' else b'')
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction='ignore')
        if query.format == 'csv':
            writer.writeheader()
            output.extend(buffer.getvalue().encode('utf8'))
        rows = owner.all_rows(pinned, deadline)
        try:
            for index, row in enumerate(rows):
                check_deadline(deadline)
                if query.format == 'csv':
                    buffer.seek(0)
                    buffer.truncate()
                    writer.writerow(row)
                    body = buffer.getvalue().encode('utf8')
                else:
                    body = (b',' if query.format == 'json' and index else b'') + encode(row)
                    if query.format == 'jsonl':
                        body += b'\n'
                if len(output) + len(body) + 1 > RESPONSE_BYTES:
                    raise ObservationError('response_budget_exceeded', '导出超过容量，请缩短日期或选择字段', 422)
                output.extend(body)
        finally:
            rows.close()
            buffer.close()
        if query.format == 'json':
            output.extend(b']')
        return Response(bytes(output), media_type={'csv': 'text/csv', 'json': 'application/json', 'jsonl': 'application/x-ndjson'}[query.format],
                        headers={'X-Observation-Snapshot': page['snapshot_id'], 'Cache-Control': 'no-store'})
    action, _, identity = path.partition('/')
    if not re.fullmatch('[a-zA-Z0-9_.-]{1,100}', identity) and path != 'assets':
        raise ObservationError('unknown_route', '观察接口或指标身份无效', 404)
    if action == 'snapshots':
        version, manifest = owner.snapshot(valid_sha(identity))
        return dict(snapshot_id=version, published_at=manifest['published_at'],
                    datasets={key: dict(dataset_version=item['partition'], parents=item['parents']) for key, item in manifest['datasets'].items()}, usage=USAGE)
    if action in ('definitions', 'history', 'quality', 'reference'):
        version, definition, item = owner.definition(identity, fixed)
        if action == 'definitions':
            return dict(snapshot_id=version, definition=definition)
        if action == 'history':
            rows = owner.derived(item, definition, SeriesQuery(metric_id=identity), deadline)
            key = definition.get('primary_field') or definition['lines'][0]['key']
            stride = max(1, (len(rows) + 1999) // 2000)
            points = [dict(date=row['date'], value=row.get(key)) for row in rows[::stride]]
            if rows and points[-1]['date'] != rows[-1]['date']:
                points.append(dict(date=rows[-1]['date'], value=rows[-1].get(key)))
            return dict(snapshot_id=version, coverage=definition['coverage'], points=points,
                        aggregation='stride:' + str(stride) if stride > 1 else 'none', raw_count=len(rows))
        if action == 'quality':
            return dict(snapshot_id=version, metric_id=identity, coverage=definition['coverage'],
                        frequency=definition['frequency'], quality=definition.get('quality'),
                        limitations=definition.get('limitations'), freshness=definition.get('freshness'),
                        runs=owner.repository.runs(), usage=USAGE)
        _, manifest = owner.snapshot(version)
        profile = manifest.get('comparison', {}).get('profiles', {}).get(definition['board'], {})
        original = manifest.get('references', {}).get(profile.get('reference', definition['board']), {})
        image = original.get('data')
        if original.get('object_sha256'):
            image = 'data:' + original['media_type'] + ';base64,' + base64.b64encode(owner.objects.get(original['object_sha256'])).decode('ascii')
        return dict(snapshot_id=version, review=definition.get('reference_review'), image=image, profile=profile, usage=USAGE)
    version, manifest = owner.snapshot(fixed)
    if path == 'assets':
        cursor, limit = int(query.get('cursor', '0')), int(query.get('limit', '100'))
        term, group = query.get('q', '').strip().casefold(), query.get('group', '')
        if not 0 <= cursor <= 1000000 or not 1 <= limit <= 200 or len(term) > 200 or len(group) > 100:
            raise ObservationError('invalid_query', '观察资产查询超过范围', 422)
        assets = list(manifest['assets'].values())
        items = sorted((item for item in assets if (not group or item.get('group') == group) and
                        (not term or term in ' '.join(str(item.get(key, '')) for key in
                         ('asset_id', 'sha256', 'group', 'source_ref', 'source_id', 'instrument_id', 'provider_symbol')).casefold())), key=lambda item: item['asset_id'])
        return dict(snapshot_id=version, total=len(items), all_total=len(assets), groups=sorted({item.get('group', '') for item in assets}),
                    items=items[cursor:cursor + limit], next_cursor=cursor + limit if cursor + limit < len(items) else None)
    if action == 'lineage':
        def parents(hashes):
            return [dict(sha256=sha, asset_ids=[item['asset_id'] for item in manifest['assets'].values() if item['sha256'] == sha]) for sha in hashes]
        if identity in manifest['datasets']:
            item = manifest['datasets'][identity]
            return dict(snapshot_id=version, asset_id=identity, partition=item['partition'], parent_assets=item['parents'],
                        parent_objects=parents(item['parents']), parser_version=item['parser_version'], usage=USAGE)
        if identity in manifest['assets']:
            item = manifest['assets'][identity]
            return dict(snapshot_id=version, **item, parent_objects=parents(item.get('parent_assets', [])))
        raise ObservationError('asset_not_found', '观察资产未登记', 404)
    if action == 'assets' and not ui:
        item = manifest['assets'].get(identity)
        if item is None:
            raise ObservationError('asset_not_found', '观察资产未登记', 404)
        if query.get('download', 'false') not in ('true', 'false'):
            raise ObservationError('invalid_query', '观察下载参数无效', 422)
        if query.get('download') == 'true':
            return Response(owner.objects.get(item['sha256']), media_type='application/octet-stream', headers={
                'Content-Disposition': f'attachment; filename="{identity}"', 'Cache-Control': 'no-store', 'X-Observation-Snapshot': version})
        return dict(snapshot_id=version, **item)
    raise ObservationError('unknown_route', '观察接口未登记', 404)


def make_router():
    router = APIRouter()

    async def read_only():
        return JSONResponse(dict(code='read_only', detail='市场观察仅提供只读查询'), status_code=405,
                            headers={'Allow': 'GET', 'Cache-Control': 'no-store'})

    async def read(request: Request, path: str):
        deadline = monotonic() + REQUEST_SECONDS
        if (len(request.url.query) > 6000 or request.headers.get('content-length', '0') != '0'
                or request.headers.get('transfer-encoding')):
            raise ObservationError('invalid_query', '观察读取参数超限或包含正文', 422)
        pairs = list(request.query_params.multi_items())
        if len(pairs) != len({key for key, _ in pairs}):
            raise ObservationError('invalid_query', '观察查询参数重复', 422)
        try:
            query = _query(path, dict(pairs))
        except (ValidationError, ValueError, TypeError):
            raise ObservationError('invalid_query', '观察查询条件无效，请核对日期和参数范围', 422) from None
        owner = getattr(request.app.state, 'observation_owner', None)
        if owner is None:
            error = getattr(request.app.state, 'observation_error', None)
            if error is not None:
                raise ObservationError(error['code'], error['detail'], error['status'])
            raise ObservationError('not_configured', '尚未配置独立市场观察数据', 503)

        def operation(_remaining):
            try:
                result = _dispatch(owner, path, query, deadline, ui=request.url.path.startswith(UI_PREFIX))
                if path=='updates':
                    result['process']=dict(state='independent',label='由独立观察服务更新',
                        reason='更新状态以数据根的最近心跳和来源回执为准')
                check_deadline(deadline)
                if isinstance(result, Response):
                    return result
                body = encode(result)
                if len(body) > RESPONSE_BYTES:
                    raise ObservationError('response_budget_exceeded', '观察结果超过容量，请缩小范围', 422)
                check_deadline(deadline)
                return Response(body, media_type='application/json', headers={'Cache-Control': 'no-store'})
            except ObservationError:
                raise
            except (ValueError, TypeError, KeyError, OSError):
                raise ObservationError('observation_unavailable', '观察数据暂不可用，请重新读取', 503) from None

        future = None
        try:
            future = request.app.state.reader.submit(operation, deadline)
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            return await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline - monotonic()))
        except (ReadCapacityError, TimeoutError):
            raise ObservationError('observation_timeout', '观察读取繁忙或超时，请重新读取', 503) from None
        finally:
            if future is not None:
                future.cancel()

    for prefix in (UI_PREFIX, API_PREFIX):
        router.add_api_route(prefix + '/{path:path}', read, methods=['GET'])
        router.add_api_route(prefix + '/{path:path}', read_only,
                             methods=['POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'])
    return router
