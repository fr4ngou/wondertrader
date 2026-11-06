"""原HostTradingJournal的绑定版本值；不拥有连接、线程、队列或SDK。"""
from contextlib import contextmanager
from guanheng_qmt_shm_agent.protocol import canonical,decode
from guanheng_qmt_shm_agent.trading_contract import validate_trade_binding
from guanheng_qmt_shm_agent.read_capabilities import validate_read_profile
from guanheng_qmt_shm_agent.trade_capabilities import validate_trade_profile_binding
from .bound import digest,sha256_text
from .journal import JournalConflict,JournalFull,HostReadJournal
from .trade_event_records import validate_trade_event_storage

VERSION='qmt.trade-binding-extension.v1'
TABLES=frozenset(('trade_binding_versions','trade_binding_current'))
_FIELDS={
    'schema_version',  # 持久绑定扩展协议版本；不改变私有wire binding.v1。
    'version',  # 同一原Journal的连续版本号，从创世1开始。
    'parent_sha256',  # 前版完整规范记录SHA；创世为None。
    'identity',  # 原绑定及原交易资源预算全文，包含私有账户信息，仅存受控Journal。
    'profile',  # 此版完整已准入来源profile，旧B按其摘要核历史事实。
    'event_identity',  # 此版期望事件身份；没有事件owner时为None，原创世表不重写。
    'retention_identity',  # 原读票据创世身份；未选择票据能力时为None。
    'authorization_sha256',  # 本次受控授权原件SHA；创世无新增授权，保持None。
    'symbol_additions',  # 此版明确新增证券列表，原许可证券始终保留。
    'rule_changes',  # 逐证券before/after及ETF合同证据SHA，不推断账户可卖数量。
    'protected_facts_sha256',  # 采用时全部原表及原字节的有序摘要，不含本扩展两张表。
    'plan_sha256',  # 本次prepare规范计划SHA；创世为None，重试沿同计划识别。
}
_PLAN_FIELDS={
    'schema_version',  # 固定prepare计划协议，不是Agent交易命令。
    'journal_path',  # 当前独占owner已解析的原绝对路径，不能迁移到另一个Journal。
    'expected_version',  # prepare时原current连续版本，供adopt事务CAS。
    'expected_current_sha256',  # 原版本记录SHA；尚未扩展时为原trade_identity SHA。
    'new_identity',  # 后继绑定与不变资源预算，不含新的数据库或队列。
    'new_profile',  # 仅变更trade_profile.binding_sha256的后继来源profile。
    'authorization_sha256',  # 调用者已核受控授权原件SHA。
    'rule_changes',  # 明确授权规则差异，包含before/after与ETF合同证据。
    'symbol_additions',  # 本次严格新增证券，原有额外许可不删除。
    'protected_facts',  # 原schema/表行数/原字节摘要；原文留在原受控存储。
    'plan_sha256',  # 去除此字段后全部规范计划的SHA，篡改后不可采用。
}


def _need(ok):
    if not ok:raise JournalConflict('trade binding extension identity or facts differ')


def _delta(before,after,changes):
    """只核明确授权的ETF规则差异；实际可卖与订单仍由原金融owner负责。"""
    old,new=validate_trade_binding(before),validate_trade_binding(after)
    _need({k:v for k,v in old.items() if k!='symbol_rules'}=={k:v for k,v in new.items() if k!='symbol_rules'})
    previous,current=old['symbol_rules'],new['symbol_rules'];_need(set(previous)<set(current))
    _need(type(changes)is dict and set(changes)<=set(previous))
    actual={s for s in previous if previous[s]!=current[s]};_need(actual==set(changes))
    for symbol,item in changes.items():
        _need(type(item)is dict and set(item)=={'before','after','security_type','security_reference_sha256'})
        _need(item['security_type']=='ETF' and item['before']==previous[symbol] and item['after']==current[symbol])
        sha256_text(item['security_reference_sha256'])
        a,b=previous[symbol],current[symbol]
        _need(a['buy_min']==a['buy_step']==b['buy_min']==b['buy_step']==100
              and a['price_tick']==b['price_tick'] and a['sell_min']==a['sell_step']==100
              and b['sell_min']==b['sell_step']==1)
    return sorted(set(current)-set(previous))


