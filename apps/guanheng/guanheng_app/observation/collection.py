"""单一采集/计算/发布owner；手动与计划窗口共用同一主链。"""
import copy
import json
from time import monotonic
from datetime import date,datetime,timedelta,timezone
from .admission import admit_dataset,register_standard_assets,register_standard_asset
from .contracts import ObservationError,USAGE
from .source_fetch import BoundedContentStore,CollectionBudget,Fetcher,SourceFailure
from .providers import ADAPTERS
from .disclosures import gov10y,repo_fixing
from .supplemental import northbound,marketcap_gdp,rebase_gdp_dependencies,fund_allocation,pbc_bank
from .refresh_models import merge,market_models,spread_and_bond,attach_sse_reference,source_window,source_observation_dates
from .daily_context import attach_daily_context
from .calendars import admit_calendars, closed_day_cutoff, last_open_day, official_calendar
from .metadata import asset_contract,computation_identity
from .publication import validate_manifest,VALIDATION_CONTRACT
from .asset_index import compact_assets
from .query import ObservationReader,parquet_bytes
from .storage import digest,encode
from .stock_partitions import extend_daily_partitions
from .wondertrader_source import history as market_history, prepare_table as prepare_market_table
from .breadth_models import METRICS as BREADTH_METRICS, admit_definition, prepare_definitions,attach_boards
from . import financial_models, executive_models, t2108_models
from .financial_source import annual_reports
from .executive_source import executive_changes
from .t2108_feed import history as t2108_history
from .wt_t2108_source import history as wt_t2108_history
from .wt_breadth_source import history as wt_breadth_history
from .ashare_source import history as ashare_history
from .ashare_public import history as public_ashare_history
from .breadth_trends import attach_trends, attach_benchmark
from .legulegu_source import history as legulegu_history
from .nfra_source import history as nfra_history
from . import legulegu_gdp
from . import institution_reports, bond_mtm, shareholder_source
from . import market_structure, market_structure_source
from . import etf_flow, wt_margin_summary
from .collection_config import WT_DERIVED
from .data_repair import WT_SOURCES
from .gov10y_source import TABLE as GOV10Y_TABLE, WT_KIND as WT_GOV10Y
from .wt_gov10y_source import history as wt_gov10y_history

PARSERS = dict(ADAPTERS,gov10y=gov10y,repo_fixing=repo_fixing,northbound=northbound,
    marketcap_gdp=marketcap_gdp,fund_allocation=fund_allocation,pbc_bank=pbc_bank,
    executive_changes=executive_changes,ashare_snapshot=ashare_history,legulegu_pb=legulegu_history,nfra_insurance=nfra_history,legulegu_gdp=legulegu_gdp.history,
    pbc_custody=institution_reports.pbc_custody,wealth_allocation=institution_reports.wealth_allocation,
    citic_broker=institution_reports.citic_broker,chinabond_wealth=bond_mtm.history)


