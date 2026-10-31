# QMT 长窗历史快照与分页

状态：分段 accepted，BS1–BS6、BA/BF/HP/BC/BW及BP/BQ/BG为实施合同；Host/C++后继接线分别验收。类型：功能规格。普通历史和默认配置保持原行为，无新增 WT 核心修改。BS纯核心模块为 `connectors/qmt_shm/agent/guanheng_qmt_shm_agent/bulk_snapshot.py`，直接测试 `tests/integration/qmt_shm_history/test_bulk_snapshot.py`。BS核心保持Python3.6.8标准库，无SDK导入、文件、网络、SHM、HTTP或线程创建；上层拥有原QMT线程与既有I/O线程。

## 原生能力与适配范围

复用 [WT-D03/04/05/11](../development/wondertrader-capabilities.md)：历史保存、格式写验和策略读取继续使用 WT 原生模块，来源补齐由服务商适配承担。已固定验证的 Helper/DSB/Reader 字节及实际样本沿[原生整链证据](../evidence/2026-10-27-qmt-source-history-native.md)，本合同不修改它们。新增范围只补 QMT 受限终端长窗结果的线程脱离、容量及分页；原共享内存/认证/Host 域 writer 继续复用，旧项目不进入执行依赖。

## BS1 构造与公开API

`BulkSnapshot(identity, limits, deadline, clock=time.monotonic)`：构造线程是唯一capture owner。deadline为已有绝对单调D，有限数字；绝不续期。identity精确字段：range_id、session_id、snapshot_id、symbol、start_time、end_time。三个ID由上层已绑定身份生成，非空可打印ASCII（0x21–0x7e）最多128字符；symbol为六位.SH/.SZ；时间14位整分钟上海时间，start<=end。纯核心不取系统日期、不生成随机身份、不判断来源资格；上层负责已结束日期/能力/签名认证。每页逐字携带这些固定身份。

limits精确字段：max_rows、max_row_bytes、max_snapshot_bytes、max_page_rows、max_page_bytes、max_total_bytes。全部正整数；max_rows<=1000000，max_page_rows<=max_rows；row/page/snapshot/total容量的关系在构造时验证（row<=page<=total，snapshot<=total）。上层profile固定具体额度，调用者不可逐页覆盖。max_snapshot_bytes指纯值行逐行规范编码的累计UTF8字节（不宣称Python堆精确字节）；max_total_bytes指首次产生的各页完整编码累计字节，重传不重复计费。实际驻留包含单份纯值行数组及一个已发布待ACK页。构建页时允许有限的逐行pieces、join与封套连接临时bytes：令P=max_page_bytes，E为该固定identity在行数/页号硬界下的最大空封套编码长度，R为七个已验证内建数值的最大行编码长度，保守逻辑文本上界为3*max(P,E)+2*E+R，另加至多两个已构造返回包装引用；不包含Python容器/数值对象堆。单行编码受固定七字段、有限float与2**53整数界约束；尚未证明进程RSS等于逻辑额度。供应商Frame在capture阶段与快照并存，其内部内存由来源适配边界说明。

公开方法：

- `capture(read_rows)`：只在构造线程、只允许一次。入口先标记capture_inflight并记录调用已消费，再调用read_rows一次。回调由接线层实现SDK+Frame访问，本核心测试用纯序列；回调返回可迭代的七值行 `(time, open, high, low, close, volume, amount)`，不返回整包JSON。成功返回安全status字典，不返回行。
- `page()`：任何工作线程可调用；单次串行分页工作，同一时刻第二个page调用返回typed busy错误。READY时构建下一页；AWAIT_ACK时返回同一个不可变bytes对象及相同page_sha256，不重新遍历/编码/SDK。不要求QMT tick逐页调度。
- `ack(page_index, page_sha256)`：上层已完成认证和持久化后调用。仅当前待ACK页身份完全一致时推进；记录最后已ACK号/hash，重复最后一次同号同hash ACK幂等。错号/hash固定typed协议错误且不推进/丢弃当前页。最终ACK释放所有纯值行及页bytes，进入completed。
- `close()`：主动放弃未完成快照；无在途工作时释放并进入closed；capture/encoding在途时仅标记close_requested，返回ownership_pending=true并保留全部owner引用。禁止以close返回假装SDK/producer已返回。原工作返回后的finally完成释放。
- `status()`：只安全状态/计数/身份/固定错误码，无行、异常正文。触发截止检查；不调用SDK/producer。返回state、ownership_pending、inflight_kind、close_requested、rows_captured、rows_acked、pages_acked、snapshot_bytes、emitted_bytes、failure_code及identity副本。

公开固定异常 `BulkSnapshotError(code)`，code仅有限枚举：invalid_contract、owner_required、capture_already_started、busy、not_ready、ack_mismatch、expired、closed、failed、source_shape_invalid、source_value_invalid、row_limit、row_bytes_limit、snapshot_bytes_limit、page_bytes_limit、total_bytes_limit、source_failed。异常不含SDK原文；上层保留自身原业务首因。

## BS2 一次来源调用与纯值复制

capture在进入用户回调前检查原D、线程与状态；捕获owner标记先于回调。整个对象永不重新调用read_rows。回调/iterator/NumPy.item等外部操作不可抢占；close或D到期不能解除其责任，只能等待原调用返回并在finally报告真实ownership状态。上层必须持有该对象至inflight=false；不能因status expired释放对象/代码。

最多从iterator取max_rows+1行，额外一行仅判断超限；每次next、标量转换、编码前后检查原D和关闭请求。无限生成器最多消费该有限次数，但单次next可阻塞，按外部owner未知处理。有限producer抛异常为source_failed；超行立即失败，无自动截断。纯序列仍必须验证，不信任Frame.shape。Source adapter需另外用SDK count哨兵判饱和，核心不根据短列表推导历史覆盖。

每行精确7值，原行时间为整数值epoch-ms且分钟对齐、在原闭区间且严格递增；OHLC正/高低关系、量额非负、有限数字。数值转换在capture owner线程进行；只把内建int/float组成的独立tuple加入私有list，不保留调用者可变row/Frame/NumPy对象。逐行有限编码仅计大小并丢弃，整份rows JSON永不构造；超单行/快照额度失败释放已经复制的行。快照完成后read_rows返回的迭代器/Frame引用从核心局部释放，后续worker只接触纯值。

