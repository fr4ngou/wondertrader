"""原WT/NAP发布的展示副本历史；不拥有资金账、行情估值或交易执行。"""
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from threading import RLock
from time import monotonic
from zoneinfo import ZoneInfo

from .managed_local_process import _inspect
from .watchlist_lock import WindowsLease
from .wt_runtime_observation import RuntimeObservationConfig, resolve_runtime_configuration, read_runtime_snapshot
from .wt_business_observation import read_business
from .strategy_runtime_projection import project_strategy
from .observer_strategy_details import _execution_lifecycle
from .account_publication import observe_published_account
from .contracts.live_strategy import LiveResponse

SCHEMA = 'guanheng.live-strategy-performance.v1'
MAX_DEALS = 2000  # 单次展示窗口的成交条数；超出显式标partial，原历史不删除。
SHANGHAI = ZoneInfo('Asia/Shanghai')
DAY_BYTES = 16384  # 已核八ETF持仓加金额/状态的单日展示副本；成交逐条独立存储。
DEAL_BYTES = 4096  # 单条白名单成交副本的最大JSON字节数，禁止读库放大。


def _check(deadline):
    if monotonic() >= deadline: raise TimeoutError('live observation deadline')


def _json(value):
    return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False)


def _sha(value):
    return hashlib.sha256(_json(value).encode('ascii')).hexdigest()


def _stamp(value):
    if type(value) is not str or len(value)>64: raise ValueError('live observation time')
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.utcoffset() is None or stamp>datetime.now(timezone.utc): raise ValueError('live observation time')
    return stamp.astimezone(timezone.utc).isoformat()


def _day(value):
    return datetime.fromisoformat(_stamp(value)).astimezone(SHANGHAI).date().isoformat()


def _amount(value):
    if type(value) not in (str,int,float) or type(value) is bool: raise ValueError('live amount')
    text=str(value)
    if len(text)>128: raise ValueError('live amount')
    decimal=Decimal(text)
    if (not decimal.is_finite() or abs(decimal)>Decimal('9007199254740991')
            or decimal.as_tuple().exponent < -64): raise ValueError('live amount')
    return format(decimal,'f')