def refresh(reader,config,*,as_of,deadline,source_ids=None,window_key=None,now=None,cancelled=None,
            fetcher_factory=Fetcher,market_client_factory=None,structure_history_start=None,repair_history_start=None,
            repair_history_end=None):
    """采集lease持有整个批次；CAS、窗口及成功回执由原目录一次提交。

    调用者提供原绝对D与已准入配置。外部SDK在独立受管进程内运行；
    本函数不创建另一线程/队列，不操作策略、账户或真实下撤单。
    """
    if structure_history_start is not None:
        allowed={source['id'] for source in config['sources']
                 if source['kind'] in (market_structure_source.CSI_KIND,market_structure_source.STOCK_KIND)}
        if (window_key or not source_ids or set(source_ids)-allowed
                or not market_structure_source.FIRST_DAY<=structure_history_start<=as_of
                or date.fromisoformat(structure_history_start).isoformat()!=structure_history_start):
            raise ObservationError('invalid_structure_backfill','市场结构补历史需要显式来源与有效起始日',422)
    if repair_history_start is not None:
        eligible={source['id'] for source in config['sources'] if source['kind'] in WT_SOURCES}
        if (window_key or not source_ids or set(source_ids)-eligible or structure_history_start is not None
                or repair_history_start>as_of or date.fromisoformat(repair_history_start).isoformat()!=repair_history_start):
            raise ObservationError('invalid_data_repair_range','补齐历史需要已登记的 WT 来源和有效日期',422)
    if repair_history_end is not None and (repair_history_start is None
            or not repair_history_start<=repair_history_end<=as_of
            or date.fromisoformat(repair_history_end).isoformat()!=repair_history_end):
        raise ObservationError('invalid_data_repair_range','补齐历史窗口结束日期无效',422)
    CollectionBudget(deadline,cancelled=cancelled).remaining()
    deadline=min(deadline,monotonic()+config.get('budget',{}).get('seconds',600))
    with reader.repository.collection_lease() as acquired:
        if not acquired:return dict(status='another_owner_running')
        attempt=None
        if window_key:
            from .schedule_policy import window_as_of
            now=now if now is not None else datetime.now(timezone.utc)
            if window_as_of(window_key,now,config['schedule'],config['models'])!=as_of:
                raise ObservationError('invalid_schedule_window','观察窗口与来源日期不一致',422)
            try:
                attempt=reader.repository.reserve_window_attempt(window_key,now,config['max_window_attempts'],config['retry_seconds'],
                    deadline=deadline,cancelled=cancelled,schedule=config['schedule'])
            except ObservationError as exc:
                if exc.code=='write_outcome_unknown':
                    return dict(status='attempt_unknown',window_key=window_key,error_code=exc.code)
                raise
            if attempt['status']!='reserved':return attempt
        return _refresh(reader,config,as_of=as_of,deadline=deadline,source_ids=source_ids,
            window_key=window_key,attempt=attempt,cancelled=cancelled,now=now,
            fetcher_factory=fetcher_factory,market_client_factory=market_client_factory,
            structure_history_start=structure_history_start,repair_history_start=repair_history_start,
            repair_history_end=repair_history_end)