公共校验接缝：在现history_1m.py新增 `validated_row(row,start_ms,end_ms,previous)`，复用现 `_number` 与现行时间/OHLC判断，返回tuple；现v1 _read与bulk均调用，保持原错误code/边界/数值类型。原v1 args/Frame列映射/SDK调用/输出dict/预算语义保持。该提取避免复制两份数值契约；公共校验由 history_1m.py 唯一拥有，两个适配器共同使用。

## BS3 页编码及ACK

page返回精确字典 `{page_index, page_sha256, payload}`，payload为bytes，SHA覆盖同一bytes。payload规范JSON UTF8（ensure_ascii=True、sort_keys=True、紧凑分隔、allow_nan=False），字段：schema=`qmt.history-bulk-page.v1`、identity、page_index（从0）、rows（七值数组）、final、total_rows。total_rows仅快照已完成后已知；source-options/单位等上层profile由session绑定，不在核心伪造事实。

页由max_page_rows与max_page_bytes共同限制，页边界只在行之间；完整封套与final/total_rows计入字节，不只计rows。编码使用有界增量pieces/当前行，不为每次尝试构造整份候选rows重复编码；留足真实封套长度后逐行填充，单行无法放入空页则失败。页生成完成前检查max_total_bytes，只有完整成功页才一次记入emitted_bytes。失败不发布半页。

AWAIT_ACK期间保留page bytes及原行，重复page返回bytes对象同一身份。ACK后把已ACK行引用逐项释放并清除page bytes，再进入ready；最后ACK进入completed。空快照也生成唯一final空页，等待ACK后completed（业务empty由上层报告）。ACK不驱动SDK/重新编码；异常ACK不改变rows_acked/游标/页bytes。

## BS4 状态与并发/关闭

状态：new → capturing → ready → encoding → awaiting_ack → ready/completed。终态failed/expired/closed/completed明确区分。failed为来源/校验/容量失败；expired为原D先到；closed为主动关闭先到；completed仅最终ACK后成立。第一次被核心观察到的终态原因锁存，后续close/D不把failed或completed覆盖；状态终态与ownership_pending独立，expired/closed发生在外部调用在途时仍pending。

短锁仅保护状态/游标/引用交换；capture回调、iterator、行编码与分页编码在锁外执行，期间有明确inflight owner记录。close/status可及时发现pending；第二worker不能同时encode或ACK正在encoding页。关闭/到期后编码返回的临时结果丢弃，不发布页；finally清owner，释放快照。原D检查与终态锁存受同一短锁保护，ACK与expiry竞争按检查/锁存顺序决定，D之后不能推进ACK；completed后的相同最终ACK仅返回原终态，不重新推进或授予新的成功。

调用方异常/工作线程仍运行时不设置pending=false。方法内部finally负责正常/异常返回时解除该方法owner；所有状态释放都保留正在使用的局部引用至其返回。模块不创建daemon、不join、不重试、不延长D。capture原异常经过安全码投影，上层可按其原异常协议记根因，不输出正文。

## BS5 最少直接回归

一次回调/owner线程；行转换后原列表变异不影响快照；首次page后重传bytes is相同且callback/encode计数不增；ACK推进/最后ACK释放/重复最后ACK幂等/错ACK不丢页；空快照final页；跨页时间/原值等值；row/maxrows+1有界消费/无穷iterator；单行/页完整封套/总快照/总发出字节边界；NaN/Inf/非法OHLC/越窗/重复时间；capture异常；原D在capture或encoding内到期；阻塞producer期间close/status立即pending且不释放owner；返回后closed/expired释放；并发page busy/ACK与关闭竞争；failed后close不覆盖，completed后close不降级。必要真实线程测试用Event和有限join，纯替身不SDK，不睡满业务D。

本核心不宣称调用者持久ACK、签名身份、SHM路由、真实Frame线程安全或全市场覆盖已验证。同range永不SDK重放；上层在确认snapshot失效及原owner结束后，可由显式调度策略生成新任务身份/数据版本，不把readonly unknown永久变成人工阻塞，也不伪称新任务是原快照恢复。

## BS6 当前页只读元数据

pending_page_metadata()只在当前awaiting_ack时返回精确小字典page_index/page_sha256/rows/final。rows为_page_end-rows_acked，final为_page_end==rows_captured（含空页）；元数据与已缓存page同一身份，不解码page或复制行，不改变原page()/status()字段与bytes。短锁内沿原D检查后构造小对象；无当前页not_ready、捕获/编码在途busy、关闭/到期沿原错误。调用者须将元数据index/hash与同次page返回值核同，再决定max_pages最后页是否完整；该查询不授ACK或覆盖资格。

验证空页/普通多页/最终页的元数据与实际payload一致，返回字典变异不影响缓存；查询不编码、不调用SDK或推进计数，同页bytes保同一对象；ACK后不再返回旧页；过D/close、编码在途及失败均不伪造页。该接缝避免运行层为读取final而解码整页行JSON。

## BA1 原线程 SDK 适配

`BulkHistory1mAdapter(context, value, identity, limits, deadline, clock, as_of_date_provider)` 每实例绑定一次读取及一个 `snapshot`。value 沿普通四字段参数（symbol/start_time/end_time/max_rows）；只显式扩大部署 max_calendar_days/max_rows，不放宽普通 v1。limits 额外包含 max_calendar_days，其余为 BS1 六额度；所有权及请求行数收窄在构造时固定。身份中的证券及起止必须与参数逐字一致；起日>=20211101，结束日期早于可信上海 as_of，截止传原单调 D。构造无 SDK/线程/文件/网络调用，未注册新能力。

`capture()` 仅构造线程一次驱动快照；SDK 仅 `ContextInfo.get_market_data_ex`，fields 为原七列，period=1m、none/fill_data=False/subscribe=False，count=request.max_rows+1。shape>=count 为 row_limit，禁止饱和截断成功；Frame shape/columns/实际迭代行数交叉核查。列可以合法重排，实际行按 FIELDS 复制；空 Frame 仅允许0或7列。shape、列、iterator 和 NumPy.item 均在原线程执行并按同一 D/close 检查，安全失败分类不含供应商异常正文。SDK 原生内存峰值及不可抢占时间独立保留为未验限制。

## BA2 分页和后继接线

