"""单一采集/计算/发布owner；手动与计划窗口共用同一主链。"""
import copy
import json
from time import monotonic
from datetime import datetime,timezone
from .admission import admit_dataset,register_standard_assets,register_standard_asset
from .contracts import ObservationError,USAGE
from .source_fetch import BoundedContentStore,CollectionBudget,Fetcher,SourceFailure
from .providers import ADAPTERS
from .disclosures import gov10y,repo_fixing
from .supplemental import northbound,marketcap_gdp,rebase_gdp_dependencies,fund_allocation,pbc_bank
from .refresh_models import merge,market_models,spread_and_bond,attach_sse_reference,source_window,source_observation_dates
from .daily_context import attach_daily_context
from .calendars import admit_calendars
from .metadata import asset_contract,computation_identity
from .publication import validate_manifest
from .query import ObservationReader,parquet_bytes
from .storage import digest,encode
from .stock_partitions import extend_daily_partitions
from .wondertrader_source import history as market_history
from .breadth_models import METRICS as BREADTH_METRICS, admit_definition, prepare_definitions,attach_boards
from . import financial_models, executive_models, t2108_models
from .financial_source import annual_reports
from .executive_source import executive_changes
from .t2108_source import history as t2108_history
from .ashare_source import history as ashare_history
from .ashare_public import history as public_ashare_history
from .breadth_trends import attach_trends, attach_benchmark

PARSERS = dict(ADAPTERS,gov10y=gov10y,repo_fixing=repo_fixing,northbound=northbound,
    marketcap_gdp=marketcap_gdp,fund_allocation=fund_allocation,pbc_bank=pbc_bank,financial_annual=annual_reports,
    executive_changes=executive_changes,qmt_t2108=t2108_history,ashare_snapshot=ashare_history)


def refresh(reader,config,*,as_of,deadline,source_ids=None,window_key=None,now=None,cancelled=None,
            fetcher_factory=Fetcher,market_client_factory=None):
    """采集lease持有整个批次；CAS、窗口及成功回执由原目录一次提交。

    调用者提供原绝对D与已准入配置。外部SDK在独立受管进程内运行；
    本函数不创建另一线程/队列，不操作策略、账户或真实下撤单。
    """
    CollectionBudget(deadline,cancelled=cancelled).remaining()
    deadline=min(deadline,monotonic()+config.get('budget',{}).get('seconds',600))
    with reader.repository.collection_lease() as acquired:
        if not acquired:return dict(status='another_owner_running')
        attempt=None
        if window_key:
            from .schedule_policy import window_as_of
            now=now if now is not None else datetime.now(timezone.utc)
            if window_as_of(window_key,now)!=as_of:
                raise ObservationError('invalid_schedule_window','观察窗口与来源日期不一致',422)
            try:
                attempt=reader.repository.reserve_window_attempt(window_key,now,config['max_window_attempts'],config['retry_seconds'],
                    deadline=deadline,cancelled=cancelled)
            except ObservationError as exc:
                if exc.code=='write_outcome_unknown':
                    return dict(status='attempt_unknown',window_key=window_key,error_code=exc.code)
                raise
            if attempt['status']!='reserved':return attempt
        return _refresh(reader,config,as_of=as_of,deadline=deadline,source_ids=source_ids,
            window_key=window_key,attempt=attempt,cancelled=cancelled,
            fetcher_factory=fetcher_factory,market_client_factory=market_client_factory)


