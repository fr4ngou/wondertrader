# QMT持续行情采集

类型：运行手册。适用范围：独立WT管理的终端外全推采集进程。职责沿[WRI](../specs/independent-wt-runtime.md)，组件格式沿[QST](../specs/qmt-quote-stream.md)。隔离验证、真实来源时效和生产资格分别核对。

## 运行结构

独立WT运行入口→隐藏采集进程→WinSHM Receiver→C++ NativeDataKitSession→原生DataKit/Writer。QMT使用已配对内存策略；外部服务读取部署配置。QMT内部无文件及网络访问的边界沿[源端模块](../modules/qmt-quote-stream.md)保持。

WT启动后listener持续等候，操作员无需另开Host窗口或协调60秒窗口。来源断开后Receiver关闭旧连接资源，再建立下一代认证；同一采集子进程保持一个Writer。采集依原Writer分钟和归档能力运行，断线期间缺少的分钟由历史能力补齐，并单独核实来源覆盖。

## 安装与配置

1. 核GuanhengCollection组件安装清单及各文件摘要。原生DLL、运行库、采集Python闭包与许可证由WT发行管理，观衡Web包和SPA独立安装。
2. 准备连接settings JSON，沿[QST2](../specs/qmt-quote-stream.md#qst2-冻结数据合同)与源策略保持route、transport及证券/profile一致，正文不写secret。凭据从受管环境注入；任意bytes秘密采用显式secret_encoding=base64，省略编码沿utf8。保持原配对身份。
3. 准备原生DataKit配置，basefiles、writer.path及非allday的statemonitor使用绝对路径。writer.module明确选择该候选已验组件；需使用关闭修正组件时配置WtDataStorageLifecycle。保持同步Writer（async=false）及原session，日间使用原StateMonitor；allday只用于对应验证范围。
4. 准备qmt.quote-collector.v1子配置和qmt.quote-collector-process.v1部署描述，固定Pythonw、entry、子配置、原生配置及Session DLL摘要，范围沿[QST6.1](../specs/qmt-quote-stream.md#qst61-应用托管与独立进程)。子入口运行pythonw -I -B，不依赖开发目录或PYTHONPATH。
5. 在独立WT的components.collection中选择kind=quote_collection，填写descriptor及sha256；按[WT手册](wt-independent-runtime.md)启动。旧GUANHENG_QMT_COLLECTION_CONFIG等App托管配置已退出观衡入口。

stop_seconds在部署启动前按证券规模和实际归档/回收时间确定，并绑定本次配置。首次关闭使用同一总截止；达到截止仍未归档完时保留失败记录及已生成文件，不宣称正常归档完成。

同一数据根保持单个Writer。采集服务使用byte-range锁，关闭未确认时继续持有。其他原生Writer和导入工具按部署交接同一根；该锁协调采用本入口的实例，外部程序仍由部署流程管理。

## 观察与数据读取

观衡只读GET /v1/ui/wt-runtime展示WT最近发布的组件状态。采集控制目录status.json包含原生投递/处理、最大来源时间、回调观察时间、连接代际、心跳、队列及固定错误。核实际进程、控制身份和配置摘要后使用；ready只表示进程初始化，旧JSON单独不能证明进程存活。

读取JSON使用独立SDK的guanheng_market_client.runtime_status.read_status；Windows句柄共享删除，允许publisher原子替换。同一次读取可得到完整旧快照，再核schema、控制ID、PID和配置摘要。首次文件未生成或取得句柄元数据前的共享冲突返回CollectionStatusPending，沿原业务截止等待；权限、内容和身份错误按实际失败处理。

盘中分别检查来源时间推进、有效/缺失证券、队列和溢出、原生处理及分钟文件回读。连接恢复、全天分钟完整性和行情时效各有证据。Writer真实写入错误会停止流，已部分生效批次按原责任核查。

采集归档由source-collected历史服务读取，旧历史与新DSB按原[归档模块](../modules/collected-native-history.md)合并，观衡通过公开查询连接读取。原Writer新归档无需手工再次导入；盘中DMB与分钟订阅沿原Reader。缓存准备、读取结果与来源完整性分别标明。

## 正常停止与恢复

### MCC完整候选

`scripts/minute_collection.py`提供`stage-program`、`prepare-source`、`prepare-config`、`prepare-update`、`verify`、`adopt-source`、`rollback-source`、`run-role`、`stop-role`、`accept-minutes`及`accept-coverage`。准备命令只在新E盘根生成程序、完整Source和配置；`verify`核完整文件集、原/新CAS及同一producer/Reader引用。`adopt-source`和`rollback-source`供Root停止对应GH行后显式调用，按完整正文before/after CAS采用或恢复；独立交易/v9保持。

运行过的候选以`prepare-update`固定原deployment和新program，更新进程入口/控制根，保留producer、原恢复marker、收据和原Native引用；原程序仍被数据引用时继续保留。投影发布和消费复用同一预算表，原状态64KiB、覆盖8MiB、维护16MiB，显式预算贯穿原私有文件创建和SDK原子替换。按全部证券乘当前日期范围验容量，另核真实一次完整扫描与稳定运行；[实际故障及全量验证](../evidence/2026-11-04-minute-projection-capacity.md)。

程序包从当前主线保留其他模块，仅覆盖MCC拥有的源；原Writer组件沿既有固定制品，新桥及Reader沿本次成功离线构建。数据根继续原单Writer，恢复产物仍由原Importer独占新根。完整配置准备同时固定7649等实际集合、contracts/commodities/session、QST双方profile、原HPR联合额度及完整Source，数量取本次名册差异证明，不能固定为历史常数。

配置准备请求的`process_pythonw={path,sha256}`显式选择新history/collection完整解释器，原HPR及日线环境独立保持。准入须以每份实际descriptor解释器在`-I -B`下加载其实际入口，核模块来自候选release；schema通过不替代入口依赖验证。Source已被Root按after CAS采用时，准备新目录仍保留原before/after身份及回退备份。实际启动接线修正见[后继验证](../evidence/2026-11-04-minute-startup-runtime-repair.md)。

Root维护前确认当前HPR/日线轮次完成或原请求责任已交接，原未知请求保持原ID核查。动态日线组合先正常停止原日线owner；随后停止原GH行，沿原owner正常停止旧data/quotes并核closed及进程树退出，按CAS采用完整新Source，启动新data/quotes角色，恢复GH行，再启动新日线角色。逐段核认证、实际注册/投递、公开分钟及原日线查询。金融WT及其分析owner保持原所有权。回退先正常停止新日线、GH及新quotes/data，按after CAS恢复旧正文，沿固定原配置恢复data/quotes、GH及原日线控制器。

当前正式日线为动态读取与每日生产同SMP时，`prepare-config`可增加`daily_role_service`固定引用；`daily_base`必须捕获实际当前Snapshot.base，不能用历史模板替代。工厂生成带delegate的`daily-source`、保留原`daily_update`的SMP配置及新角色控制配置，原市场CURRENT/日线任务根/保护槽/53指数等原件保持。此路径由Root先正常停止旧日线owner以释放共享来源与发布租约，统一维护Source/data/quotes，再采用新日线角色；回退停止新角色后沿原控制器恢复。新角色控制CURRENT独立，金融WT当前代及v7/v8所有者保持，避免控制旧HOSTS-RUNTIME。

`prepare-source`从已固定原全文和当前名册生成完整正文，只改同一QST两端集合并移除无消费者旧trade。原HPR配对、profile、Journal与v7/v8设置逐值保留时，旧未知请求继续沿原ID核查；分页读取和后继预算先按实际绑定额度核验。Source产品冻结在已安装原Host环境执行，普通核验/读取保持原轻依赖。

`accept-coverage --deployment <path> --deployment-sha256 <sha> --control-directory <当前采集控制代>`只读原有界投影，核配置/控制UUID/Windows进程身份，按原65秒状态合同报告来源连接、逐类分母/实订/收到/旧日/未收到和分钟扫描进度。命令通过表示身份、当前连接与投影可核且没有明确当日Reader失败；未扫项、缺标签、当日历史准入及BSE等未接入类别分别列出。已报告、成功核查、未报告和未知分开计数；仅成功核查项计入已知缺口小计，全部订阅证券均成功核查后总缺口才提供数值。实际12样本和整集合计数共同存证，不能据注册数量或缓存存在宣称全日完整。

`run-role`复用原`ManagedLocalProcess`及WRI命令，`stop-role`只发送该owner身份的正常停止；实际closed由原监督者发布。`accept-minutes`查询实际策略八ETF、股票和沪深指数，逐项记录该日原值与尾时刻；结果只证明所列样本。来源不支持的市场、当日历史准入、缺少分钟与覆盖未知继续保留。正式源采用和运行资格按[MCC证据](../evidence/2026-11-04-continuous-minute-collection.md)核定。

### 原读取责任与共享容量

Host保留终态并等待消费时，先按原request_id找到生产者窗口及retained-reads slot，分别核对原请求、票据、完整响应、窗口所属证券和日期。采集owner的`retained_read_resume`恢复已派发的未消费读取，并与原窗口工作交替；窗口内部仍在到期重试和新窗口间轮流，日期退出lookback后也继续交接。该路径仅查询原ID并确认完整结果已持久接收，不重新提交准备、不修改Host Journal或容量。state为pending时保留原身份；unavailable时按原last_error_type核身份、内容及读取故障。consumed只证明结果交接，价格成功与原生完整性仍看原窗口/Reader。

升级沿`stage-program`与`prepare-update`产生固定候选，保持原producer配置及workspace、Source配对、原请求、Native根和金融角色。Root正常停止原数据角色、核关闭后采用候选，再从原配置恢复；此修正不要求修改或重启QMT正文。启动后核实际PID/控制代、原ID逐项转consumed、Host等待消费数量下降，以及公开分钟和收盘归档仍可读取。失败按原角色协议退回旧程序，保留已经保存的结果和消费事实；回退不重置Journal或原slot。

动态日线`.9`及原HPR保留的最终候选见[正式采用材料与验证](../evidence/2026-11-04-minute-daily-adoption-candidate.md)。该实例包含固定程序/配置、三份quotes及回退绑定、逐阶段正常启停命令和两个公开入口的12样本/实际采集覆盖验收；正式维护和运行资格由Root执行后登记。

启用原生day归档、50常用指数持续订阅与统一历史动态尾部时，按[持续日线手册](continuous-native-day.md)生成同批配置。维护窗口一次切换后复用原收盘归档，后续每日无需手工打包日线。

停止观衡只收回观衡资源，采集继续运行。停止WT时，父运行入口向采集owner交付停止；Receiver结束并join后归档、关闭Native，父owner核实际子树退出、双管道EOF、线程join及句柄释放。closed.json只在原组件成功关闭时发布；生成文件仍由Helper/Reader回读确认。

超时或强制终止保留失败及未知结果，保持原目录。恢复前分别定位写入失败、来源断开或源时间滞后，并确认旧Writer已结束，再按原身份和数据根协议启动。真实交易及生产切换遵循各自授权与验收。


## 全市场显式v2启动

新部署通过正式pair材料显式选择 `profile.schema_version=qmt.quote-stream.v2`、`max_batch=1000`，沿已确认的全市场证券清单、4MiB帧、65536在线队列和原各期限。源与Host均须支持QST9，并重新生成和verify配对；原v1材料不得改写版本后直接复用。Native仍使用原同步Writer和200证券入口。

启动就绪先表示listener可等待来源。冷初始化期间源保存每证券最新值、Host同步初始化原Writer；随后同代收据确认集合、原子切入最新快照与在线FIFO。观察完整快照覆盖、后继心跳、增量与原生实际计数；当前初始分钟、缺失证券和断线历史分别核实。初始化尚未完成时继续展示等待及实际进度，不能以重连前缀或文件总数宣称全市场在线。

默认v1、旧正在运行实例和旧制品保持；切换、源端一次订阅/原timer、日志、停止恢复及发布资格仍沿原受控步骤。初始化期间保存最新值的语义与在线逐更新资格明确区分，在线overflow不隐藏、不绕过。实际候选和现场结果见对应日期证据，SDK压力通过不能替代实际QMT验收。