适配器只把独立 snapshot 交分页 owner；Context、Frame、标量对象和原行引用均不交 worker。供应商对象仍被 capture/generator 使用时必须 pending；原调用返回及 finally 关闭自有 generator 后才能报告释放。分页 BS 接口成功仅证明内存合同；尚未证明 Host 落盘或 SHM 业务 ACK。单页传输复用 ControlPeer 原 CALL/REPLY/ACK 与 HostDomainWorker，slot ACK只表示运输复制，Host持久页之后的业务确认才推进快照。关闭清除peer不等于已ACK；后继接线须保留明确的已验证退休事实。

Host 后续逐页CSV直接生成原 QMI v2 chunks，每证券独占数据根及成功 qmt-import 收据，复用原 Helper/DSB/sourceReader，不新增拼接器或数据库。原Importer每证券仍物化有限 WTSBar 数组，整体内存须实测。独立 bulk profile 版本尚未实施；v4 已供交易使用，不借旧版本偷偷放宽。显式新能力未接入认证 registry 前，普通 API 均不开放 bulk。

## BA3 SDK 边界验收

验证一次 SDK/哨兵/长窗/列重排/空值/shape与迭代不一致、owner拒绝、NumPy标量线程、Frame原列表变异、工作线程逐页且SDK次数不变、D在SDK/迭代内到期及关闭时pending。保留普通 v1原测试及错误码/默认字节。Python3.6实际解释器与现代解释器分别跑；它们只证明替身边界。真实两分钟与月窗的对照、SDK耗时/纯复制/内存/页落盘吞吐、完整证券历史与ETF覆盖仍需真实后继证明。

原生能力复用与最终范围见[批量导入方案](../migration/qmt-bulk-history-export-plan.md)及[源值存储合同](qmt-source-history.md)。


## BF1 输入与类型

`BulkHistoryFiles(root, source_session, source_profile, identity, limits, deadline, clock=time.monotonic)`。

- root：本地可信配置给出的绝对 `Path`，现有受管E盘父目录下尚不存在的新目录。用原 `create_private_directory` 独占创建root及root/csv；拒绝现有目标、符号链接/重解析点。root不取自页面正文。
- source_session：本地已认证SourceSession的精确dict：provider=`Qmt`、instance_id、session_id、generation；两ID为沿RS校验的非空白文本<=128，generation为内建int、1..2**64-1。任何这些值均不由页正文生成或覆盖。
- source_profile：本地精确dict，与现C++v2配置相同12字段：dataset_version、source_license、input_kind、asset_class、timezone、minute_boundary、adjustment、factor_version、value_semantics、price_unit、volume_unit、amount_unit。asset_class=`cash-equity`，input_kind=`synthetic`或`qmt_export`，timezone=`Asia/Shanghai`，adjustment=`none`、factor_version空，value_semantics=`source`；minute_boundary=left/right/unknown，price/amount=CNY/unknown，volume=share/lot/unknown；dataset/license为沿RS校验的非空白文本<=256（拒控制字符、DEL/C1与surrogate，不改变原字符串）。配置不含4个派生来源身份；最终QMI profile=SourceSession四字段加配置中除asset_class外的字段。
- identity：精确BS字典 range_id/session_id/snapshot_id/symbol/start_time/end_time，格式及窗口与冻结BS相同。identity.session_id必须与上述SourceSession.session_id一致；range/snapshot已由上层绑定。文件边界另沿BA限定start>=20211101且end.year<=2099，保证原Importer日期可接；不在Host自行推导as_of或真实历史覆盖。只接受该symbol及窗口，页不得重定义身份。
- limits：精确内建正整数dict：max_pages（<=10000）、max_page_rows（<=max_total_rows）、max_page_bytes（<=2MiB）、max_csv_bytes（<=2MiB）、max_total_rows（<=1000000）、max_total_bytes（<= (max_pages+1)*2MiB）、max_manifest_bytes（<=2MiB）。total_bytes计实际写出的CSV及manifest；重放不重复收费。一个页只产一个CSV，文件数量最多max_pages+1。max_page_bytes限制输入bytes，max_csv_bytes限制输出CSV，防止格式化扩大；max_manifest_bytes兼容原durable writer单文件2MiB上限，严于Importer4MiB上限。
- deadline：上层原绝对单调D，不刷新；clock可信可调用。所有外部文件读写和行迭代前后检查D。构造先验全部配置与D再创建目录；半构造留下私有partial，异常不删除/覆写。

构造防御复制小配置。依赖根提供的 `private_files.write_private_durable_new(path, content, deadline, clock)`，该函数成功才代表写入、FlushFileBuffers及Close已确认；它失败时本模块不能假定文件不存在或已耐久。测试通过模块级替身隔离OS，生产不另写WinAPI。

## BF2 方法与状态

`accept(page_bytes, page_sha256) -> receipt`：page_bytes必须精确bytes且非空、<=max_page_bytes；sha为小写64hex并匹配同buffer。JSON严格UTF8、拒重复字段/NaN/Inf/异常深度，精确BS page schema/identity/page_index/rows/final/total_rows；所有整数拒bool，字段/身份/窗口须完全一致。page index从0连续，max_pages有界。

解析后逐行仅接受七项内建int/float，复用已冻结 `history_1m.validated_row` 做数值/分钟/窗口/跨页严格递增校验，传原D检查函数；JSON输入没有可信NumPy钩子。total_rows首次固定且每页一致，<=max_total_rows；非终页必须有行且累计<total，终页累计==total。声明total不证明交易日覆盖，只限定本snapshot实际记录集合。

单页CSV字段精确为 `timestamp,open,high,low,close,volume,amount`；上海源分钟label不移位，格式YYYY-MM-DDTHH:MM:00+08:00。六数值先验finite与exact-int域后按double的17位有效数字输出，locale无关；重新解析float后须与源值的double表示相同，禁止乘factor/改变单位。逐行编码进受max_csv_bytes约束的有限buffer，不组装全证券大rows列表或整JSON副本。每页生成 `csv/page-000000.csv`（0-based六位，max10000页），完整表头允许Importer chunks逐页消费。

流程：全页验证及容量预计算 → durable新CSV → 读回同文件核大小/SHA及前后身份/D → 更新内存已提交页表和行游标。可抛出的安全receipt对象及更新所需小对象尽量在IO前备好，失败都终止当前collector，不能因partial误报ACK资格。写入后发生异常也保留文件且失败；同collector不偷偷重写该页。