def _process_running(pid, started_at):
    """只读Win32查询；原生命周期时间排除复用PID，未知/拒绝访问保持None。"""
    if os.name!='nt' or type(pid)is not int or not 0<pid<2**32 or not started_at: return None
    import ctypes
    from ctypes import wintypes
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);api.OpenProcess.restype=wintypes.HANDLE
    api.WaitForSingleObject.argtypes=(wintypes.HANDLE,wintypes.DWORD);api.WaitForSingleObject.restype=wintypes.DWORD
    api.GetProcessTimes.argtypes=(wintypes.HANDLE,)+(ctypes.POINTER(wintypes.FILETIME),)*4
    api.GetProcessTimes.restype=wintypes.BOOL;api.CloseHandle.argtypes=(wintypes.HANDLE,);api.CloseHandle.restype=wintypes.BOOL
    handle=api.OpenProcess(0x100000|0x1000,False,pid)
    if not handle: return False if ctypes.get_last_error()==87 else None
    try:
        status=api.WaitForSingleObject(handle,0)
        if status==0: return False
        if status!=258: return None
        times=[wintypes.FILETIME()for _ in range(4)]
        if not api.GetProcessTimes(handle,*(ctypes.byref(t)for t in times)): return None
        created=((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)/10000000-11644473600
        # 原started事件发生在进程创建之后；新复用进程的创建时间晚于旧事件。
        return created<=datetime.fromisoformat(_stamp(started_at)).timestamp()
    finally:
        api.CloseHandle(handle)


def _blank(day):
    return dict(date=day,observed_at=None,nav_cny=None,cash_cny=None,market_value_cny=None,
        pnl_cny=None,return_pct=None,runtime_scope_id=None,positions=[],deals=[],positions_state='unavailable',deals_state='unavailable')


def _stored_day(raw):
    if type(raw)is not str or len(raw.encode('utf8'))>DAY_BYTES:raise ValueError('live day capacity')
    row=json.loads(raw)
    if (type(row)is not dict or set(row)-set(_blank(''))-{'positions_observed_at','positions_runtime_scope_id','price_observed_at','pnl_source'} or set(_blank(''))-set(row)
            or date.fromisoformat(row['date']).isoformat()!=row['date'] or row['return_pct'] is not None
            or row['deals']!=[] or row['positions_state']not in ('available','empty','unavailable')
            or row['deals_state']not in ('available','empty','partial','unavailable')
            or type(row['positions'])is not list or len(row['positions'])>8):raise ValueError('live stored day')
    for key in ('nav_cny','cash_cny','market_value_cny','pnl_cny'):
        if row[key] is not None:
            if type(row[key])is not str:raise ValueError('live stored amount')
            _amount(row[key])
    if row['observed_at'] is not None and _day(row['observed_at'])!=row['date']:raise ValueError('live stored nav day')
    for position in row['positions']:
        if (type(position)is not dict or set(position)!={'symbol','quantity','sellable','observed_at'}
                or not re.fullmatch(r'[0-9]{6}\.(SH|SZ)',position['symbol'])
                or any(type(position[k])is not int or not 0<=position[k]<=9007199254740991 for k in ('quantity','sellable'))
                or position['sellable']>position['quantity'] or _day(position['observed_at'])!=row['date']):
            raise ValueError('live stored position')
    return row


def _stored_deal(raw):
    if type(raw)is not str or len(raw.encode('utf8'))>DEAL_BYTES:raise ValueError('live deal capacity')
    deal=json.loads(raw)
    if (type(deal)is not dict or set(deal)!={'id','symbol','side','quantity','price_cny','amount_cny','date','time',
            'source_time','observed_at','attribution','runtime_scope_id'} or not re.fullmatch('[a-f0-9]{64}',deal['id'])
            or not re.fullmatch(r'[0-9]{6}\.(SH|SZ)',deal['symbol']) or deal['side']not in ('BUY','SELL','UNKNOWN')
            or type(deal['quantity'])is not int or not 0<deal['quantity']<=9007199254740991
            or deal['attribution']!='account-universe-only' or date.fromisoformat(deal['date']).isoformat()!=deal['date']):
        raise ValueError('live stored deal')
    datetime.fromisoformat(deal['date']+'T'+deal['time'])
    for key in ('price_cny','amount_cny'):
        if type(deal[key])is not str or Decimal(_amount(deal[key]))<0:raise ValueError('live stored deal amount')
    if deal['observed_at']is not None:_stamp(deal['observed_at'])
    return deal


def _symbol(identity):
    code,exchange=identity.get('m_strInstrumentID'),identity.get('m_strExchangeID')
    if type(code)is str and re.fullmatch('[0-9]{6}',code) and exchange in ('SH','SZ'):
        return code+'.'+exchange
    return None


def _field(row,key):
    item=row.get('fields',{}).get(key,{})
    return item.get('value') if item.get('availability')=='present' else None


def _deal_rows(account,symbols,*,identity_scope=None,runtime_scope=None):
    """只复制NAP真实成交，证券重合保持账户范围，缺归属不标策略成交。"""
    if account is None: return [],None,'unavailable'
    group=account.get('groups',{}).get('deal',{})
    if group.get('status')!='complete': return [],None,'unavailable'
    result=[];seen={};partial=False
    observed=group.get('execution_finished_at') or group.get('received_at')
    observed=_stamp(observed) if observed else None
    for row in group.get('rows',[]):
        symbol=_symbol(row.get('identity',{}))
        if symbol not in symbols: continue
        try:
            raw_date=_field(row,'date');raw_time=_field(row,'time')
            if type(raw_date)is not str: raise ValueError('deal date')
            text=raw_date.replace('-','');day=date(int(text[:4]),int(text[4:6]),int(text[6:])).isoformat()
            if len(text)!=8 or date.fromisoformat(day)>datetime.now(SHANGHAI).date(): raise ValueError('deal date')
            if type(raw_time)is not str or not re.fullmatch(r'(?:[0-9]{5,6}|[0-9]{2}:[0-9]{2}:[0-9]{2})',raw_time): raise ValueError('deal time')
            # 原QMT HHMMSS字段的上午时刻可省略小时十位0；只做明确零填充，保留源文本。
            padded=raw_time.zfill(6)
            clock=raw_time if ':'in raw_time else ':'.join((padded[:2],padded[2:4],padded[4:]))
            datetime.fromisoformat(day+'T'+clock)
            traded=datetime.fromisoformat(day+'T'+clock).replace(tzinfo=SHANGHAI)
            if traded>datetime.now(timezone.utc) or observed is None or traded>datetime.fromisoformat(observed):
                raise ValueError('deal beyond original observation')
            quantity=_amount(_field(row,'quantity'));price=_amount(_field(row,'price'));amount=_amount(_field(row,'amount'))
            if Decimal(quantity)<=0 or Decimal(quantity)!=Decimal(quantity).to_integral() or min(Decimal(price),Decimal(amount))<0: raise ValueError('deal values')
            identity=row.get('identity',{});trade_id=identity.get('m_strTradeID') or identity.get('derived_trade_id')
            if type(trade_id)is not str or not trade_id or len(trade_id)>256: raise ValueError('deal identity')
            side={48:'BUY',49:'SELL'}.get(_field(row,'side'),'UNKNOWN')
            deal=dict(id=_sha([identity_scope or account.get('publication',{}).get('scope_id'),trade_id,symbol,day]),
                symbol=symbol,side=side,quantity=int(Decimal(quantity)),price_cny=price,amount_cny=amount,
                date=day,time=clock,source_time=raw_time,observed_at=observed,runtime_scope_id=runtime_scope,attribution='account-universe-only')
            if deal['id'] in seen:
                if seen[deal['id']]!=deal: return [],None,'unavailable'
                continue
            seen[deal['id']]=deal;result.append(deal)
        except (ValueError,TypeError,ArithmeticError): partial=True
    trade_date=account.get('trade_date',{})
    empty_day=None
    if trade_date.get('availability')=='present':
        try:
            raw=str(trade_date['value']).replace('-','');empty_day=date(int(raw[:4]),int(raw[4:6]),int(raw[6:])).isoformat()
            if len(raw)!=8 or date.fromisoformat(empty_day)>datetime.now(SHANGHAI).date(): empty_day=None
        except (KeyError,ValueError,TypeError): pass
    return result,empty_day,'partial' if partial else 'available' if result else 'empty'


def _merge_day(previous,row):
    """单一来源时间归约，持久写入、只读降级和快照展示共用。"""
    merged=dict(previous or _blank(row['date']))
    if row['observed_at'] is not None and (merged['observed_at']is None or row['observed_at']>=merged['observed_at']):
        merged.update({k:row[k]for k in ('observed_at','nav_cny','cash_cny','market_value_cny','pnl_cny','return_pct','runtime_scope_id')})
        for key in ('price_observed_at','pnl_source'):
            if key in row:merged[key]=row[key]
    if row.get('positions_observed_at')is not None and row['positions_observed_at']>=merged.get('positions_observed_at',''):
        merged.update({k:row[k]for k in ('positions','positions_state','positions_observed_at','positions_runtime_scope_id')})
    if row['deals_state']!='unavailable':merged['deals_state']=row['deals_state']
    return merged


def _view(rows,events,limit):
    """统一有界显示；已有历史及本轮真实快照按同一原时钟合并，不写来源。"""
    selected={r['date']:dict(r)for r in rows}
    for day,row in events.items():
        old=selected.get(day);merged=_merge_day(old,row)
        deals={d['id']:d for d in (old or {}).get('deals',[])}
        for deal in row['deals']:
            existing=deals.get(deal['id'])
            if existing is None or (deal.get('observed_at')or'')>(existing.get('observed_at')or''):deals[deal['id']]=deal
        merged['deals']=list(deals.values());selected[day]=merged
    result=[selected[d]for d in sorted(selected)[-limit:]]
    deals=sorted((d for r in result for d in r['deals']),key=lambda d:(d['date'],d['time'],d['id']),reverse=True)
    truncated=len(deals)>MAX_DEALS;shown={d['id']for d in deals[:MAX_DEALS]}
    for row in result:
        original=row['deals'];row['deals']=sorted((d for d in original if d['id']in shown),key=lambda d:(d['time'],d['id']))
        if original and row['deals_state']in ('empty','unavailable'):row['deals_state']='available'
        if len(row['deals'])<len(original):row['deals_state']='partial'
    return result,truncated


class LiveStrategyPerformanceOwner:
    """App拥有展示副本和独占本地租约；原读池线程串行调用，实例不创建线程。"""
    def __init__(self,settings,*,history_root='',snapshot_reader=None,process_probe=None):
        self.settings=settings  # 只使用原WT读取配置及账户来源选择，不读凭据或运行配置。
        self.history_root=history_root  # 已准备个人观察根；空值只提供本轮快照。
        self._read_snapshot=snapshot_reader or self._snapshot  # 单次已核原发布快照，测试可注入事实。
        self._probe=process_probe or _process_running  # 只读OS创建/存活核查，未知保持None。
        self._lock=RLock()  # 本owner采集/查询/关闭序列，持锁等待受调用者绝对截止限制。
        self._lease=None  # 固定本地副本的唯一WindowsLease，close保持实际资源责任。
        self._root=None  # 初始化后固定个人根路径；产品程序目录之外。
        self._root_key=None  # 已核根的设备/inode身份；路径被换根时拒绝沿旧租约读新库。
        self._closed=False  # 关闭后禁止新观察，原运行角色及来源保持。

    def _snapshot(self,deadline):
        configuration=resolve_runtime_configuration(RuntimeObservationConfig.from_settings(self.settings),deadline)
        if configuration is None: return None
        before=read_runtime_snapshot(configuration,deadline).value
        strategies,reference,state=read_business(configuration,deadline)
        if not strategies: return dict(configuration=configuration,runtime=before,reference=reference,strategy=None,account=None,lifecycle={})
        strategy=project_strategy(dict(schema='guanheng.configured-cta-observation.v1',strategies=strategies),runtime_state=state)
        account=None;account_binding=[]
        if self.settings.account_source=='wt_account_publication':
            try: account=observe_published_account(configuration,deadline,binding_observer=lambda binding:
                account_binding.append(_sha(dict(account=binding.account,environment=binding.environment,currency='CNY')))).model_dump(mode='json')
            except (ValueError,OSError,TimeoutError): pass  # 成交来源独立降级；原策略核心事实仍完整验证。
        lifecycle=_execution_lifecycle(reference,deadline)
        after=read_runtime_snapshot(configuration,deadline).value
        if (after['pid']!=before['pid'] or after['components'].get('execution')!=before['components'].get('execution')
                or resolve_runtime_configuration(RuntimeObservationConfig.from_settings(self.settings),deadline)!=configuration):
            raise ValueError('live runtime changed')
        _check(deadline)
        return dict(configuration=configuration,runtime=after,reference=reference,strategy=strategy,account=account,
            account_binding_sha256=account_binding[0]if account_binding else None,lifecycle=lifecycle)

    def _database(self,deadline):
        _check(deadline)
        if not self.history_root: return None
        if self._root is None:
            root=Path(self.history_root)
            if not root.is_absolute(): raise ValueError('live observation root')
            _inspect(root,directory=True)
            if self._lease is None:self._lease=WindowsLease()
            lease=self._lease  # 先登记，部分open失败仍由close负责释放，后续不覆盖其资源引用。
            if not lease.closed:raise RuntimeError('live lease initialization incomplete')
            lock=root/'.live-strategy-observations.lock'
            if os.path.lexists(lock):_inspect(lock)
            try: lease.open(lock,create=True,check=lambda:_check(deadline))
            except FileExistsError: lease.open(lock,create=False,check=lambda:_check(deadline))
            self._root=root
            info=_inspect(root,directory=True);self._root_key=(info.st_dev,info.st_ino)
        info=_inspect(self._root,directory=True)
        if (info.st_dev,info.st_ino)!=self._root_key:raise ValueError('live observation root replaced')
        path=self._root/'live-strategy-observations.sqlite3'
        if path.exists(): _inspect(path)
        database=sqlite3.connect(path,timeout=max(0,deadline-monotonic()))
        database.set_progress_handler(lambda: 1 if monotonic()>=deadline else 0,1000)
        try:
            tables={r[0]for r in database.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if tables-{'observations','deals'}:raise ValueError('live observation database identity')
            database.execute('CREATE TABLE IF NOT EXISTS observations(scope TEXT NOT NULL,day TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(scope,day))')
            database.execute('CREATE TABLE IF NOT EXISTS deals(scope TEXT NOT NULL,id TEXT NOT NULL,day TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(scope,id))')
            database.execute('CREATE INDEX IF NOT EXISTS deals_day ON deals(scope,day,id)')
            database.commit();_check(deadline)
            return database
        except BaseException:
            database.close();raise

    def initialize(self,deadline):
        """App启动读池先准备本地展示库；冷建schema允许调用方提供独立有限启动预算。"""
        self._acquire(deadline)
        try:
            database=self._database(deadline)
            if database is not None:database.close()
        finally:self._lock.release()

    def _project(self,snapshot,deadline):
        if snapshot is None or snapshot['strategy'] is None: return None
        strategy=snapshot['strategy'];runtime=snapshot['runtime'];configuration=snapshot['configuration'];reference=snapshot['reference']
        baseline=strategy.get('capital_baseline');capital=strategy.get('capital')
        scope=_sha([configuration.instance_id,configuration.control_id,configuration.configuration_sha256,
            reference,strategy['strategy_id'],strategy['strategy_version'],baseline])
        anchor=(capital or {}).get('cash_anchor')
        stable=(baseline is not None and type(anchor)is dict and anchor.get('schema')=='guanheng.broker-cash-anchor.v1'
            and (capital or {}).get('pnl_source')=='broker-cash-delta' and anchor.get('baseline_sha256')==_sha(baseline)
            and type(anchor.get('account_binding_sha256'))is str and re.fullmatch('[a-f0-9]{64}',anchor['account_binding_sha256']))
        history_scope=(_sha(['published-cash-anchor-history-v1',configuration.instance_id,strategy['strategy_id'],
            strategy['strategy_version'],_sha(baseline),_sha(anchor)])if stable else scope)
        execution=runtime['components'].get('execution',{})
        started=snapshot['lifecycle'].get('execution_started_at')
        execution_active=self._probe(reference['pid'],started) if reference else None
        runtime_active=self._probe(runtime.get('pid'),started)
        active=(False if execution_active is False or runtime_active is False else
            True if execution_active is True and runtime_active is True else None)
        is_current=(runtime['state']=='ready' and runtime['ready'] is True and execution.get('state')=='ready'
            and execution.get('ready')is True and active is True and not snapshot['lifecycle'].get('execution_finished_at'))
        current=dict(strategy_id=strategy['strategy_id'],strategy_version=strategy['strategy_version'],key_matches=True,
            runtime_state=runtime['state'],is_current=is_current,scope_id=scope,process_state='alive' if active is True else 'exited' if active is False else 'unknown')
        events={};summary=None
        if capital is not None:
            stamp=_stamp(capital['observed_at']);row=events.setdefault(_day(stamp),_blank(_day(stamp)))
            row.update(observed_at=stamp,nav_cny=capital['nav_cny'],cash_cny=capital['cash_balance_cny'],
                market_value_cny=capital['market_value_cny'],pnl_cny=capital['native_pnl_cny'],runtime_scope_id=scope,
                price_observed_at=capital.get('price_observed_at'),pnl_source=capital.get('pnl_source','native-theoretical'))
            summary=dict(nav_cny=capital['nav_cny'],pnl_cny=capital['native_pnl_cny'],return_pct=None,observed_at=stamp,
                price_observed_at=capital.get('price_observed_at'),pnl_source=capital.get('pnl_source','native-theoretical'),
                return_reason='缺少连续策略资金流及独立归因，收益率保持未知。')
        positions=[dict(symbol=p['symbol'],quantity=p['broker_quantity'],sellable=p['broker_sellable'],
            observed_at=strategy['broker_observed_at'])for p in strategy['positions'] if p['broker_quantity']is not None]
        if strategy.get('broker_observed_at') is not None and all(p['broker_quantity']is not None for p in strategy['positions']):
            stamp=_stamp(strategy['broker_observed_at']);row=events.setdefault(_day(stamp),_blank(_day(stamp)))
            row.update(positions=positions,positions_state='available' if any(p['quantity']for p in positions)else'empty',
                positions_observed_at=stamp,positions_runtime_scope_id=scope)
        account=snapshot['account'];binding=snapshot.get('account_binding_sha256')
        # 跨正常代历史只接受与现金原点一致的已核NAP账户；缺证明保留资金/持仓并单独缺成交。
        if stable and binding!=anchor['account_binding_sha256']:account=None
        deals,empty_day,deals_state=_deal_rows(account,{p['symbol']for p in strategy['positions']},
            identity_scope=history_scope if stable else None,runtime_scope=scope)
        for deal in deals:
            row=events.setdefault(deal['date'],_blank(deal['date']));row['deals_state']=deals_state
            row['deals'].append(deal)
        if empty_day:
            events.setdefault(empty_day,_blank(empty_day))['deals_state']=deals_state
        _check(deadline)
        return dict(current=current,history_scope_id=history_scope,continuity='stable-cash-anchor'if stable else'runtime-only-unproven-lineage',
            baseline=None if baseline is None else dict(total_cny=baseline['total_cny'],
            baseline_at=baseline['baseline_at'],scope_id=_sha(baseline)),summary=summary,events=events)

    def _record(self,projected,deadline,limit):
        events=projected['events'];scope=projected['history_scope_id']
        database=self._database(deadline)
        if database is None:
            rows,truncated=_view([],events,limit)
            return rows,'snapshot-only',truncated
        with closing(database):
            state='app-published-observation-history'
            try:
                with database:
                    for day,row in events.items():
                        _check(deadline)
                        previous=database.execute('SELECT CASE WHEN length(payload)<=? THEN payload ELSE NULL END FROM observations WHERE scope=? AND day=?',(DAY_BYTES,scope,day)).fetchone()
                        merged=_merge_day(_stored_day(previous[0])if previous else None,row)
                        for deal in row['deals']:
                            raw=_json(deal);_stored_deal(raw)
                            database.execute("INSERT INTO deals VALUES(?,?,?,?) ON CONFLICT(scope,id) DO UPDATE SET payload=excluded.payload WHERE json_extract(excluded.payload,'$.observed_at')>json_extract(deals.payload,'$.observed_at')",
                                (scope,deal['id'],day,raw))
                        merged['deals']=[]
                        raw=_json(merged);_stored_day(raw)
                        database.execute('INSERT INTO observations VALUES(?,?,?) ON CONFLICT(scope,day) DO UPDATE SET payload=excluded.payload',
                            (scope,day,raw))
                    _check(deadline)
            except sqlite3.OperationalError as error:
                _check(deadline)
                # 只降级明确存储写入/容量/锁错误；取消、总D、格式/身份错误继续失败。
                code=getattr(error,'sqlite_errorcode',0)&255
                if code not in (sqlite3.SQLITE_READONLY,sqlite3.SQLITE_FULL,sqlite3.SQLITE_IOERR,
                        sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED,sqlite3.SQLITE_PERM):raise
                state='degraded-readonly-history'
            rows=self._history(database,scope,limit,deadline)
            rows,truncated=_view(rows,events if state=='degraded-readonly-history'else{},limit)
            _check(deadline)
            return rows,state,truncated

    def _history(self,database,scope,limit,deadline):
        """按经济scope读取已核副本；写入降级不更换原租约/身份或绕过格式验证。"""
        _check(deadline)
        values=database.execute('SELECT CASE WHEN length(payload)<=? THEN payload ELSE NULL END FROM observations WHERE scope=? ORDER BY day DESC LIMIT ?',(DAY_BYTES,scope,limit)).fetchall()
        rows=[_stored_day(item[0])for item in reversed(values)];selected={r['date']:r for r in rows}
        deals=database.execute('SELECT CASE WHEN length(payload)<=? THEN payload ELSE NULL END FROM deals WHERE scope=? AND day>=? ORDER BY day DESC,id LIMIT ?',
            (DEAL_BYTES,scope,rows[0]['date']if rows else'9999-12-31',MAX_DEALS+1)).fetchall()
        for (raw,)in deals:
            deal=_stored_deal(raw)
            if deal['date']in selected:selected[deal['date']]['deals'].append(deal)
        _check(deadline);return rows

    def _acquire(self,deadline):
        _check(deadline)
        if not self._lock.acquire(timeout=max(0,deadline-monotonic())): raise TimeoutError('live owner busy')
        if self._closed:
            self._lock.release();raise RuntimeError('live owner closed')

    def capture_current(self,deadline):
        """原App读池的同步观察入口；无新来源请求，失败由调用者保留上次完整副本。"""
        self._acquire(deadline)
        try:
            projected=self._project(self._read_snapshot(deadline),deadline)
            if projected is None:return dict(state='waiting')
            rows,state,truncated=self._record(projected,deadline,1)
            return dict(state='degraded'if state=='degraded-readonly-history'else'recorded',
                scope_id=projected['current']['scope_id'],history_state=state)
        finally:self._lock.release()

    def read(self,strategy_id,strategy_version,limit=90,*,deadline) -> LiveResponse:
        """按完整策略key读取同scope日观察；limit单位日，原读池的同一绝对D约束所有IO。"""
        if (any(type(s)is not str or not re.fullmatch(r'[A-Za-z0-9_.+@-]{1,64}',s)for s in (strategy_id,strategy_version))
                or type(limit)is not int or not 1<=limit<=366):raise ValueError('live selection')
        self._acquire(deadline)
        try:
            requested=dict(strategy_id=strategy_id,strategy_version=strategy_version)
            projected=self._project(self._read_snapshot(deadline),deadline)
            current=dict(**requested,key_matches=False,runtime_state=None,is_current=False,scope_id=None,process_state='unknown')
            body=dict(schema_version=SCHEMA,read_only=True,observed_at=datetime.now(timezone.utc).isoformat(),
                state='waiting',reason='尚未取得此策略的实际发布观察。',requested=requested,current=current,
                coverage=dict(**{'from':None,'to':None},point_count=0,basis='actual-published-observations',
                    history_state='unavailable',history_scope_id=None,continuity='unproven',
                    reason='缺少连续历史；不会补造过去净值。',deals_truncated=False),
                baseline=None,summary=None,daily=[],markers=[])
            if projected is None:return body
            if any(projected['current'][k]!=v for k,v in requested.items()):
                body.update(state='not_current',reason='所选策略版本与当前WT发布身份不匹配。');return body
            rows,history,truncated=self._record(projected,deadline,limit)
            points=[r for r in rows if r['nav_cny']is not None]
            summary=projected['summary']
            if points:
                latest=max(points,key=lambda r:r['observed_at'])
                if summary is None or latest['observed_at']>=summary['observed_at']:
                    summary=dict(nav_cny=latest['nav_cny'],pnl_cny=latest['pnl_cny'],return_pct=None,
                        observed_at=latest['observed_at'],price_observed_at=latest.get('price_observed_at'),
                        pnl_source=latest.get('pnl_source','native-theoretical'),
                        return_reason='缺少连续策略资金流及独立归因，收益率保持未知。')
            body.update(state='available',reason='WT实际资金观察；成交属于账户及所选证券范围，策略归属未确认。',
                current=projected['current'],baseline=projected['baseline'],summary=summary,daily=rows,
                markers=[{k:d[k]for k in ('id','date','time','symbol','side','price_cny','quantity','attribution')}for row in rows for d in row['deals']],
                coverage=dict(**{'from':points[0]['date']if points else None,'to':points[-1]['date']if points else None},
                    point_count=len(points),basis='actual-published-observations',history_state=history,
                    history_scope_id=projected['history_scope_id'],continuity=projected['continuity'],
                    reason=('历史保存本轮失败，当前为已核旧历史与真实来源快照，尚未保存本轮。'if history=='degraded-readonly-history'else
                        '仅含App实际观察到的来源日期；缺日和过去净值保持缺失，收益率归因尚未具备。')
                        +(' 缺少稳定金融现金原点，历史限本运行代。'if projected['continuity']=='runtime-only-unproven-lineage'else''),
                    deals_truncated=truncated))
            return body
        finally:self._lock.release()

    def close(self):
        """由App在读池回收后调用；只关闭本地准入/租约，不触碰原WT或账户owner。"""
        with self._lock:
            self._closed=True
            if self._lease is not None:
                self._lease.close()
                if self._lease.closed:self._lease=None