def _refresh(reader,config,*,as_of,deadline,source_ids,window_key,attempt,cancelled,fetcher_factory,market_client_factory):
    limits=config['budget']
    # 编码/校验在原D前结束，为同一目录事务或失败回执保留收束时间。
    # 收束仍服从调用者原D；短预算按比例保留，最长5秒。
    closing_reserve=min(5.0,CollectionBudget(deadline,cancelled=cancelled).remaining()/20)
    work_deadline=deadline-closing_reserve
    finalization=CollectionBudget(work_deadline,cancelled=cancelled)
    # 外部来源可耗尽采集阶段；原总D内保留五分之一（至多60秒）完成存证和事务发布。
    reserve=min(60.0,finalization.remaining()/5)
    budget=CollectionBudget(work_deadline-reserve,limits['max_requests'],limits['max_bytes'],limits['response_bytes'],cancelled=cancelled)
    reader=ObservationReader(reader.repository,BoundedContentStore(reader.objects,finalization))
    previous=reader.repository.current();receipts=[];successes=0
    selected={s['id'] for s in config['sources']} if source_ids is None else set(source_ids)
    if not selected or selected-{s['id'] for s in config['sources']}:
        raise ObservationError('invalid_source_selection','观察采集来源未登记',422)
    run=dict(started_at=_now(),as_of=as_of,execution_mode='scheduled' if window_key else 'manual',
        previous_snapshot=previous,current_snapshot=previous,sources=receipts,status='failed')
    if window_key:run.update(window_key=window_key,window_complete=False)
    if attempt:run.update(started_at=attempt['started_at'],attempt_number=attempt['attempt_number'])
    try:
        _,manifest=reader.snapshot(previous);candidate=copy.deepcopy(manifest)
        candidate['usage']=dict(USAGE)
        definitions={key:copy.deepcopy(value['definition']) for key,value in manifest['datasets'].items()}
        datasets={key:[dict(row) for row in reader.rows(value['partition'])] for key,value in manifest['datasets'].items()}
        prepare_definitions(definitions,datasets,config['sources'])
        financial_models.prepare_definitions(definitions,datasets,config['sources'])
        executive_models.prepare_definitions(definitions,datasets,config['sources'])
        t2108_models.prepare_definitions(definitions,datasets,config['sources'])
        tables={key:[dict(row) for row in reader.rows(value)] for key,value in manifest.get('source_tables',{}).items()}
        table_parents=copy.deepcopy(manifest.get('source_table_parents',{}))
    except Exception as exc:
        return _failed_run(reader,run,exc,deadline,cancelled)
    for source in config['sources']:
        if source['id'] not in selected:continue
        receipt=dict(source_id=source['id'],started_at=_now());fetch=None
        try:
            budget.remaining()
            timeout=min(config['timeout_seconds'],source.get('timeout_seconds',config['timeout_seconds']))
            fetch=fetcher_factory(reader.objects,config['allowed_hosts'],timeout=timeout,budget=budget)
            observed=source_observation_dates(datasets,definitions,source.get('datasets',[]))
            existing=[row['date'] for key in source.get('tables',[]) for row in tables.get(key,[])]
            last=max(observed+existing) if observed or existing else as_of
            start,end=source_window(last,as_of,source,config)
            if source['kind']=='wondertrader':
                # 完整重取原表覆盖范围；所有量窗口改用同一A来源，不混用旧供应商量。
                start=min(existing) if existing else start;end=as_of
            receipt.update(requested_start=start,requested_end=end)
            if source['kind']=='wondertrader':
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=market_history(fetch,source,start,end,market_client_factory)
            elif source['kind']=='ashare_public':
                updates=public_ashare_history(reader,fetch,source,start,end,
                    retry_seconds=config['retry_seconds'],max_attempts=config['max_window_attempts'])
            else:updates=PARSERS[source['kind']](fetch,source,start,end)
            allowed=set(source.get('tables',[]))|set(source.get('datasets',[]))
            if set(updates)-allowed:raise SourceFailure('unregistered_source_output')
            prepared={};revisions=[];count=0;prepared_definitions={}
            for key,rows in updates.items():
                budget.remaining();old=datasets.get(key,tables.get(key,[]))
                if source['kind']=='qmt_t2108' and key==t2108_models.METRIC:
                    old=t2108_models.versioned_history(old,definitions[key]['definition_version'])
                if key in BREADTH_METRICS:
                    prepared_definitions[key]=admit_definition(key,definitions.get(key),old,rows)
                if source.get('replace_tables'):
                    if key in datasets or not {r['date'] for r in old if r['date']<=as_of}<={r['date'] for r in rows}:
                        raise SourceFailure('market_existing_coverage_missing')
                    prepared[key],changes=merge([],rows)
                else:prepared[key],changes=merge(old,rows,tenor=definitions.get(key,{}).get('axis_type')=='tenor')
                revisions.extend(dict(metric_id=key,**item) for item in changes);count+=len(rows)
            raw_manifest=reader.objects.put(encode(fetch.records),kind='standard')
            definitions.update(prepared_definitions)
            if source['kind']=='qmt_t2108':definitions[t2108_models.METRIC]=t2108_models.definition()
            for key,rows in prepared.items():
                if key in datasets:datasets[key]=rows
                else:
                    tables[key]=rows
                    table_parents[key]=[raw_manifest,*([manifest['source_tables'][key]] if key in manifest.get('source_tables',{}) else [])]
            receipt.update(status='checked_disclosure' if source['kind']=='disclosure' else 'success' if count else 'no_new_observations',
                observations=count,revisions=revisions,source_manifest=raw_manifest,
                latest_period=max((row['date'] for rows in updates.values() for row in rows),default=None),
                loaded_period=max(source_observation_dates(datasets,definitions,source.get('datasets',[]))+
                    [r['date'] for key in source.get('tables',[]) for r in tables.get(key,[])],default=last))
            successes+=1
        except Exception as exc:
            receipt.update(status='failed',error_code=exc.code if isinstance(exc,(SourceFailure,ObservationError)) else 'source_parse_failed')
        finally:
            if fetch is not None:
                try:
                    if 'source_manifest' not in receipt:receipt['source_manifest']=reader.objects.put(encode(fetch.records),kind='standard')
                finally:fetch.close()
        receipt['completed_at']=_now();receipts.append(receipt)
    run.update(completed_at=_now(),requests=budget.requests,http_requests=budget.http_requests,
        sdk_requests=budget.sdk_requests,captured_bytes=budget.captured_bytes,decoded_bytes=budget.decoded_bytes)
    if not successes:
        _record_run(reader,run,deadline,cancelled);return run
    try:
        finalization.remaining();admit_calendars(reader.objects,candidate,tables,config['models'])
        table_parents.update({key:value for key,value in candidate.get('source_table_parents',{}).items() if key.endswith('_official_calendar')})
        market_models(tables,datasets,definitions,config['models'],as_of)
        spread_and_bond(tables,datasets,config['models']);attach_sse_reference(tables,datasets)
        mapping=config['models'].get('daily_context',{})
        if 'valuation_marketcap_gdp_observed' in datasets:
            datasets['valuation_marketcap_gdp_observed']=merge(datasets['valuation_marketcap_gdp_observed'],datasets.get('valuation_marketcap_gdp_monthly',[]))[0]
        rebase_gdp_dependencies(tables,datasets);attach_daily_context(tables,datasets,definitions,mapping)
        financial_models.refresh_ranks(datasets,check=finalization.remaining)
        attach_trends(datasets,definitions,tables,check=finalization.remaining)
        attach_benchmark(datasets,definitions,tables)
        for row in datasets.get('leverage_margin',[]):
            if row.get('fin_buy') is not None and row.get('fin_repay') is not None:row['fin_net_arithmetic']=row['fin_buy']-row['fin_repay']
        if 'leverage_margin' in datasets:datasets['margin.short']=[dict(r) for r in datasets['leverage_margin']]
        for key in sorted(datasets,key=lambda name:bool(definitions[name].get('input_metrics'))):
            rows=datasets[key]
            if key not in manifest['datasets'] and not rows:continue
            finalization.remaining();definition=definitions[key]
            relevant=[r for r in receipts if any(s['id']==r['source_id'] and key in s.get('datasets',[])+s.get('derived_metrics',[])+s.get('tables',[]) for s in config['sources'])]
            if relevant:definition['freshness']=dict(last_checked_at=run['completed_at'],source_results=relevant,loaded_end=rows[-1]['date'] if rows else None)
            old=manifest['datasets'].get(key,dict(parents=[]))
            universe_table=definition.get('universe_table')
            if universe_table in tables:
                definition['universe_version']=reader.objects.put(parquet_bytes(tables[universe_table]),kind='standard')
            context_parents=table_parents.get('market.'+mapping[key]['symbol'],[]) if key in mapping else []
            input_parents=[candidate['datasets'][name]['partition'] for name in definition.get('input_metrics',[])]
            candidate['datasets'][key]=admit_dataset(reader.objects,definition,rows,[*([old['partition']] if 'partition' in old else []),*old['parents'],*context_parents,*input_parents,
                *[r['source_manifest'] for r in relevant if r.get('source_manifest')]])
        candidate['source_tables']={key:reader.objects.put(parquet_bytes(rows),kind='standard') for key,rows in tables.items()}
        attach_boards(candidate,candidate['datasets'])
        financial_models.attach_boards(candidate,candidate['datasets'])
        executive_models.attach_boards(candidate,candidate['datasets'])
        t2108_models.attach_board(candidate)
        candidate['source_table_parents']=table_parents
        for receipt in receipts:
            if 'source_manifest' not in receipt:continue
            records=json.loads(reader.objects.get(receipt['source_manifest']))
            register_standard_asset(reader.objects,candidate,receipt['source_id']+'.capture',receipt['source_manifest'],
                [item['sha256'] for item in records],'standard.capture-manifest')
            if receipt['status']=='success':extend_daily_partitions(reader.objects,candidate,records,check=finalization.remaining)
            source=next(item for item in config['sources'] if item['id']==receipt['source_id'])
            for index,item in enumerate(records):
                identity=digest(encode(dict(source=receipt['source_id'],capture=receipt['started_at'],index=index,sha256=item['sha256'])))
                candidate['assets'][identity]=asset_contract(dict(asset_id=identity,sha256=item['sha256'],bytes=len(reader.objects.get(item['sha256'])),
                    group='source.capture',source_ref=receipt['source_id'],retrieved_at=item.get('retrieved_at'),ingested_at=run['completed_at'],
                    qualification='captured_bytes',usage=candidate['usage']),source=source,record=item,capture_id=receipt['source_manifest'])
        register_standard_assets(reader.objects,candidate)
        candidate['computation_identity']=computation_identity()
        candidate['source_configuration_sha256']=digest(encode(config));candidate['published_at']=run['completed_at'];candidate['parent_snapshot']=previous
        validate_manifest(reader,candidate,work_deadline);finalization.remaining()
        run['completed_at']=candidate['published_at']=_now()
        run.update(status='partial' if any(r['status']=='failed' for r in receipts) else 'success',current_snapshot=digest(encode(candidate)))
        if window_key:run['window_complete']=True
        reader.repository.publish(candidate,previous,receipt=run,deadline=deadline,cancelled=cancelled)
    except Exception as exc:
        return _failed_run(reader,run,exc,deadline,cancelled)
    return run


def _failed_run(reader,run,exc,deadline,cancelled):
    """准备读取与最终采用共用失败收束；未知提交继续保留原候选身份。"""
    if isinstance(exc,ObservationError) and exc.code=='publication_outcome_unknown':
        run.update(status='publication_unknown',candidate_snapshot=run['current_snapshot'],current_snapshot=None,
            completed_at=_now(),error_code=exc.code)
        if run.get('window_key'):run['window_complete']=None
        return run
    run.update(status='failed',current_snapshot=None if isinstance(exc,ObservationError) and exc.code=='publication_conflict' else run['previous_snapshot'],
        completed_at=_now(),error_code=exc.code if isinstance(exc,(ObservationError,SourceFailure)) else 'publication_failed')
    if run.get('window_key'):run['window_complete']=False
    _record_run(reader,run,deadline,cancelled)
    return run


def _record_run(reader,run,deadline,cancelled):
    try:reader.repository.record_run(run,deadline=deadline,cancelled=cancelled)
    except ObservationError as exc:run['receipt_error_code']=exc.code


def _now():
    return datetime.now(timezone.utc).isoformat()