终页非空：把按页序的已提交CSV引用封成原QMI v2精确结构 `schema_version/profile/securities[{symbol,chunks[{path,sha256}]}]`；路径使用普通相对posix路径。写入前重新核所有已落chunk SHA、大小/身份、总数、总字节和D；以同durable函数独占写 `qmi-manifest.json` 并读回核同。只有全部成功才进入sealed。成功manifest最后产生；此前文件失败/超时仅partial且本collector不给成功receipt。若manifest写入本身发生Flush/Close/后验故障，磁盘可能留名为qmi-manifest.json的未确认文件，状态仍failed/expired，上层必须以collector成功receipt+原Host Journal terminal提交为资格，不能凭文件存在判成功；模块不删文件掩盖失败。

唯一空结果：只允许page0、final=true、total_rows=0、rows=[]。原Importer禁止空证券，因此保留空观察状态empty，不生成伪QMI/CSV；final receipt的manifest字段为None，importable=false。上层提交明确empty terminal后才有最终ACK资格；空结果不推导缺历史/停牌事实。

receipt精确字段：page_index、page_sha256、csv_path（相对路径或空结果None）、csv_sha256（或None）、rows、total_rows、final、durable（bool）、ack_eligible（bool）、requires_terminal_commit（bool）、manifest_path（相对路径或None）、manifest_sha256（或None）、importable（bool）。中间页durable=true/ack_eligible=true/requires_terminal_commit=false；非空终页sealed且manifest已确认时durable=true/ack_eligible=false/requires_terminal_commit=true/importable=true；empty的durable=true仅指没有待持久化行情正文、ack_eligible=false/requires_terminal_commit=true/importable=false。收集器绝不把final ACK标成已获准，上层原Journal terminal提交成功后自己决定最终ACK。

`status()`：仅安全字段 state、failure_code、pages_committed、rows_committed、bytes_committed、next_page_index、identity、manifest_sha256（或None）；不含行情行/绝对私有路径/原始异常。状态collecting、sealed、empty、failed、expired。原deadline到期时未sealed/empty进入expired；后续accept包括重放均须检查原D，不将已sealed事实重写为另一业务结果，但过D重放也不再授ACK。

无close方法：不拥有长期文件句柄，durable writer负责每次真实关闭；上层domain线程持有collector直到方法返回。调用者不能跨线程调用accept/status，不构造并发假安全。原D不能中断正在系统调用的IO，调用返回后再次核原D并保partial。

## BF3 重放、首因和恢复

已提交页表每项保存原page hash、已落CSV相对路径/hash/大小、范围/行数及安全receipt；不保存源page bytes/整页rows。最多max_pages项。收到旧页号时先验证相同page hash和输入bufferhash，然后以有界读取重新核实际CSV SHA/文件身份；final同时核原manifest及其全部chunk。只有仍一致且D允许才返回同资格receipt，不新增文件/不推进计数。异hash、缺文件、文件被替换/改写或未提交页跳号均failed，保第一错误。

公共 `BulkHistoryFilesError(code)` 仅固定枚举：invalid_contract、owner_required、invalid_page、identity_mismatch、page_sequence、page_conflict、source_value_invalid、row_limit、byte_limit、file_identity、storage_failed、expired、failed、sealed。原异常正文/自定义code永不进入公开状态。纯页/身份/数值/协议验证异常只锁存固定码，不保存无资源原异常或解码栈；实际存储/资源异常才保原私有error/resources。对象不缓存会被抛出的public异常；每次新建安全错误，在except外抛出，自有accept/读写/编码局部在finally释放，防止状态通过traceback保留整页。若底层SecurityResourceError保留未确认释放的resources，collector与其固定错误保留同一私有retained_error/retained_resources引用，供上层沿原domain线程继续回收；读取首因与独立close错误分开，原读取/到期错误保持公开首因，retained_stream/retained_cleanup_error私有引用持有未确认流及清理异常；不进入安全status/receipt，失败后不新增写入或声明closed。失败和过期首因锁存；后续accept只抛同首因，不进行写入/不覆盖已落材料。wrong owner拒绝不篡改原owner状态。

不提供从磁盘重建collector或恢复Agent快照的API。Host重启/原snapshot不可恢复时由上层明确unknown/expired；确认原owner结束后显式调度新range、新snapshot及新dataset_version/新独占根，重新建立完整证券数据集。原partial保留，不把其行重新标成新session，也不把readonly未知永久转成人工审批。一个range的页重放与新任务重建是两种明确状态。

## BF4 最少直接验证

纯页→CSV→原Importer解析兼容（source double和时间往返）；多页终页原QMI字段/顺序/hash；unknown单位保留；mid ACK资格与final等待terminal资格；空终页无伪manifest；重放同号同hash实际读回成功且不增预算；CSV/manifest被改/失踪/重解析路径拒绝；异hash/跳号/错身份/重复JSON键/bool计数/NaN/跨页倒序/总数不符；输入/输出/总量/manifest容量边界；逐行到期；CSV写/Flush/Close失败与终页manifest写失败均无ACK资格，partial保留、第一错误保持；根已存在拒绝；wrong thread；正常sealed后重复终页核文件，不自动提交Journal/ACK。

真实durable writer的Flush/Close行为由其独立测试与根实测授予；collector纯替身测试不冒充OS耐久证据。本接缝只产与原Importer兼容的文件，不注册bulk profile，不启动Host/SDK。

## HP1 Host 显式耐久私有文件

`private_files.write_private_durable_new(path, content, deadline, clock=time.monotonic)` 复用原创建期protected DACL、CREATE_NEW和SecurityResources；单文件仍1..2MiB，成功必须WriteFile完整、FlushFileBuffers成功、CloseHandle/LocalFree释放已确认且仍在同一原D内。入API前、可信分配/WinAPI后及资源scope关闭后核D，buffer构造后/实际WriteFile前也核D。新入口不替换普通write_private_new默认行为，普通入口仍保持原不flush的配对材料用途；实现共用唯一内部创建/写入。

Flush失败、短写、到期或关闭失败保留原文件及首因，无自动覆盖/重试/删除。SecurityResourceError保留实际resource slots；上层接收固定码时仍须持有该owner，直到原线程确认关闭。单WinAPI不可抢占，原D只在调用返回后判定；不声称文件flush给出断电目录事务或强制终止IO。验证含真实私有小文件写/读、默认不flush兼容、短写、Flush失败/晚回、buffer跨D不启动Write、Close失败与资源/首因保留。