def _profile(profile,binding,max_result_bytes):
    old=decode(canonical(profile));_need(old.get('read_profile_version')=='qmt.read-profile.v4')
    old['trade_profile']['binding_sha256']=digest(canonical(binding))
    checked=validate_read_profile(old,max_result_bytes=max_result_bytes)
    validate_trade_profile_binding(checked['trade_profile'],binding)
    return checked


class BindingVersions:
    """仅借用owner授予的db；每版保存完整身份，默认没有扩展或新表。"""
    def __init__(self,owner,version,maintenance):
        _need(version in (None,VERSION) and type(maintenance)is bool and (not maintenance or version==VERSION))
        self.owner,self.version,self.maintenance=owner,version,maintenance
        self.history=[]  # 已验证的创世及后继原件；仅构造期替换，调用方不持其别名。
        self.current=None  # 当前配置严格匹配的版本记录，不是来源会话。
        self.adopted=False  # 本维护owner已切current；必须关闭后用新配置重开。

    @staticmethod
    def present(db):
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        found=tables&TABLES;_need(not found or found==TABLES);return bool(found)

    def _identity(self,binding):
        from .trading_journal import validate_trade_journal_configuration
        return decode(validate_trade_journal_configuration(binding,max_trade_commands=self.owner.max_trade_commands,
            max_trade_bytes=self.owner.max_trade_bytes,max_trade_result_bytes=self.owner.max_trade_result_bytes)[1])

    def read(self,db):
        """逐版核规范原件、父SHA、规则、profile与唯一current；不修改任何表。"""
        if not self.present(db):return [],None
        _need(self.version==VERSION)
        for table,columns in (('trade_binding_versions',{'version','value','sha256'}),('trade_binding_current',{'id','version','sha256'})):
            _need({r[1] for r in db.execute('PRAGMA table_info('+table+')').fetchall()}==columns)
        cursor=db.execute('SELECT version,value,sha256 FROM trade_binding_versions ORDER BY version');rows=[];used=0
        while True:
            self.owner._check_owner_deadline();row=cursor.fetchone()
            if row is None:break
            number,raw,sha=row;_need(type(raw)is bytes and type(number)is int and number==len(rows)+1)
            used+=len(raw)+64
            if used>self.owner.max_trade_bytes:raise JournalFull('trade binding version metadata exceeds explicit budget')
            _need(digest(raw)==sha);value=decode(raw)
            _need(type(value)is dict and set(value)==_FIELDS and canonical(value)==raw and value['schema_version']==VERSION and type(value['version'])is int and value['version']==number)
            identity=self._identity(value['identity']['trade_binding']);_need(identity==value['identity'])
            profile=validate_read_profile(value['profile'],max_result_bytes=self.owner.max_result_bytes)
            _need(profile==_profile(profile,identity['trade_binding'],self.owner.max_result_bytes))
            event=value['event_identity']
            if event is not None:
                _need(self.owner.events is not None)
                _,_,expected,_=validate_trade_event_storage(profile,identity['trade_binding'],self.owner.events.storage,max_result_bytes=self.owner.max_result_bytes)
                # 已有read_retention迁移可保留其之前的事件身份；仅创世允许该明确关系。
                allowed=[decode(expected)]
                if number==1 and 'read_retention'in profile:
                    previous=dict(profile);previous.pop('read_retention')
                    allowed.append(decode(validate_trade_event_storage(previous,identity['trade_binding'],self.owner.events.storage,max_result_bytes=self.owner.max_result_bytes)[2]))
                _need(event in allowed)
            _need(value['retention_identity'] is None or type(value['retention_identity'])is dict)
            sha256_text(value['protected_facts_sha256'])
            if not rows:
                _need(value['parent_sha256']is None and value['authorization_sha256']is None and value['plan_sha256']is None
                      and value['symbol_additions']==[] and value['rule_changes']=={})
            else:
                parent=rows[-1];_need(value['parent_sha256']==parent[1]);sha256_text(value['authorization_sha256']);sha256_text(value['plan_sha256'])
                additions=_delta(parent[0]['identity']['trade_binding'],identity['trade_binding'],value['rule_changes'])
                _need(value['symbol_additions']==additions and profile==_profile(parent[0]['profile'],identity['trade_binding'],self.owner.max_result_bytes))
                _need(value['retention_identity']==rows[0][0]['retention_identity'])
            rows.append((value,sha))
        current=db.execute('SELECT id,version,sha256 FROM trade_binding_current').fetchall()
        _need(rows and len(current)==1 and current[0]==(1,len(rows),rows[-1][1]))
        original=db.execute('SELECT id,value FROM trade_identity').fetchall()
        _need(original==[(1,canonical(rows[0][0]['identity']))])
        return rows,rows[-1]

    def opening(self,db):
        rows,current=self.read(db)
        if current is not None:
            _need(canonical(current[0]['identity'])==self.owner._trade_identity_bytes
                  and canonical(current[0]['profile'])==self.owner._read_profile_bytes)
        self.history,self.current=rows,current

    def trade_identity_matches(self,raw):
        return self.current is not None and raw==canonical(self.history[0][0]['identity'])

    def event_identity_matches(self,raw):
        return self.current is not None and self.history[0][0]['event_identity'] is not None and raw==canonical(self.history[0][0]['event_identity'])

    def retention_identity_matches(self,raw):
        if self.current is None:return False
        original=self.history[0][0]['retention_identity']
        if original is None:return False
        _need(raw==canonical(original))
        expected=decode(self.owner._retention_identity)
        return {k:v for k,v in original.items() if k!='profile'}=={k:v for k,v in expected.items() if k!='profile'} and original['profile']==self.history[0][0]['profile']

    def profile_hashes(self):
        found=set()
        for value,_ in self.history:
            found.add(digest(canonical(value['profile'])))
            if value['event_identity'] is not None:found.add(value['event_identity']['profile_sha256'])
            if 'read_retention'in value['profile']:
                p=dict(value['profile']);p.pop('read_retention');found.add(digest(canonical(p)))
        return found

    def logical_bytes(self,db):
        if self.version is None or not self.present(db):return 0
        return db.execute('SELECT COALESCE(SUM(length(value)+length(sha256)+16),0) FROM trade_binding_versions').fetchone()[0]+96

    def _facts(self,db,deadline):
        from .trade_event_maintenance import _facts
        return _facts(db,deadline,excluded_tables=TABLES)

    def _preserved_responsibilities(self,db,deadline):
        """版本追加不派发交易；原unknown/SDKReturned及其准入围栏保持原义。"""
        from .trading_journal import _COLUMNS
        for row in db.execute('SELECT '+','.join(_COLUMNS)+' FROM trade_commands ORDER BY seq').fetchall():
            HostReadJournal._finish_deadline(deadline);record=self.owner._record(row)
            if record['state']in ('queued','dispatching'):
                raise JournalConflict('binding maintenance would recover an active original command')
        # 原完整ORDER proof仍由原owner验证/保留，缺终态本身不阻止权限元数据追加。
        # 此处不调用任何重派、取消、阶段改写或unknown解除接口。
        self.owner._admission_facts(db)

    def _require_maintenance(self):
        _need(self.version==VERSION and self.maintenance)

    def prepare(self,new_binding,authorization_sha256,rule_changes,*,deadline):
        self._require_maintenance();authorization_sha256=sha256_text(authorization_sha256)
        new=validate_trade_binding(new_binding);changes=decode(canonical(rule_changes))
        additions=_delta(self.owner.trade_binding,new,changes);profile=_profile(self.owner.admission_profile,new,self.owner.max_result_bytes)
        with self.owner._trade_lock(deadline):
            with self.owner._transaction(deadline)as db:
                self._preserved_responsibilities(db,deadline);rows,current=self.read(db)
                _need(current is None or canonical(current[0]['identity'])==self.owner._trade_identity_bytes)
                original=db.execute('SELECT value FROM trade_identity WHERE id=1').fetchone();_need(original is not None)
                protected=self._facts(db,deadline)
                plan=dict(schema_version='qmt.trade-binding-extension-plan.v1',journal_path=str(self.owner.path),expected_version=1 if current is None else current[0]['version'],
                    expected_current_sha256=digest(bytes(original[0])) if current is None else current[1],new_identity=self._identity(new),new_profile=profile,
                    authorization_sha256=authorization_sha256,rule_changes=changes,symbol_additions=additions,protected_facts=protected)
                plan['plan_sha256']=digest(canonical(plan));HostReadJournal._finish_deadline(deadline);return plan

    @contextmanager
    def _adoption(self):
        try:yield
        except BaseException:
            # COMMIT可能已生效；同owner关闭新交易，后继沿同plan/current核查。
            self.owner._fail_trade('binding_extension_adoption_unconfirmed')
            raise

    def adopt(self,plan,*,deadline):
        self._require_maintenance();plan=decode(canonical(plan))
        keys=_PLAN_FIELDS
        _need(type(plan)is dict and set(plan)==keys and plan['schema_version']=='qmt.trade-binding-extension-plan.v1' and plan['journal_path']==str(self.owner.path) and type(plan['expected_version'])is int and plan['expected_version']>=1)
        expected=plan.pop('plan_sha256');_need(digest(canonical(plan))==sha256_text(expected));plan['plan_sha256']=expected
        receipt=None
        with self._adoption(),self.owner._trade_lock(deadline):
            with self.owner._transaction(deadline)as db:
                rows,current=self.read(db)
                if current is not None and current[0]['plan_sha256']==expected:
                    receipt=dict(schema_version=VERSION,version=current[0]['version'],identity_sha256=current[1],plan_sha256=expected,adopted=True)
                else:
                    _need((current is None and plan['expected_version']==1)or(current is not None and current[0]['version']==plan['expected_version']))
                    origin=db.execute('SELECT value FROM trade_identity WHERE id=1').fetchone();_need(origin is not None)
                    _need(plan['expected_current_sha256']==(digest(bytes(origin[0]))if current is None else current[1]))
                    _need(plan['protected_facts']==self._facts(db,deadline));self._preserved_responsibilities(db,deadline)
                    new=plan['new_identity']['trade_binding'];_need(self._identity(new)==plan['new_identity'])
                    _need(_delta(self.owner.trade_binding,new,plan['rule_changes'])==plan['symbol_additions'])
                    _need(_profile(self.owner.admission_profile,new,self.owner.max_result_bytes)==plan['new_profile']);sha256_text(plan['authorization_sha256'])
                    if current is None:
                        db.execute('CREATE TABLE trade_binding_versions(version INTEGER PRIMARY KEY,value BLOB NOT NULL,sha256 TEXT UNIQUE NOT NULL)')
                        db.execute('CREATE TABLE trade_binding_current(id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL,sha256 TEXT NOT NULL)')
                        event=db.execute('SELECT value FROM trade_event_identity WHERE id=1').fetchone()if self.owner.events is not None else None
                        tables={r[0]for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                        retention=db.execute('SELECT value FROM read_retention_identity WHERE id=1').fetchone()if 'read_retention_identity'in tables else None
                        genesis=dict(schema_version=VERSION,version=1,parent_sha256=None,identity=decode(bytes(origin[0])),profile=self.owner.admission_profile,
                            event_identity=None if event is None else decode(bytes(event[0])),retention_identity=None if retention is None else decode(bytes(retention[0])),
                            authorization_sha256=None,symbol_additions=[],rule_changes={},protected_facts_sha256=plan['protected_facts']['facts_sha256'],plan_sha256=None)
                        raw=canonical(genesis);current=(genesis,digest(raw));db.execute('INSERT INTO trade_binding_versions VALUES(?,?,?)',(1,raw,current[1]))
                    event=None
                    if self.owner.events is not None:event=decode(validate_trade_event_storage(plan['new_profile'],new,self.owner.events.storage,max_result_bytes=self.owner.max_result_bytes)[2])
                    value=dict(schema_version=VERSION,version=current[0]['version']+1,parent_sha256=current[1],identity=plan['new_identity'],profile=plan['new_profile'],
                        event_identity=event,retention_identity=current[0]['retention_identity'],authorization_sha256=plan['authorization_sha256'],symbol_additions=plan['symbol_additions'],
                        rule_changes=plan['rule_changes'],protected_facts_sha256=plan['protected_facts']['facts_sha256'],plan_sha256=expected)
                    raw=canonical(value);identity=digest(raw);db.execute('INSERT INTO trade_binding_versions VALUES(?,?,?)',(value['version'],raw,identity))
                    db.execute('INSERT INTO trade_binding_current VALUES(1,?,?) ON CONFLICT(id)DO UPDATE SET version=excluded.version,sha256=excluded.sha256',(value['version'],identity))
                    if self.owner._trade_used(db)>self.owner.max_trade_bytes:raise JournalFull('binding extension exceeds original explicit trade byte budget')
                    _need(self._facts(db,deadline)==plan['protected_facts']);HostReadJournal._finish_deadline(deadline)
                    receipt=dict(schema_version=VERSION,version=value['version'],identity_sha256=identity,plan_sha256=expected,adopted=True)
        self.adopted=True;self.owner._fail_trade('binding_extension_adopted');return receipt