def _refresh(reader,config,*,as_of,deadline,source_ids,window_key,attempt,cancelled,fetcher_factory,market_client_factory,
             now=None,structure_history_start=None,repair_history_start=None,repair_history_end=None):
    from .schedule_policy import source_as_of,local_now
    # 计划补跑使用原窗口时点；手动历史刷新保留显式日期，当日刷新使用真实时钟。
    observed_now=local_now(now if now is not None else datetime.now(timezone.utc))
    cutoff=datetime.fromisoformat(window_key) if window_key else observed_now
    if not window_key and as_of<observed_now.date().isoformat():
        cutoff=datetime.fromisoformat(as_of+'T23:59:00+08:00')
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
            # 手工历史as_of是所选日期；WT前日上限由实际观察时钟限定，避免历史再退一天。
            policy_clock=observed_now if not window_key and source.get('date_policy')=='cn-prior-day' else cutoff
            effective=source_as_of(source,as_of,config,policy_clock,check=budget.remaining)
            last=max(observed+existing) if observed or existing else effective
            start,end=source_window(last,effective,source,config)
            if repair_history_start is not None:
                start=min(start,repair_history_start)
                if source['kind']=='wt_breadth':
                    start=repair_history_start
                    end=min(effective,(date.fromisoformat(start)+timedelta(days=config['max_days_per_batch']-1)).isoformat())
                if source['kind']=='wt_t2108':
                    # 每批只检查一个缺日，避免把尚未读取的股池日期标成已查。
                    start=end=repair_history_start
            if source['kind'] in (*etf_flow.ETF_KINDS,*WT_DERIVED,wt_margin_summary.KIND):
                calendar=config['models']['calendars']['cn']
                latest=(date.fromisoformat(effective)-timedelta(days=source['overlap_days'])).isoformat()
                start=max(repair_history_start or latest,source['history_from'],calendar['coverage_start'])
                end=min(effective,(date.fromisoformat(start)+timedelta(days=config['max_days_per_batch']-1)).isoformat())
            if source['kind']=='wondertrader':
                # 完整重取原表覆盖范围；所有量窗口改用同一A来源，不混用旧供应商量。
                start=min(existing+[start]) if repair_history_start is not None else min(existing) if existing else start
                end=effective
            if source['kind'] in (market_structure_source.CSI_KIND,market_structure_source.STOCK_KIND,
                                  market_structure_source.WT_STOCK_KIND):
                calendar=config['models']['calendars']['cn']
                start=structure_history_start or max(repair_history_start or (start if existing else source['history_from']),
                    calendar['coverage_start'],source['history_from'])
                if structure_history_start is not None:
                    effective=min(effective,as_of)
                end=min(effective,(date.fromisoformat(start)+timedelta(days=config['max_days_per_batch']-1)).isoformat())
            if source['kind']==market_structure_source.WT_INDEX_KIND:
                calendar=config['models']['calendars']['cn']
                floor=max(calendar['coverage_start'],source['history_from'])
                sessions,_=official_calendar(calendar,check=budget.remaining)
                index_days=[row['date'] for row in sessions if row['is_open'] and floor<=row['date']<=effective]
                # 日更从有效日回查。历史缺口由补齐任务的窗口游标推进。
                start=max(floor,repair_history_start or
                          (date.fromisoformat(effective)-timedelta(days=source['overlap_days'])).isoformat())
                end=min(effective,(date.fromisoformat(start)+timedelta(days=config['max_days_per_batch']-1)).isoformat())
            if repair_history_end is not None:
                end=min(end,repair_history_end)
            # effective_as_of是本来源截止日；requested_end仍可受既有分批上限约束。
            receipt.update(requested_start=start,requested_end=end,
                effective_as_of=effective,  # YYYY-MM-DD：本来源按窗口时点及所选日历得到的有效查询截止。
                date_policy=source.get('date_policy','legacy'))  # 本来源日期口径；legacy表示沿调用者原as_of。
            if source['kind'] in (market_structure_source.WT_INDEX_KIND,market_structure_source.WT_STOCK_KIND,WT_GOV10Y,wt_margin_summary.KIND,
                                  *etf_flow.ETF_KINDS,*WT_DERIVED,'wt_breadth','wt_t2108'):
                calendar=config['models']['calendars']['cn']
                producer_day=last_open_day(calendar,closed_day_cutoff(observed_now),check=budget.remaining)
                prior_day=last_open_day(calendar,(observed_now.date()-timedelta(days=1)).isoformat(),check=budget.remaining)
                versions=sorted({producer_day,prior_day,effective},reverse=True)
            if source['kind']=='wondertrader':
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=market_history(fetch,source,start,end,market_client_factory)
            elif source['kind']==WT_GOV10Y:
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                start=max(start,source['history_from'])
                updates=wt_gov10y_history(fetch,start,end,market_client_factory,snapshot_dates=versions)
            elif source['kind']==wt_margin_summary.KIND:
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=wt_margin_summary.history(fetch,start,end,market_client_factory,snapshot_dates=versions)
            elif source['kind'] in (market_structure_source.CSI_KIND, market_structure_source.STOCK_KIND):
                stock_rows=tables.get(market_structure_source.STOCK_TABLE,[])
                updates=market_structure_source.history(fetch,source,start,end,calendar,
                    existing={r['date'] for r in stock_rows if r['sample_count'] is not None})
            elif source['kind']==market_structure_source.WT_STOCK_KIND:
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=market_structure_source.wt_stock_history(fetch,start,end,calendar,market_client_factory,
                                                                  snapshot_dates=versions)
            elif source['kind']==market_structure_source.WT_INDEX_KIND:
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=market_structure_source.wt_index_history(fetch,start,end,calendar,market_client_factory,
                                                                  snapshot_dates=versions)
            elif source['kind']=='ashare_public':
                # 同批成功Baostock的原字符串表已归档；公开全A组合沿同一原件继续，减少重复网络取数。
                admitted=[]
                stock_sources={item['id'] for item in config['sources'] if item['kind']=='baostock'}
                for earlier in receipts:
                    if earlier['source_id'] in stock_sources and earlier.get('status')=='success':
                        admitted.extend(json.loads(reader.objects.get(earlier['source_manifest'])))
                updates=public_ashare_history(reader,fetch,source,start,end,
                    retry_seconds=config['retry_seconds'],max_attempts=config['max_window_attempts'],admitted_records=admitted)
            elif source['kind']=='qmt_t2108':
                updates=t2108_history(fetch,source,start,end,calendar=config['models'].get('calendars',{}).get('cn'))
            elif source['kind']=='wt_breadth':
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=wt_breadth_history(fetch,source,start,end,market_client_factory,
                    calendar=calendar,snapshot_dates=versions)
            elif source['kind'] in etf_flow.ETF_KINDS:
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=etf_flow.history(fetch,source,start,end,market_client_factory,
                                         calendar=calendar,snapshot_dates=versions)
            elif source['kind'] in WT_DERIVED:
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=WT_DERIVED[source['kind']].history(fetch,start,end,market_client_factory,
                                                           calendar=calendar,snapshot_dates=versions)
            elif source['kind']=='wt_t2108':
                if market_client_factory is None:raise SourceFailure('market_source_not_configured')
                updates=wt_t2108_history(fetch,source,start,end,market_client_factory,
                    calendar=calendar,snapshot_dates=versions)
            elif source['kind']=='shareholder_changes':
                key=shareholder_source.METRIC
                if key not in datasets:raise SourceFailure('shareholder_archive_required')
                updates={key:shareholder_source.history(fetch,source,start,end,datasets[key],tables,market_client_factory)}
            elif source['kind']=='financial_annual':
                key='source.financial_'+source.get('scope','shsz')+'_universe'
                updates=annual_reports(fetch,source,start,end,admitted_rows=tables.get(key,()))
            else:updates=PARSERS[source['kind']](fetch,source,start,end)
            allowed=set(source.get('tables',[]))|set(source.get('datasets',[]))
            if set(updates)-allowed:raise SourceFailure('unregistered_source_output')
            prepared={};revisions=[];count=0;prepared_definitions={};retained_dates={}
            for key,rows in updates.items():
                # 来源配置决定事实所有者；同名只读指标投影不取得原源表写入权。
                # market.sh000001同时有源表和页面投影，必须先更新原表再统一派生。
                is_table=key in source.get('tables',[])
                budget.remaining();old=tables.get(key,[]) if is_table else datasets.get(key,[])
                if source['kind']in ('qmt_t2108','wt_t2108') and key==t2108_models.METRIC:
                    old=t2108_models.versioned_history(old,definitions[key]['definition_version'])
                if key in BREADTH_METRICS:
                    prepared_definitions[key]=admit_definition(key,definitions.get(key),old,rows)
                if source['kind'] in WT_DERIVED:
                    derived=WT_DERIVED[source['kind']]
                    prepared_definitions[key]=derived.definition()
                    prior={row['date']:row for row in old if derived.row_complete(row)}
                    rows=[row if derived.row_complete(row) else prior.get(row['date'],row) for row in rows]
                if source['kind'] in etf_flow.ETF_KINDS:
                    if source['kind']==etf_flow.CAP_KIND:
                        prepared_definitions[key]=etf_flow.cap_definition()
                    else:
                        symbol=next(symbol for symbol in source['symbols'] if etf_flow.metric(symbol)==key)
                        prepared_definitions[key]=etf_flow.definition(symbol)
                    field=prepared_definitions[key]['primary_field']
                    # 每行估算及其输入来自同一WT版本；缺口保留上一整行有效估算。
                    by_date={row['date']:row for row in old}
                    rows=[by_date[row['date']] if row[field] is None and
                          by_date.get(row['date'],{}).get(field) is not None else row for row in rows]
                if source.get('replace_tables'):
                    if not is_table:
                        raise SourceFailure('market_existing_coverage_missing')
                    if source['kind']=='wondertrader':
                        prepared[key],changes,retained=prepare_market_table(key,old,rows,effective)
                        if retained:retained_dates[key]=retained
                    else:
                        if not {r['date'] for r in old if r['date']<=effective}<={r['date'] for r in rows}:
                            raise SourceFailure('market_existing_coverage_missing')
                        # 补跑旧窗口保留已接纳的更晚真实行；替换仅覆盖本次请求截止以内。
                        prepared[key],changes=merge([r for r in old if r['date']>effective],rows)
                else:prepared[key],changes=merge(old,rows,tenor=definitions.get(key,{}).get('axis_type')=='tenor')
                revisions.extend(dict(metric_id=key,**item) for item in changes);count+=len(rows)
            raw_manifest=reader.objects.put(encode(fetch.records),kind='standard')
            definitions.update(prepared_definitions)
            if source['kind']in ('qmt_t2108','wt_t2108'):definitions[t2108_models.METRIC]=t2108_models.definition()
            for key,rows in prepared.items():
                if key in source.get('tables',[]):
                    tables[key]=rows
                    table_parents[key]=[raw_manifest,*([manifest['source_tables'][key]] if key in manifest.get('source_tables',{}) else [])]
                else:datasets[key]=rows
            incomplete=source['kind']==market_structure_source.STOCK_KIND and any(
                item.get('diagnostic_code') for item in fetch.records)
            etf_incomplete=False
            if source['kind'] in etf_flow.ETF_KINDS:
                etf_field='ratio' if source['kind']==etf_flow.CAP_KIND else 'flow'
                sessions,_=official_calendar(calendar,check=budget.remaining)
                expected={row['date'] for row in sessions if row['is_open'] and start<=row['date']<=end}
                etf_incomplete=any(expected-{row['date'] for row in updates.get(key,())
                    if (etf_flow.cap_row_complete(row) if source['kind']==etf_flow.CAP_KIND else row[etf_field] is not None)}
                                   for key in source['datasets'])
            def observed_dates(items):
                return [row['date'] for rows in items for row in rows
                        if (source['kind']!=market_structure_source.STOCK_KIND or row['sample_count'] is not None)
                        and (source['kind'] not in etf_flow.ETF_KINDS or row[etf_field] is not None)]
            receipt.update(status='partial' if incomplete or etf_incomplete else 'checked_disclosure' if source['kind']=='disclosure' else 'success' if count else 'no_new_observations',
                observations=count,revisions=revisions,source_manifest=raw_manifest,
                latest_period=max(observed_dates(updates.values()),default=None),
                loaded_period=max(source_observation_dates(datasets,definitions,source.get('datasets',[]))+
                    observed_dates(tables.get(key,[]) for key in source.get('tables',[])),
                    default=None if source['kind']==market_structure_source.STOCK_KIND else last))
            if incomplete:receipt['error_code']='market_structure_stock_partial'
            if etf_incomplete:receipt['error_code']='wt_history_incomplete'
            if source['kind'] in WT_DERIVED:
                derived=WT_DERIVED[source['kind']]
                rows=updates.get(derived.METRIC,())
                receipt.update(latest_period=max((row['date'] for row in rows if derived.row_complete(row)),default=None),
                               loaded_period=max((row['date'] for row in datasets.get(derived.METRIC,())
                                                   if derived.row_complete(row)),default=None))
                if any(not derived.row_complete(row) for row in rows):
                    receipt.update(status='partial',error_code='wt_history_incomplete')
            if source['kind']==market_structure_source.WT_STOCK_KIND:
                sessions,_=official_calendar(calendar,check=budget.remaining)
                expected={row['date'] for row in sessions if row['is_open'] and start<=row['date']<=end}
                if expected-{row['date'] for row in updates[market_structure_source.STOCK_TABLE]}:
                    receipt.update(status='partial',error_code='wt_history_incomplete')
            if source['kind']==market_structure_source.WT_INDEX_KIND:
                received=set.intersection(*({row['date'] for row in updates[key]
                    if market_structure_source.index_row_complete(key,row)} for key in source['tables']))
                loaded=set.intersection(*({row['date'] for row in tables[key]
                    if market_structure_source.index_row_complete(key,row)} for key in source['tables']))
                receipt.update(latest_period=max(received,default=None),loaded_period=max(loaded,default=None))
                if any(start<=day<=end and day not in loaded for day in index_days):
                    receipt.update(status='partial',error_code='wt_history_incomplete')
            if source['kind']==wt_margin_summary.KIND:
                sessions,_=official_calendar(calendar,check=budget.remaining)
                loaded={row['date'] for row in tables[wt_margin_summary.TABLE] if wt_margin_summary.row_complete(row)}
                receipt.update(latest_period=max((row['date'] for row in updates[wt_margin_summary.TABLE]
                                                  if wt_margin_summary.row_complete(row)),default=None),
                               loaded_period=max(loaded,default=None))
                if any(row['is_open'] and start<=row['date']<=end and row['date'] not in loaded for row in sessions):
                    receipt.update(status='partial',error_code='wt_history_incomplete')
            # 表ID→ISO交易日：原参考表已接纳、本次原生日线未返回而继续保留的日期。
            # 字段缺省表示无需保留；不将旧观察重标成本次新采集。
            if retained_dates:receipt['retained_dates']=retained_dates
            successes+=1
        except Exception as exc:
            receipt.update(status='failed',error_code=exc.code if isinstance(exc,(SourceFailure,ObservationError)) else 'source_parse_failed')
            # diagnostic仅在适配器有固定阶段证据时出现；缺项表示未提供该类诊断，不推定成功。
            if isinstance(exc,SourceFailure) and exc.diagnostic is not None:receipt['diagnostic']=exc.diagnostic
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
        bond_mtm.extend(tables,datasets,check=finalization.remaining)
        if bond_mtm.TABLE in tables and bond_mtm.METRIC in definitions:
            bond_mtm.update_definition(definitions[bond_mtm.METRIC])
        mapping=config['models'].get('daily_context',{})
        if 'valuation_marketcap_gdp_observed' in datasets:
            datasets['valuation_marketcap_gdp_observed']=merge(datasets['valuation_marketcap_gdp_observed'],datasets.get('valuation_marketcap_gdp_monthly',[]))[0]
        rebase_gdp_dependencies(tables,datasets);attach_daily_context(tables,datasets,definitions,mapping)
        financial_models.refresh_ranks(datasets,check=finalization.remaining)
        attach_trends(datasets,definitions,tables,check=finalization.remaining)
        attach_benchmark(datasets,definitions,tables)
        structure_inputs=market_structure.derive(tables,datasets,definitions,check=finalization.remaining)
        margin_rows=tables.get(wt_margin_summary.TABLE, [])
        if margin_rows and 'leverage_margin' in datasets:
            datasets['leverage_margin']=merge(datasets['leverage_margin'],margin_rows)[0]
        for row in datasets.get('leverage_margin',[]):
            if row.get('fin_buy') is not None and row.get('fin_repay') is not None:row['fin_net_arithmetic']=row['fin_buy']-row['fin_repay']
        if 'leverage_margin' in datasets:datasets['margin.short']=[dict(r) for r in datasets['leverage_margin']]
        for key in sorted(datasets,key=lambda name:bool(definitions[name].get('input_metrics'))):
            rows=datasets[key]
            if key not in manifest['datasets'] and not rows:continue
            finalization.remaining();definition=definitions[key]
            relevant=[r for r in receipts if any(s['id']==r['source_id'] and key in s.get('datasets',[])+s.get('derived_metrics',[])+s.get('tables',[]) for s in config['sources'])]
            if relevant:definition['freshness']=dict(last_checked_at=run['completed_at'],source_results=relevant,loaded_end=rows[-1]['date'] if rows else None)
            if definition['board'] in (etf_flow.BOARD,etf_flow.CAP_BOARD):
                available=[row['date'] for row in rows if row[definition['primary_field']] is not None]
                definition['primary_coverage']=dict(start=min(available,default=None),end=max(available,default=None),
                                                    observations=len(available))
            for derived in WT_DERIVED.values():
                if key == derived.METRIC:
                    available=[row['date'] for row in rows if derived.row_complete(row)]
                    definition['primary_coverage']=dict(start=min(available,default=None),end=max(available,default=None),
                                                        observations=len(available))
            if key==legulegu_gdp.METRIC:legulegu_gdp.update_definition(definition,rows,relevant,run['completed_at'])
            if key in ('bond.custody','holdings_wealth','holdings_broker') and relevant and any(
                    source['kind'] in ('pbc_custody','wealth_allocation','citic_broker')
                    and key in source.get('datasets',[]) for source in config['sources']):
                institution_reports.update_definition(key,definition,rows,relevant,run['completed_at'])
            if key==bond_mtm.METRIC and bond_mtm.TABLE in tables and relevant:
                institution_reports.update_definition(key,definition,rows,relevant,run['completed_at'])
            old=manifest['datasets'].get(key,dict(parents=[]))
            universe_table=definition.get('universe_table')
            if universe_table in tables:
                definition['universe_version']=reader.objects.put(parquet_bytes(tables[universe_table]),kind='standard')
            context_parents=table_parents.get('market.'+mapping[key]['symbol'],[]) if key in mapping else []
            if key in ('spread_sw', 'bond.erp_rank756'):
                context_parents=[*context_parents, *table_parents.get(GOV10Y_TABLE, [])]
            if key in wt_margin_summary.DATASETS and wt_margin_summary.TABLE in tables:
                context_parents=[*context_parents,*table_parents.get(wt_margin_summary.TABLE, [])]
            if key in structure_inputs:
                context_parents=[reader.objects.put(parquet_bytes(tables[name]),kind='standard')
                                 for name in structure_inputs[key]]
            if key==bond_mtm.METRIC and bond_mtm.TABLE in tables:
                context_parents=[*context_parents,*[parent for name in
                    (bond_mtm.TABLE,'source.csi_all','market.sh000001') for parent in table_parents.get(name,[])]]
            if key==shareholder_source.METRIC and any(r['status']=='success' for r in relevant):
                context_parents=[*context_parents,*[parent for name in shareholder_source.INDEX_TABLES.values()
                    for parent in table_parents.get(name,[])]]
            input_parents=[candidate['datasets'][name]['partition'] for name in definition.get('input_metrics',[])]
            # 只登记直接前代和本轮输入；递归历史由原不可变快照持有，避免每轮复制历史图。
            candidate['datasets'][key]=admit_dataset(reader.objects,definition,rows,[*([old['partition']] if 'partition' in old else []),*context_parents,*input_parents,
                *[r['source_manifest'] for r in relevant if r.get('source_manifest')]])
        candidate['source_tables']={key:reader.objects.put(parquet_bytes(rows),kind='standard') for key,rows in tables.items()}
        attach_boards(candidate,candidate['datasets'])
        financial_models.attach_boards(candidate,candidate['datasets'])
        executive_models.attach_boards(candidate,candidate['datasets'])
        t2108_models.attach_board(candidate)
        market_structure.attach_boards(candidate)
        etf_flow.attach_board(candidate)
        for derived in WT_DERIVED.values():
            if derived.METRIC in candidate['datasets']:
                if not any(board['id']==derived.METRIC for board in candidate['boards']):
                    candidate['boards'].append(dict(id=derived.METRIC,label=derived.LABEL))
                candidate['preferences']['default_datasets'][derived.METRIC]=derived.METRIC
        candidate['source_table_parents']=table_parents
        active_assets=set()  # 本轮真实生成/复用的抓取资产身份；同内容复用也保持本轮登记。
        for receipt in receipts:
            if 'source_manifest' not in receipt:continue
            records=json.loads(reader.objects.get(receipt['source_manifest']))
            active_assets.add(register_standard_asset(reader.objects,candidate,receipt['source_id']+'.capture',receipt['source_manifest'],
                [item['sha256'] for item in records],'standard.capture-manifest'))
            if receipt['status']=='success':extend_daily_partitions(reader.objects,candidate,records,check=finalization.remaining)
            source=next(item for item in config['sources'] if item['id']==receipt['source_id'])
            for index,item in enumerate(records):
                identity=digest(encode(dict(source=receipt['source_id'],capture=receipt['started_at'],index=index,sha256=item['sha256'])))
                active_assets.add(identity)
                candidate['assets'][identity]=asset_contract(dict(asset_id=identity,sha256=item['sha256'],bytes=len(reader.objects.get(item['sha256'])),
                    group='source.capture',source_ref=receipt['source_id'],retrieved_at=item.get('retrieved_at'),ingested_at=run['completed_at'],
                    qualification='captured_bytes',usage=candidate['usage']),source=source,record=item,capture_id=receipt['source_manifest'])
        register_standard_assets(reader.objects,candidate)
        run['asset_index']=compact_assets(reader.objects,candidate,manifest,previous,active_asset_ids=active_assets)
        candidate['computation_identity']=computation_identity()
        candidate['source_configuration_sha256']=digest(encode(config));candidate['published_at']=run['completed_at'];candidate['parent_snapshot']=previous
        candidate['validation_contract']=VALIDATION_CONTRACT
        run['validation']=validate_manifest(reader,candidate,work_deadline,previous_snapshot=previous)
        finalization.remaining()
        run['completed_at']=candidate['published_at']=_now()
        run.update(status='partial' if any(r['status'] in ('failed','partial') for r in receipts) else 'success',current_snapshot=digest(encode(candidate)))
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