HP1补充：内部同步writer及两个公开包装在WinAPI与资源scope返回后finally清content/buffer等自有行情引用；原SecurityResourceError实例、resources、original身份继续保留。纯Python/JSON验证栈无需成为恢复owner，实际资源失败图不得通用擦除。


## BC1 已验证回复确认收据

ControlPeer 新增可选 observe_reply_ack(call_seq, payload)，仅对该peer当前保留的成功REPLY及逐字规范payload创建/复用一个只读收据；未有REPLY、payload不同、错误/过期REPLY、已经退休或close均返回None。sequence沿原约束；canonical/解码及对象构造在短锁外，发布前重核同一缓存bytes、peer仍open及成功payload相同。异常/关闭竞争不得发布伪收据或新建已消失的incoming。

收据公开只读 generation、call_seq、request_sha256、reply_sha256、state；状态pending→acknowledged或abandoned，仅一次终态。state在与peer状态同一短锁下读取；收据仅持该锁及小型固定身份，不持payload、Snapshot、SDK、handler或整个peer。每个当前incoming最多一收据，计入原entry_overhead_bytes固定预留；无额外历史表/队列。默认调用未申请时不创建收据，不改1.0/2.0wire/schema/额度和原reply返回值。

acknowledged仅在原receive完成整个认证上层交来的packet的语法、generation、cycle及所有上下文验证后，与匹配已发送成功REPLY的ACK退休在同一次锁内发布。任何后续同packet消息不合法时，全部状态及收据均不推进。prepare、sent、ControlFuture.ack、future.retired、has_incoming消失均不能代替源端receive确认。close对尚pending收据置abandoned，已acknowledged保持；旧代收据不用于新peer。ACK可证明对端确认该REPLY身份，是否已持久化仍由Host域遵守BF/Journal顺序，本收据不伪造耐久资格。

SDK快照调用方在读取acknowledged后仍调用原snapshot.ack并受原D/关闭约束；确认事实不续期、不令已失效快照恢复。确认没有应用层回调，避免短锁内调用业务或SDK。

最少回归：未回复/错payload/失败回复拒绝；同页重复观察同一收据且身份绑定；Host只take/ack、ACK仅prepare/sent时源收据仍pending；源真实receive后acknowledged；错误hash/旧generation/错cycle与同packet后续非法CALL保持pending和缓存；重复ACK原协议拒绝；并发观察与close/receive不复活条目；关闭pending为abandoned、成功后关闭保留成功；未观察的原默认路径及窗口额度保持；ACK退休后新CALL可使用原窗口；空/多页快照可据真实收据推进，最终页在原Journal terminal提交后才发送ACK。该合同本身不声明bulk registry/运行调度/真实SHM整链已接。


## BW1 显式 bulk 控制语法

新增 local_control_protocol_bulk.json，schema_version=3.0、extends=1.0、base_sha256核原base固定身份；复用1.0全部packet/message/ACK/双向窗口/预算常量，交易2.0保持独立。control_versions仅按显式3.0选control_wire_bulk；默认1.0/2.0输出与行为保持。生成器复用原公开生成路径，旧CLI默认trade、原render(base,trade)输出字节保持；bulk显式选项生成静态源码，QMT运行不读JSON。

精确新增host caller三项：agent.bulk.open payload键 request_id/identity/arguments/clock_schema/deadline_ms/queue_deadline_ms；agent.bulk.page键 request_id/identity/page_index；agent.bulk.status键 request_id/identity。原control_messages仅验证已有封套及这些精确字段，身份/业务D/额度/内容由后继能力接线层验证，不将grammar通过称为业务受理或SDK权限。

身份沿BS六字段；open原线程一次capture、page原I/O分页、status只安全状态。一个页REPLY逐字承载规范BS bytes的base64及原SHA；Host按BF写中间CSV/最终QMI及原Journal成功后ACK，源端由BC1真实确认才snapshot.ack。最终业务payload、v5 capability/profile、Host请求/terminal模型和运行接线仍待后继合同冻结；本节只冻结控制语法，不向旧profile或默认API授bulk能力。

验收覆盖公开JSON生成与静态源码逐字一致、固定base摘要/重复键/重合操作/非法字段拒绝、原trade输出不变、1.0/2.0不能发bulk、3.0不能借用trade、版本握手/方向/精确payload/原窗口/ACK收据在3.0亦保持，现代和国信3.6.8分别验证。

## BP1 显式 v5 能力与配置

能力名固定market.history_1m.bulk，profile版本qmt.read-profile.v5；本切片只组合原只读能力，不组合trade。read_operations为排序唯一的原三个只读操作与bulk的子集，必须含bulk且至少一种原只读操作。旧known_operation、普通请求和build_read_profile继续只登记原三个操作；旧validate_read_configuration继续拒v5。

v5 profile精确六字段：read_profile_version、read_operations、execution_timeout_ms、control_profile、operation_profiles、bulk_profile。control_profile必须3.0。operation_profiles精确包含启用的原只读操作，直接复用原_operation_profiles的policy、执行额度及结果校验；execution_timeout_ms仍为这些原descriptor的最大值。普通operation_descriptor/validate_read_request通过共用validate_read_profile显式识别v5，bulk不进入普通SDK结果队列。原v1–v4分支、字节和范围保持。

bulk_profile精确七字段：schema_version=qmt.history-bulk-profile.v1、policy_id=qmt.history-bulk-read.v1、policy_version=1.0、clock_schema=qmt.win-uptime-ms.v1、queue_timeout_ms、total_timeout_ms、limits。queue为100..300000毫秒，total为100..360000毫秒，queue<=total。所有业务阶段共享total原D，不把total当每页额度。limits精确九字段：max_calendar_days（1..36600）、max_rows（1..1000000）、max_row_bytes、max_snapshot_bytes、max_page_rows、max_page_bytes、max_total_bytes、max_pages（1..10000）、max_ranges（1..10000）。row/page字节正整数且<=2MiB，snapshot/total正整数且<=1GiB；row<=page<=total、snapshot<=total、page_rows<=rows、ceil(rows/page_rows)<=max_pages。逻辑编码预算不表示SDK或Python RSS硬上限，部署必须显式提供额度，无批量默认放宽。

