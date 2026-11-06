"""原SQLite维护→版本采用→新绑定恢复；合成账户及SDK替身，没有网络/真实委托。"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import hashlib,json,sqlite3,time
import pytest
from guanheng_qmt_shm_agent.protocol import canonical,decode
from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
from guanheng_qmt_shm_agent.trading_kernel import TradingKernel
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm.trading_journal import HostTradingJournal
from guanheng_qmt_shm.trade_binding_maintenance import open_binding_extension_owner
from guanheng_qmt_shm.trade_binding_extension import VERSION,_profile
from guanheng_qmt_shm.trade_event_records import CONTINUITY_VERSION
from guanheng_qmt_shm.journal import JournalConflict
from test_trade_bootstrap import agent_config
from test_trade_service import command
from test_trading_journal import result

OLD='510300.SH';NEW='159352.SZ';EXTRA='588120.SH';SHA='a'*64

def end():return time.monotonic()+10

def make(tmp_path):
    cfg=agent_config();cfg['operation_profiles']['account.trade_detail']['policy_version']='2.0';cfg['trade_binding']['max_commands']=64
    rule=dict(price_tick='0.001',buy_min=100,buy_step=100,sell_min=100,sell_step=100)
    cfg['trade_binding']['symbol_rules']={OLD:dict(rule),EXTRA:dict(rule)}
    cfg['trade_profile']['limits']['max_commands']=64;cfg['trade_profile']['binding_sha256']=hashlib.sha256(canonical(cfg['trade_binding'])).hexdigest()
    admitted=validate_trade_configuration(cfg)
    kw=dict(max_records=32,max_result_bytes=16384,max_request_bytes=8192,max_journal_bytes=32*(8192+16384+16384),trade_binding=admitted.trade_binding,
        max_trade_commands=64,max_trade_bytes=4_000_000,max_trade_result_bytes=admitted.profile['trade_profile']['limits']['max_call_result_bytes'],
        read_profile=admitted.profile,event_storage=dict(max_streams=4,max_events=32,max_bytes=60000,max_page_bytes=4096),connection_continuity=CONTINUITY_VERSION)
    path=tmp_path/'original.sqlite';route=cfg['route'];return path,route,kw

def source(route,profile,generation='a'):
    return host_binding(route=route,generation=generation*32,host_instance_id='b'*32,journal_generation=None,observation_identity=None,capability_sha256=hashlib.sha256(canonical(profile)).hexdigest(),schema_version='2.0')

def successor(kw,*,sell=True):
    new=deepcopy(kw['trade_binding']);new['symbol_rules'][NEW]=dict(price_tick='0.001',buy_min=100,buy_step=100,sell_min=1,sell_step=1)
    changes={}
    if sell:
        old=deepcopy(new['symbol_rules'][OLD]);new['symbol_rules'][OLD].update(sell_min=1,sell_step=1)
        changes[OLD]=dict(before=old,after=deepcopy(new['symbol_rules'][OLD]),security_type='ETF',security_reference_sha256='c'*64)
    return new,changes

def seed(owner,route,kw,count=1):
    b=source(route,kw['read_profile']);records=[]
    for n in range(1,count+1):
        c=command(n);c.update(symbol=OLD,limit_price='10.01')
        owner.submit_trade(canonical(c),b,ttl_ms=300000,deadline=end());owner.claim_trade(b,deadline=end())
        r=result(c,stage='definitely_not_called',sdk_entered=False,signal_sent=None,error_code='not_admitted')
        records.append(owner.finish_trade(c['command_id'],r,b,deadline=end()))
    return records

def maintain(path,route,kw):return open_binding_extension_owner(path,route,deadline=end(),**kw)

def test_56_original_commands_preserved_and_new_kernel_scope(tmp_path):
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw);records=seed(owner,route,kw,56);owner.close()
    owner=maintain(path,route,kw)
    try:
        new,changes=successor(kw);plan=owner.prepare_binding_extension(new,SHA,changes,deadline=end())
        assert owner.get_trade(records[0]['command_id'],deadline=end())==records[0]
        receipt=owner.adopt_binding_extension(plan,deadline=end());assert receipt['version']==2
        assert owner.adopt_binding_extension(plan,deadline=end())==receipt
    finally:owner.close()
    newer=dict(kw,trade_binding=new,read_profile=_profile(kw['read_profile'],new,kw['max_result_bytes']),trade_binding_extension=VERSION)
    owner=HostTradingJournal(path,route,**newer)
    try:
        assert all(owner.get_trade(r['command_id'],deadline=end())==r for r in records)
        assert owner.trade_binding['symbol_rules'][EXTRA]==kw['trade_binding']['symbol_rules'][EXTRA]
        c=command(57);c.update(symbol=NEW,limit_price='10.01');saved=owner.submit_trade(canonical(c),source(route,newer['read_profile'],'c'),ttl_ms=1000,deadline=end());assert saved['body']==canonical(c)
    finally:owner.close()
    calls=[];kernel=TradingKernel(object(),binding=new,passorder=lambda *a:calls.append(a),cancel=lambda *a:False,clock=time.monotonic,writes_enabled=True)
    c=command(58);c.update(symbol=NEW,side='sell',quantity=99,limit_price='10.01')
    assert kernel.execute(c,deadline=end(),phase='live_drain')['stage']=='sdk_returned' and len(calls)==1
    c=command(59);c.update(symbol=NEW,side='buy',quantity=99,limit_price='10.01')
    assert kernel.execute(c,deadline=end(),phase='live_drain')['error_code']=='quantity_off_grid' and len(calls)==1

@pytest.mark.parametrize('kind',['account','shrink','unauthorized_rule','buy_grid','wrong_evidence'])
def test_bad_successor_rejected_without_original_change(tmp_path,kind):
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw);saved=seed(owner,route,kw);owner.close();owner=maintain(path,route,kw)
    try:
        new,changes=successor(kw)
        if kind=='account':new['account_id']='OTHER'
        elif kind=='shrink':new['symbol_rules'].pop(EXTRA)
        elif kind=='unauthorized_rule':changes={}
        elif kind=='buy_grid':new['symbol_rules'][OLD]['buy_min']=1;changes[OLD]['after']=deepcopy(new['symbol_rules'][OLD])
        else:changes[OLD]['security_type']='stock'
        with pytest.raises((JournalConflict,ValueError)):owner.prepare_binding_extension(new,SHA,changes,deadline=end())
        assert owner.get_trade(saved[0]['command_id'],deadline=end())==saved[0]
    finally:owner.close()

def test_changed_facts_and_stale_configuration_rejected(tmp_path):
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw);saved=seed(owner,route,kw);owner.close();owner=maintain(path,route,kw)
    try:
        new,changes=successor(kw);plan=owner.prepare_binding_extension(new,SHA,changes,deadline=end())
        with owner._transaction(end())as db:db.execute("UPDATE trade_commands SET queued_at=queued_at+1")
        with pytest.raises(JournalConflict):owner.adopt_binding_extension(plan,deadline=end())
    finally:owner.close()
    owner=maintain(path,route,kw)
    try:
        plan=owner.prepare_binding_extension(new,SHA,changes,deadline=end());owner.adopt_binding_extension(plan,deadline=end())
    finally:owner.close()
    for extra in ({},{'trade_binding_extension':VERSION}):
        with pytest.raises(JournalConflict):HostTradingJournal(path,route,**dict(kw,**extra))


def test_original_event_source_and_http_ticket_remain_exact_after_adoption(tmp_path):
    from guanheng_qmt_shm.read_retention_journal import HttpRetainedTradingJournal
    from guanheng_qmt_shm_agent.read_retention import TICKET,content_id
    from guanheng_qmt_shm_agent.read_capabilities import ACCOUNT
    from guanheng_qmt_shm_agent.results import finalize_result
    from test_trade_capabilities import request
    clock=SimpleNamespace(seconds=lambda:100.)
    capability=dict(schema='qmt.read-retention.v1',max_lifetime_ms=1000)
    path,route,kw=make(tmp_path);kw['clock']=time.monotonic
    owner=HttpRetainedTradingJournal(path,route,http_retention=capability,retention_clock=clock,**kw)
    old=source(route,kw['read_profile']);session=dict(host_binding=old,session_id='original-source')
    value=request(ACCOUNT);value['policy_version']='2.0';value['correlation_id']=str(uuid4());ticket=dict(schema=TICKET,epoch=old['host_instance_id'],expires_ms=101000)
    value['request_id']=content_id(value,ticket);raw=canonical(value)
    owner.submit_ticket(raw,old,ticket,queue_timeout_ms=1000,deadline=end());owner.claim_bound(old,deadline=end())
    answer=finalize_result(dict(request_id=value['request_id'],operation_id=ACCOUNT,completed_at='2026-11-06T00:00:00Z',ok=False,error_code='capability_unavailable',error_message='synthetic'),kw['max_result_bytes'])
    owner.finish_bound(value['request_id'],answer,old,deadline=end());saved_read=owner.get_bound(value['request_id'],deadline=end())
    page=dict(schema_version='qmt.trade-event-page.v1',session_id='original-source',binding_id=kw['trade_binding']['binding_id'],acknowledged_through=0,published_through=1,gap=None,
        events=[dict(schema_version='qmt.trade-event.v1',session_id='original-source',binding_id=kw['trade_binding']['binding_id'],sequence=1,kind='error',payload=dict(order_args={'accountID':'SYNTHETIC'},err_msg='synthetic'))])
    owner.events.ingest(session,canonical(page),after_seq=0,limit=16,max_bytes=4096,deadline=end())
    saved_event=owner.events.read(session,after_seq=0,limit=16,max_bytes=4096,deadline=end());owner.close()
    owner=open_binding_extension_owner(path,route,deadline=end(),retention_clock=clock,http_retention=capability,**kw)
    try:
        new,changes=successor(kw);plan=owner.prepare_binding_extension(new,SHA,changes,deadline=end());owner.adopt_binding_extension(plan,deadline=end())
    finally:owner.close()
    owner=HttpRetainedTradingJournal(path,route,http_retention=capability,retention_clock=clock,**dict(kw,trade_binding=new,read_profile=_profile(kw['read_profile'],new,kw['max_result_bytes']),trade_binding_extension=VERSION))
    try:
        assert owner.get_bound(value['request_id'],deadline=end())==saved_read
        assert owner.events.read(session,after_seq=0,limit=16,max_bytes=4096,deadline=end())==saved_event
        with pytest.raises(JournalConflict):owner.events.ingest(session,canonical(page),after_seq=0,limit=16,max_bytes=4096,deadline=end())
        assert owner._historical_read_profile_matches(old)
    finally:owner.close()


def test_inflight_and_unresolved_unknown_keep_original_identity(tmp_path):
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw)
    c=command(1);c.update(symbol=OLD);actual=source(route,kw['read_profile'])
    owner.submit_trade(canonical(c),actual,ttl_ms=300000,deadline=end());owner.claim_trade(actual,deadline=end());before=owner.get_trade(c['command_id'],deadline=end());owner.close()
    with pytest.raises(JournalConflict):maintain(path,route,kw)
    with sqlite3.connect(path)as db:assert db.execute('SELECT state FROM trade_commands').fetchone()[0]=='dispatching'
    # 普通原owner沿原规则恢复为unknown；维护不执行这一步，也不重派UUID。
    owner=HostTradingJournal(path,route,**kw);unknown=owner.get_trade(c['command_id'],deadline=end());assert unknown['state']=='unknown';owner.close()
    owner=maintain(path,route,kw)
    try:
        new,changes=successor(kw);plan=owner.prepare_binding_extension(new,SHA,changes,deadline=end());owner.adopt_binding_extension(plan,deadline=end())
        assert owner.get_trade(c['command_id'],deadline=end())==unknown
    finally:owner.close()
    owner=HostTradingJournal(path,route,**dict(kw,trade_binding=new,read_profile=_profile(kw['read_profile'],new,kw['max_result_bytes']),trade_binding_extension=VERSION))
    try:
        assert owner.get_trade(c['command_id'],deadline=end())==unknown and owner.trade_admission(deadline=end())['unknown_fenced']
        fresh=command(3);fresh.update(symbol=NEW)
        with pytest.raises(JournalConflict,match='admission closed'):owner.submit_trade(canonical(fresh),source(route,owner.admission_profile,'c'),ttl_ms=1000,deadline=end())
        assert owner.claim_trade(source(route,owner.admission_profile,'c'),deadline=end())is None
    finally:owner.close()


def test_unknown_resolved_by_original_order_query_and_proof_survives_version(tmp_path):
    from guanheng_qmt_shm_agent.account_query import AccountQueryAdapter
    from guanheng_qmt_shm_agent.results import finalize_result
    from test_trade_account_projection import query,NOW
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw);actual=source(route,kw['read_profile'])
    c=command(1);c.update(symbol=OLD);owner.submit_trade(canonical(c),actual,ttl_ms=300000,deadline=end());owner.claim_trade(actual,deadline=end())
    owner.finish_trade(c['command_id'],result(c,stage='unknown',sdk_entered=True,signal_sent=None,error_code='sdk_exception'),actual,deadline=end())
    row=dict(m_strAccountID='SYNTHETIC',m_strInstrumentID='510300',m_strExchangeID='SH',m_strRemark=c['sdk_user_order_id'],m_strOrderSysID='original-broker',
        m_strOrderRef='ref',m_strInsertDate='20261106',m_strInsertTime='09:30:00',m_nVolumeTotalOriginal=100,m_nVolumeTraded=100,m_nVolumeTotal=0,m_nOrderStatus=56,m_nOffsetFlag=48,m_dLimitPrice=10.01)
    request=query('order');request['request_id']=str(uuid4());limits=kw['read_profile']['operation_profiles']['account.trade_detail']['limits']
    adapter=AccountQueryAdapter(lambda *a:[row],limits,16384,clock=lambda:0,utc_now=lambda:NOW,projection_version=2)
    answer=finalize_result(dict(request_id=request['request_id'],operation_id='account.trade_detail',ok=True,completed_at=NOW.isoformat().replace('+00:00','Z'),data=adapter.execute(request['arguments'],10)),16384)
    rid=owner.submit_bound(canonical(request),actual,queue_timeout_ms=1000,deadline=end());owner.claim_bound(actual,deadline=end());owner.finish_bound(rid,answer,actual,deadline=end())
    saved=owner.get_trade(c['command_id'],deadline=end());assert saved['state']=='unknown' and not owner.trade_admission(deadline=end())['unknown_fenced'];owner.close()
    owner=maintain(path,route,kw)
    try:
        new,changes=successor(kw);plan=owner.prepare_binding_extension(new,SHA,changes,deadline=end());owner.adopt_binding_extension(plan,deadline=end())
    finally:owner.close()
    owner=HostTradingJournal(path,route,**dict(kw,trade_binding=new,read_profile=_profile(kw['read_profile'],new,kw['max_result_bytes']),trade_binding_extension=VERSION))
    try:
        assert owner.get_trade(c['command_id'],deadline=end())==saved and not owner.trade_admission(deadline=end())['unknown_fenced']
    finally:owner.close()


def test_owner_lease_and_expired_deadline_do_not_create_scope_metadata(tmp_path):
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw)
    try:
        with pytest.raises((JournalConflict,OSError)):maintain(path,route,kw)
    finally:owner.close()
    owner=maintain(path,route,kw)
    try:
        new,changes=successor(kw)
        with pytest.raises(TimeoutError):owner.prepare_binding_extension(new,SHA,changes,deadline=time.monotonic()-1)
        with owner._transaction(end())as db:assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='trade_binding_versions'").fetchone()
    finally:owner.close()


def test_adopt_commit_late_reopens_committed_version_without_rewriting_commands(tmp_path,monkeypatch):
    from test_trading_journal import journal_connection_scope
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw);saved=seed(owner,route,kw);owner.close();owner=maintain(path,route,kw)
    new,changes=successor(kw);plan=owner.prepare_binding_extension(new,SHA,changes,deadline=end())
    real=time.monotonic;offset=[0.]
    class Connection:
        def __init__(self,db):self.db=db
        def __getattr__(self,key):return getattr(self.db,key)
        def commit(self):self.db.commit();offset[0]=100.
    try:
        with monkeypatch.context()as patch:
            patch.setattr(time,'monotonic',lambda:real()+offset[0])
            with journal_connection_scope(Connection),pytest.raises(TimeoutError):owner.adopt_binding_extension(plan,deadline=real()+5)
        assert owner._trade_failed
    finally:owner.close(deadline=end())
    newer=dict(kw,trade_binding=new,read_profile=_profile(kw['read_profile'],new,kw['max_result_bytes']))
    owner=maintain(path,route,newer)
    try:
        receipt=owner.adopt_binding_extension(plan,deadline=end());assert receipt['version']==2
        assert owner.get_trade(saved[0]['command_id'],deadline=end())==saved[0]
    finally:owner.close()


def test_current_sha_corruption_rejected_and_bad_plan_bool_never_adopted(tmp_path):
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw);owner.close();owner=maintain(path,route,kw)
    new,changes=successor(kw);plan=owner.prepare_binding_extension(new,SHA,changes,deadline=end())
    bad=deepcopy(plan);bad['expected_version']=True;bad.pop('plan_sha256');bad['plan_sha256']=hashlib.sha256(canonical(bad)).hexdigest()
    try:
        with pytest.raises(JournalConflict):owner.adopt_binding_extension(bad,deadline=end())
        owner.adopt_binding_extension(plan,deadline=end())
    finally:owner.close()
    with sqlite3.connect(path)as db:db.execute("UPDATE trade_binding_current SET sha256=?",('0'*64,))
    with pytest.raises(JournalConflict):HostTradingJournal(path,route,**dict(kw,trade_binding=new,read_profile=_profile(kw['read_profile'],new,kw['max_result_bytes']),trade_binding_extension=VERSION))


def test_maintenance_cannot_submit_new_trade_but_old_records_query(tmp_path):
    path,route,kw=make(tmp_path);owner=HostTradingJournal(path,route,**kw);saved=seed(owner,route,kw);owner.close();owner=maintain(path,route,kw)
    try:
        assert owner.get_trade(saved[0]['command_id'],deadline=end())==saved[0]
        c=command(2);c.update(symbol=OLD)
        with pytest.raises(JournalConflict,match='maintenance'):owner.submit_trade(canonical(c),source(route,kw['read_profile']),ttl_ms=1000,deadline=end())
    finally:owner.close()