公开bulk_capabilities.build_bulk_read_profile(operations, execution_ms, control, operation_profiles, bulk_profile, max_result_bytes=...)和validate_bulk_read_profile/profile_descriptor返回无别名小字典。新增唯一BULK_READ_PROFILE_VERSION常量由read_capabilities拥有；validate_read_profile仅增加显式v5委托。bulk_capabilities拥有新operation/profile/policy/limits校验；纯准入不创建SDK、时钟、线程或运输对象。

bulk_configuration.validate_bulk_configuration精确接受原_REQUIRED + read_profile_version/operation_profiles/bulk_profile，复用_admit_configuration及ReadConfiguration。要求builtin-shm，完整v5认证profile进入原布局；总时限/1000+io_seconds<=control.max_call_seconds，至少保留一个Host和一个Agent方向槽。完整page delivery必须再包进原Control REPLY全部字段（kind/call_seq/request_sha256/ok/payload/error），使用最长允许UUID/nonce、最大序号/hash及page_index，空body的完整REPLY规范字节数加4*ceil(max_page_bytes/3)必须<=max_reply_bytes；再沿原cycle/frame关系校验。测试以实际完整编码/validate_message为边界oracle。普通结果仍按原max_result_bytes验证，页原bytes额度不能替代base64封装额度。该入口不注册Host或生成终端正文。

## BQ1 会话身份与原期限

open payload沿BW1六键。request_id与identity.range_id均为同一小写canonical UUID；snapshot_id也为小写canonical UUID，identity.session_id必须等于当前已认证Session.generation的32位nonce。证券及起止沿BS，arguments精确四字段且与identity逐字一致；max_rows仅可缩小部署cap。原start>=20211101、end<=2099且严格早于可信上海今日。deadline_ms/queue_deadline_ms为正内建整数，沿原trade_clock.deadline_seconds共享毫秒域核上界后才进入浮点计算，任意大整数固定invalid_request；clock_schema固定。queueD<=业务D，初次准入时各自剩余额度不得超bulk_profile声明值。完整open canonical<=2048字节。重复同request_id只接受同一原payload bytes，任何身份/参数/D变化均拒绝，不再次SDK。

业务时钟使用现SharedUptimeClock对象的seconds()，终端默认必须实际核GetTickCount64；纯测试可显式注入提供seconds()的可信clock对象，不同时维护第二种callable配置写法。Host现代Python不能把QPC冒充同机uptime，后继Host必须提供已核Windows uptime读取器。控制CALL的本地monoD另由peer首次映射；初次open准入必须先采shared_now再采transport_now，以shared_now+max(0,controlD-transport_now)向下映射毫秒，effective_business_D取其与payload共享D的min，queueD再取min。该采样顺序把中途延迟计入，禁止反向采样令D变晚。只映射一次且只缩短；重复open、page、status、重连和ACK均不重授期限。source调用clock/monotonic失败时固定错误并停止新bulk，不回退UTC或新now+TTL。

## BG1 原线程快照服务

SourceBulkHistoryService(context, profile, max_result_bytes, clock=None, monotonic=None, as_of_date_provider=None)在原QMT构造线程建立，只用标准库。bind_generation(generation)由已认证I/O owner执行一次，相同值幂等、不同值拒绝。绑定前不得受理open。一个连接只有一个活动range；最多max_ranges个小记录且不静默淘汰。新range在旧快照completed/failed/expired/closed且ownership_pending=false后才受理；旧ID记录继续拒绝SDK重放。

公开enqueue_open(payload, control_deadline)返回原MemoryCompletion；新记录在进入SDK前占有原身份、payload bytes、原D和future。重复同payload返回同future。活动冲突busy，记录满range_limit；不创建第二任务或后台线程。tick(allow_heavy=True)只允许构造线程，最多认领一次SDK capture；先标记construct/capture在途，再锁外构造BA适配并执行。adapter在原线程构造，SDK/Frame/NumPy也只在原线程访问；I/O只取得BS快照，future发布规范小bytes及安全状态，不把快照/Frame交普通to_json_value。

服务方法page(payload)接BW1 page精确三键，status(payload)接status精确两键；核已绑定request/identity。page_index必须等于当前BS页号；max_pages用尽且非final立即固定page_limit失败，不把半程当成功。同页重传复用BS原bytes/SHA；交付payload精确schema=qmt.history-bulk-delivery.v1、request_id、identity、page_index、page_sha256、body（原page bytes的base64ASCII）。snapshot页不改变单位或源label，不依赖后续QMT tick。

open完成和status分别使用qmt.history-bulk-open.v1 / qmt.history-bulk-status.v1封套，精确字段schema/request_id/identity/stage/snapshot/error_code。stage为queued/capturing/snapshot/terminal；snapshot为None或BS安全status，服务construct/capture仍在途时ownership_pending须保持真实。未来完成bytes<=4096且不含原异常/行。活动退休后仅保小身份、原payload/future与安全终态，释放snapshot/adapter引用；全服务记录逻辑大小逐项有限，不缓存Frame、page或异常traceback。普通结果无新业务账本。

acknowledge(payload, page_sha256)仅由本地已验证BC1收据的I/O owner调用，payload仍为原page请求；服务核身份/页/hash，原snapshot.ack继续检查同一D。过D已确认收据也不推进快照。expire()只推进原D，request_close()立即冻结新open并对活动snapshot.close；构造/SDK/编码仍在途时持有原owner，drained仅在所有在途及snapshot ownership都结束后成立。关闭不重放、不强停QMT、不创造新的清理预算。

服务外层base64/规范交付及状态编码也必须计入在途，清自有临时引用后才解除owner；BS内部_work结束不能替代外层返回。服务不得持自己的状态锁调用BS，以保持唯一锁顺序。传BS的clock适配把来源时钟异常先锁存为服务clock_unavailable并停止准入，再抛BS已知BulkSnapshotError固定码，使BS.close/status仍可完成关闭。该clock回调可能在BS锁内运行，因此仅锁存服务事实，不递归关闭BS、不回退时间；服务外层随后调用close，捕获仍在途时继续保owner。真实BS加故障clock验证capture后、page中及request_close的首因与排空。

固定BulkServiceError(code)仅含BS枚举及invalid_request、identity_mismatch、range_limit、not_found、page_limit、queue_expired、clock_unavailable。同步非法请求可投原control invalid_arguments，业务失败payload仅schema=qmt.history-bulk-error.v1/code，不回显未验证输入。首因和原任务身份保留。普通异常不能让同range重新capture；不可抢占调用回返后才在finally清在途owner。

## BG2 原 I/O 控制循环

BulkAgentControlLoop继承原AgentControlLoop，只处理显式3.0；构造绑定session.generation，沿take_call_with_deadline接open的首次monoD。普通操作仍调用原_dispatch/_complete_pending。open future异步poll，SDK工作不在I/O执行；page/status在原I/O推进纯值。每连接至多一份待确认page交接，旧CALL重放仍由ControlPeer缓存；不同新CALL在上一页待ACK期间背压。

open的完成订阅同时保存该CALL首次控制monoD，与服务共享future的业务D分别拥有。派发新CALL前及poll/回复边界按同一控制时钟退休已过期订阅；只移除本CALL的引用，不cancel共享future或原SDK工作，也不向已经退休的call_seq补回复。订阅总数不超过已准入control_profile.max_pending_calls，满额返回有界busy；原Peer继续拥有运输槽与过期缓存。测试可显式注入可信monotonic，并与真实Peer使用同一控制钟；默认仍用原time.monotonic。服务owner和终态记录继续按原业务D、原身份保留，控制订阅退休不授服务drained。

page成功缓存后用observe_reply_ack绑定该成功原文，保存原page请求/hash和收据；缓存过期错误不能当交接成功。下一次receive完整提交后、派发新CALL之前先观察该收据：acknowledged才调用service.acknowledge；pending保持原页，abandoned/close只请求服务关闭。非成功业务回复不注册页收据。最终页也走相同确认，不因body为空或Host本地future.retired释放。原Host必须先遵守BF/Journal顺序，该源循环不伪造对端耐久资格。

close先对service.request_close，再关闭原peer/取消本循环future；service仍持构造/SDK在途责任，I/O退出不代表服务drained。页编码、base64、状态构造均在短锁之外，不锁内调用SDK、编码或handler；仍复用原transport/thread，不新增I/O线程。

## BG3 显式 Agent 与常驻恢复

RestrictedBulkReadAgent是显式RestrictedReadAgent子类，使用bulk_configuration，共用原_initialize、连接、认证、线程及退出；tick优先执行一个bulk认领，否则沿原普通read队列，allow_heavy=False不执行SDK。默认RestrictedReadAgent构造继续拒v5。request_close同时关闭service与原owner；管理close在原I/O join/资源确认后，仍核bulk.drained，未知SDK保留整个agent。

ReconnectingReadAgent仅增加默认原行为的_admit_configuration/_make_agent接缝；显式ReconnectingBulkReadAgent覆盖为v5及RestrictedBulkReadAgent。仍由原QMT tick推进代际，旧Agent实际退出和bulk drained后才退休；新代重新认证，旧session身份不能在新代重放，未知range不自动POST。配对/Host/C++及真实终端装载后继单独接线与验收。

BP/BQ/BG最少验证：旧profile/构造拒绝及字节兼容；新v5字段/政策/数值/绑定/额度/封装完整边界，secret无别名；一次原线程SDK和脱离Frame，open重传/改身份/D拒绝、单活跃/记录满、SDK构造/调用/编码在途close、queue/原D各阶段到期、clock失败、三页与空页、实际peer ACK前不推进、非法后续message整包拒绝、SDK错误固定码及释放，page不依赖tick；默认Agent/重连回归；现代和实际3.6.8分别执行。真实SHM bulk、Host final Journal提交顺序及全历史覆盖继续保持待验。

## HC1 Host请求、时钟和来源

显式Host bulk入口复用bound外层qmt.bound-read.v1的binding_sha256、原body base64/SHA，不扩普通DTO。新body精确13字段：schema_version=qmt.history-bulk-request.v1、request_id、correlation_id、operation_id=market.history_1m.bulk、policy_id=qmt.history-bulk-read.v1、policy_version=1.0、arguments、snapshot_id、clock_schema=qmt.win-uptime-ms.v1、deadline_ms、queue_deadline_ms、priority_class=normal、read_profile_version=qmt.read-profile.v5。三个ID为canonical小写UUID；arguments精确symbol/start_time/end_time/max_rows且满足BA历史合同及bulk_profile额度。时效值经原deadline_seconds界限校验，queueD<=D；形状验证不读取当前时间。新C++客户端首次构造后固定原字节，恢复只GET；同ID改D/snapshot/原字节冲突。用户无需填写内部身份和时钟。

Host-only bulk_clock.WindowsBulkUptimeClock使用kernel32.GetTickCount64，显式无参数及uint64原型，读取精确整数毫秒；seconds为该值/1000，不将现代Python的QPC或UTC冒充此域。仅可信测试可注入read_milliseconds/platform；非法平台、bool、负数、超过原deadline_seconds上界及原始读取异常固定ValueError。模块导入不读钟或载DLL，构造不启动线程/服务/SDK。此入口不改变现有交易默认钟。

bulk_contracts.validate_bulk_request(value,profile,*,max_result_bytes)纯验证返回独立dict，要求显式v5及bulk准入；不执行初次时效检查。bulk_identity(request,actual_binding)及bulk_open_payload分别返回BQ1六字段identity和open六字段payload；由原body和完整3.0 binding唯一构造，不生成新ID/D。bulk_source_session(actual_binding)精确映射provider=Qmt、instance_id=host_instance_id、session_id=transport_generation、generation=route_epoch+1；不得采用常驻服务内部代数。

同请求local owner首次先采local0再采shared1，localD=local0+max(0,sharedD-shared1)，queue同式且不大于localD；随后仅取min，不重设。后台任务的共享D不由HTTP短POST读取预算替代。每阶段同时检查两域，任一到期即止。受理/查询/资源等待的本地I/O D分别属于该调用，不能放宽已持久业务D。

## HC2 小终态与稳定产物引用

bulk_contracts.make_bulk_result(request_id,*,data=None,error_code=None,completed_at=None,max_result_bytes)复用原results.finalize_result及完整结果默认/计时字段，operation_id固定bulk；成功/失败分别以data/error_code表示，observation始终null。completed_at省略时仅取UTC完成标签，不用于业务期限。错误码精确operation_interrupted/source_binding_changed/queue_timeout/expired/source_failed/storage_failed/invalid_page；失败data=null且固定中文error_message“批量历史读取未完成；保留原请求标识核查”。成功error_code/error_message=null。所有timing沿原完整结果定义，布尔不当整数，result_sha256仍核未带摘要的完整canonical内容。

成功data精确：schema=qmt.history-bulk-artifact.v1、identity、source_session、source_profile、artifact_root_id、relative_root、manifest_path、manifest_sha256、rows、pages、bytes、importable。source_profile精确BF既有12字段及枚举；identity/B/SourceSession按HC1一致。artifact_root_id为部署冻结的canonical UUID，relative_root固定range_id+'--'+snapshot_id的单层目录名，直接交BF创建，不额外创建中间range父目录；manifest_path非空集为BF原qmi-manifest.json，manifest_sha256为实际SHA，空集两者null。rows=0仅空集且importable=false；非空rows>0/importable=true；pages>=1<=10000，rows<=1000000，bytes为实落CSV加manifest且有界非负整数。HTTP不暴露部署绝对路径、不回传历史行；调用方按原artifact_root_id解析原根并核原manifest SHA，不能用当前新root解释旧结果。

validate_bulk_source_profile(value)纯验证BF既有12字段、文本/单位/来源枚举并返回独立dict，artifact与后继部署准入复用该入口；不构造collector或创建文件。HD配置另外核BF七字段及与BP页/行/总量的联合上界，CSV和manifest预算各不超过原2MiB；完整HC2结果与HTTP base64/metadata分别核容量，不把artifact再发回源端。

validate_bulk_result(value,request=None,*,max_result_bytes,actual_binding=None)核完整字段、规范值/摘要、固定失败码和成功artifact；request存在核原request/range/snapshot/symbol/窗口，actual_binding存在核实际SourceSession。终态成功必须有完整结果来源；中断可保result_binding=null及原dispatch/admitted来源。校验返回独立dict。make_bulk_result后再验证完整输出，超容量拒绝，不能降成不合规的旧操作结果。

## HJ1 同一通信表与默认验证接缝

显式BulkBoundReadJournal继承原BoundReadJournal，继续独占同一SQLite文件和read_operations，零新增表/列；原body已包含身份/D。旧Host/Bound DTO仍拒bulk。纯默认算法仅提取可覆盖验证接缝，SQL/容量/绑定/锁序/原字节不分叉：

- HostReadJournal._interrupted_result(rid,operation,code)默认原interrupted；构造恢复dispatching、原claim及显式interrupt_bound都调用该接缝。Bulk仅为bulk操作生成HC2错误终态，旧操作委派父类。恢复hook所需profile/clock在super前完成准入和冻结，不依赖尚未初始化的Bound列或当前binding。
- BoundReadJournal._validate_bound_request(raw_request)默认原profile+BoundGatewayOperationRequest，返回至少具有request_id/operation_id/arguments属性的已验对象；Bulk为新body返回独立冻结描述，普通操作沿父实现。
- _admit_new_bound(raw_request,queue_timeout_ms)默认原UTC queue投影；在同事务幂等查重之后、INSERT之前调用。Bulk首次读取共享clock.seconds，严格now<D/queueD，剩余D与queue剩余不超过bulk_profile原total/queue预算；返回不晚于原queue_timeout_ms和共享queue剩余的UTC投影。已存在同body/B返回原记录，不重新授时效/ID，也不因D过期拒绝原身份查询。
- _queued_bound_failure(raw_request)默认None；Bulk仅在完整B匹配后核原共享D/queueD，返回expired/queue_timeout，原UTC expires_at仅可进一步缩短。失败沿同事务原_finish，中断不重发SDK。
- _normalize_bound_result(result)、_validate_bound_projection(request,result,actual_binding)、_validate_bound_response(value,request)默认原归一化/投影/外层校验；Bulk对新操作调用HC2，其余委派父类。bound.validate_response仅增加可信result_projection可选回调，默认仍原validate_read_result_projection；回调来自显式owner，不由wire选择。

submit_bound/claim_bound/get_bound可选keyword deadline=None；省略保原行为，显式值是原monotonic绝对D，事务前后及编码返回核同一D。首次提交COMMIT之后D到期可已落库，调用方只GET原ID；不得为了返回成功重授D。同ID并发初次POST只INSERT一次，第一份body/B为准。get_bound为新GET本身的读取D，不授旧任务重新执行或ACK。

BulkBoundReadJournal构造须显式clock对象（seconds可调用）和v5 read_profile；冻结准入profile及clock引用，不构造SDK或Host。校验器按operation选择，启动恢复的bulk dispatch中断同样合法；新B拒旧queued。普通同表记录沿原验证，中断原body保留，终态不改写为当前B。

## HD1 Host域线程和最终ACK边界

后继BulkHostControlLoop及显式HostBulkReadRuntime复用原常驻管理、Session、签名HTTP、ControlPeer及唯一HostDomainWorker。每证券一个业务记录、单未确认页；BF collector只能由原domain线程构造/accept/收口，I/O只交换有界独立JSON。配置以同一artifact_root_id和受管绝对根、source_profile/file_limits冻结；页base64加完整domain封套须在原4MiB域上限内，并与BP/BF预算联合验证。

中间页先BF耐久写验，domain结果才允许原future.ack。最终页先写验CSV/QMI，构造HC2小终态，在同domain调用finish_bound原事务；确认成功后I/O先清active，再ACK。空集无manifest但同样先提交空终态。COMMIT返回超D可能已成功，不ACK、不interrupt覆盖；后续原ID GET核事实，业务D过后不能补ACK。断连/管理close先保存已知交接，再由同domain收口collector资源；已terminal不得覆盖，dispatching仅按原中断规则终结。资源未确认保原runtime/collector/future和首异常，新代不得创建。

HC/HJ最少验收：精确body/完整结果/来源/文件引用、默认DTO拒bulk、QPC不冒充共享钟、整数上界、同body跨D幂等/改D冲突、同ID并发、queue UTC回拨仍不授时效、新B/重启中断、实际同表无schema扩张、默认Journal回归、COMMIT晚回后原GET保持成功及不覆写。HD实际域/ACK及WinSHM、C++和真实长窗另验，纯契约与Journal测试不授运行整链资格。
