# 2026-10-25 标准 TraderQMT 同实例读取运输恢复

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：限定验证记录。状态：pending-verification。关联[唯一规格 SEV-R13](../specs/native-qmt-standard-events.md#sev-r13-同实例事件读取有限运输恢复accepted实施)。本页覆盖同实例、有效事件页交付前的读取运输恢复；首次查询与实时交接继续独立验收。

## 实现与根因

Common 从实际 WinHTTP 原生错误与合法 Content-Length 的短正文形成类型化失败事实，只允许固定运输类别；事件专用 prepare 的 Binding、Status 两个 GET 与 Page 只读 POST 传播同一事实，正常本地 stop/detach 使用独立控制结果。Standard 保留原链截止、FIFO、游标、交付索引及预算，运输恢复受原 cadence 和实际排空限制。下单与撤单不增加重发。

独立审查定位并修正两处自有实现时序：正常控制完成值晚于原截止由 owner 取出时仍须超时；成功页在 Common 返回后晚于原截止发布时，worker 须在原发布锁内先关闭写入与后继任务。两个真实时序回归已通过，正常 DLL 无测试门导出。

## 构建与实际结果

固定上游 08b230dd05facf6d650d949bfe51054115a2ecb1 的 323 个原始文件，在三轮构建中逐字节核同；自有输入每轮 141 文件也与清单相同。Common 两目标、Standard 初轮十二目标、修正后四目标实际编译通过。26 项受保护框架文件相对本轮既有基线未变，该结论保留既有已批准差异的事实。

| 批次 | 实际结果 | 范围与限制 |
|---|---|---|
| common-runtime-002 / timeout-fixture-004 | 原批次11方法10通过、1失败；最终10+2覆盖12个唯一方法 | 原失败的模拟超时实际产生12152，修测试为真实12002；004运输与构造失败资源负例2/2通过，原failed批次保留 |
| standard-runtime-001 | 9方法，8通过、1 ERROR；17场景中16通过 | Binding/Status/Page恢复、九种非200、坏页、原截止及两晚发布时序通过；旧回调阻塞门15秒退出92，未生成native结果，该场景不授通过 |
| standard-regression-001 | 31/31，0skip | 原查询、事件、SHM完整字段链；正常Standard002与原固定探针 |
| unknown-regression-001 | 4/4，0skip | 未知委托原身份核查、定向取消、解绑、容量 |
| state-regression-001 | 49场景、2126断言 | 原内部状态回归，合成输入，无真实网络副作用 |
| common-compat-001 | 41/41，0skip | 当前Common重编旧客户端/故障/订单查询/八上下文/账户投影；与前述Common方法有重合，不累加冒充唯一总数 |

已完成控制器均无可见控制台、创建期Job准入、原总截止、输出EOF、tree0、reader join和实际资源关闭；Standard失败场景的原生进程exit92、forced=false、reaped=true亦保存。全部SDK为替身，真实SDK调用0。测试失败原件与后继修复分开登记。

## 输入身份与独立审查

最终Standard002正常 DLL SHA256 67860d8ba2cae3138a730fdbdb12b51ee0d458069f6deb7397914d40d6fb7005；隔离故障DLL为4632d3789c2257ef664a6b2a09ad09665a84839a3c1380a17cd0bf28be642dfa。Standard cpp为3f34a0a55167155704e155767ae13363ce55db18d97e2a4ade055e73596510cf，头文件保持f518c687ed98835a6e4c29aabe5e3c468f952c9c5facdb0371381a27a048964a。Common HTTP cpp为4f52d046274fbc6c544a86af70784c5ed37598989f4fa0b38703479097d461c2，Trade cpp为f4cf2cacda08cd69be44b97f178c416b288a1fe132e67c6d289d5f0fc41c7ee5。

设计、Common full/fixture004、Standard full/revision002、wiring/final macro delta均独立静态审查；两项Standard原截止P2静态闭合，无新增已确认P1/P2。根已复核Standard revision002的27份原件字节，实际PE导出核正常DLL无任何HTTP/事件测试门，故障DLL保有专用门。静态审查不替代缺失动态矩阵。

根验证原件：build/guanheng-workspace/qmt-event-read-retry-verification-001；构建为qmt-event-read-retry-common-fixed-001及standard-fixed-001/002；运行目录分别为qmt-event-read-retry-standard-runtime-001、standard-regression-001、unknown-regression-001、state-regression-001、common-compat-001。审查原件为build/qmt-event-read-retry-common-review-001、qmt-event-read-retry-standard-review-001/revision002、qmt-event-read-retry-wiring-review-001/FINAL-MACRO-DELTA-001。

## 未完成与风险

真实session卸载Pending与FIFO进展测试正在改用已有非阻塞session保留接缝；原阻塞callback测试不改记为通过。完整R13矩阵尚缺前缀后恢复/跨seq重复、满队列至原截止、三跳stop/detach交错、跨关闭截止保借用、精确容量/分配失败，以及有效页后Resolve/SPI故障。

首次/新源/跨进程及重连R8依旧缺共同查询/回报覆盖事实。原WT历史DEAL查询与实时trade对统计和持仓的职责不同，重连再次四查询也不能直接当作原状态清空；正在以固定上游交错反例继续核验。生产Factory保持原入口，event_consumption_complete=0。R5、完整故障/父死亡、2021-11-01起分钟覆盖、全部保留业务与独立安装发行继续；整体目标active，无新增用户即时决策阻塞。

## 同日后继：revision003真实session卸载Pending

仅更改测试：使用原有kind4保留真实HINTERNET session，原UNLOAD_NOTIFY_EVENT与drain(0)自行产生Pending；普通queryAccount在同FIFO真实返回SPI后，经后续完成值及至少600ms保留，实际WinHttpCloseHandle释放，再由原排空/join路径收回。Standard/Common产品字节未变。旧阻塞callback退出92仍保持原失败及未通过资格。

probe-fixed-003仅重编NqpStandardEventReadRetryProbe，SHA256 e606b735cf2392af03574afea9fcb5dcecc411b3b860a242f97fb11f36db5962；原固定上游323、自有141份逐字节核同。runtime-003使用该probe与原Standard002正常/故障DLL，13/13方法、0失败/错误/skip，67.154秒；其中9方法17场景是本轮恢复矩阵，另4方法为受影响共享夹具回归。真实Host/HMAC/Win32 SHM、原Adapter金融与源事务断言均保持。控制器code0、无可见console、Job创建期准入、输出EOF、tree0、reader join与资源关闭实际成立。

独立revision003 delta新增已确认P1/P2=0：报告SHA f0d6fdb97ee70d835914334b973feb3f03463f1cd30c289c2c2da5b242fdd585，清单SHA9e03fa0e4a5752a0f3dfbb5cc06a79a477f4ebb757db56e11648d79dea98d05d。三测试源码为probe395ab8e0d8188ced96d2855f0fb1c9359fe16179e55a5e7a1f7eeec6d56bb5dc、retry Python f58c9123f3392984dc2deee3d4f43bb395213ca038a22e24cf375a0833be3784、shared Python a6b347bd01460254134d4e3d709d3bc48254365d03ef724b8d75b55f70ffceee。共享夹具只新增缺原生结果时先报告child真实exit/forced/reaped，原金融与资源oracle保留。

当前限定恢复场景已通过，完整R13仍pending-verification。晚REQUEST_ERROR/READ_COMPLETE/HANDLE_CLOSING跨关闭截止、前缀后恢复/重复、满队列/精确容量、全部stop/detach及后继Resolve/SPI异常仍待验证；下一片已进入前缀恢复测试与固定原WT的R8查询/回报交错反例。此后继不授真实SDK或首次/重连生产资格。

## 同日后继：R13-B已投前缀后断流恢复

前缀用例使用原Adapter与真实Host/HMAC/SHM源链：前两项订单/成交已返回SPI、持仓120/可用100/undone80，实际after_seq=2空页被观察后才由原Adapter取消。原源线程再发同成交重复、新取消与旧订单重复；代理仅截断真实Host非空页。恢复仍同完整请求，实际恢复页包含seq3重复成交与seq4新取消，最终持仓120、可用100、undone0、order SPI2/trade SPI1。源持久ACK5与WT应用分别检查。私有read/handled/Returned、原链D和本次native_error未直接采样，不用时间戳或本地序号冒充来源cut。

固定prefix002仅编译NqpStandardEventPrefixProbe，SHA256 88a0dd67323aa998bbe3812f0bc1f43dd0dd767d9aeeed18236d5fc6114cf307；323上游、143自有输入根核原字节均同。复用Standard002正常DLL。prefix-runtime-001实跑14方法，原13全部通过，新前缀父端prepare顺序断言失败；其Native金融与关闭均通过。根因是Windows相同monotonic时间戳把后继Resolve误纳恢复窗口。只改独立Python，用真实单HTTPServer append索引表达顺序，时钟保留cadence检查；新同tick回归同时拒损坏索引。prefix-runtime-002两方法2/2、0skip、4.506秒，通过真实前缀与纯排序根因例；原failed批次保留，最终按13+2覆盖15唯一方法。

独立prefix full与排序delta均封存；原测试P2静态闭合，最终无新增已确认P1/P2。full报告SHA1e893c64a7b65620e035c2758adf3c2384f44cf9bdd1b373e2e8e9e7370781bf，delta报告SHAa880edc1564f432dbfa337fac8ddd9b64a9b538e9f9376baa385451beb84d822；最终Python SHA da03a6dfb0309da51d37e70dd6850b95716eff9a5be30d366688ed4635f8e76c。根核full40份原件，并保存后继实际控制器tree0/EOF/join/资源闭合。Common原未知委托七方法7/7也以本轮Common重新编译的DLL通过。

一次prefix构建在架构预检停止，原进程实际machine值未采集，触发原因仍unknown；隔离原生诊断和重跑同解释器采证均为AMD64/64位/原生architecture9，原检查规则保持且后继构建通过。原预检失败及诊断保存在qmt-event-read-retry-prefix-verification-001，不回写为编译失败或已定位的产品问题。

前缀测试、shared默认回调hook、接线分别冻结：spec8f3e20d768c802d9ad8dfeb991dd92eb1d1e19be03d5465b05d267a0f14bde88；shared295a73fdf847e92fd88a8baa0657115f19d68d7e17ceaee74f37f11418a26900；Native971c93e36ebb88de9b64200005afe6e176a88de3ff56bb9e7d638a046886db41。产品仍同Standard002与Common原字节，26项框架保护基线未新增差异。完整R13矩阵及生产首次/重连R8继续；固定原WT交错反例专用probe正在开发/接编译，尚无新动态结论。


## 2026-10-25 D4：完成预算与原事件截止

accepted范围见[SEV-R13-D](../specs/native-qmt-standard-events.md#sev-r13-d-fifo名额原截止与owner公平accepted-验证范围)。旧Standard3f34在普通Resolve持续占满pump(1)时，尾部delivered<limit门跳过ReadRetryWait原D维护。原版确定性红灯（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-fifo-baseline-001/result.json`）保留：严格超过事件D但仍早于普通Q1的D，pump返回1且没有timeout/fence。

产品仅在自有Standard增加owner截止维护，独立于完成额度；有效lifecycle的ReadRetryWait/PageReady先结算已完成链再判原D，锁外fail。stop/detach不制造新超时；ReadInFlight/ResolveInFlight沿原Completion真实错误处理；不enqueue、不改准入额度或延长D。移除本次新增18行后与原3f34逐字一致。最终产品SHA222810e30113cd4e5df57e27a357076f219ea378ba19a894a65d922e76a0c7cc。

固定构建002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-fifo-fixed-002/result.json`）编出normal d7259a9c1c319ce4efd7aba0fa7a7d995298cdb8a0530cd92ea62bd38912cc89、fault 18ea96a217b912065ef10b331edd1ca021f195687ab14722c95871fd41c86e34及私有状态探针；最终探针003（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-fifo-probe-fixed-003/result.json`）SHA39c951942dfa3f82e93bbb44ef9f6d2fb1ead35fa6a043e889c308ac4dbf6dbc。两构建各147自有/323固定上游原件及制品摘要均根核一致。26项既有框架保护基线本轮未改，见复核（外部历史/待归仓路径：`../../build/guanheng-workspace/migration-slice-verification-20261025-001/VERIFIED.json`）。

最终四方法4/4（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-fifo-runtime-004/result.json`）覆盖普通ready遮蔽、真实账户SPI回调入D前出D后、晚pump前detach、账户SPI内detach后跨D；两种正常detach保持正常抑制。回调跨界以首次真实账户通知推导事件D下界、实际故障观察推导上界，同时保留普通Q1原D；前置窗口不足即失败。真实Agent/SHM/Host/R21及固定Adapter参与，SDK0，实际close/delete/drain/join。

同normal产品旧标准31/31（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-fifo-standard-regression-001/result.json`）、原9重试+2前缀11/11（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-fifo-recovery-regression-001/result.json`）通过。私有状态49场景2126断言通过；本轮未知委托公开回归3/4，audit-cancel触及fixture_original_deadline且清理报告4项失败，尚在沿原记录定位，不能沿旧4/4证据把新一批称通过，见失败原件（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-fifo-unknown-regression-001/tests.log`）。外层Job实际回收与fixture内部清理通过分别表达。

首次runtime002因根未创建输出根目录4项前置失败；runtime003的原D4/detach通过，两tail实际前置失败fifo_tail_ready_before_event_lower，Python KeyError遮蔽。revision003将下界改为可证的初次账户通知时刻、提前落时序并先检查真实native退出，未放松严格跨D断言；原件保留。产品delta002（外部历史/待归仓路径：`../../build/qmt-event-read-retry-fifo-review-001/revision002/REVIEW.md`）及测试delta003（外部历史/待归仓路径：`../../build/qmt-event-read-retry-fifo-review-001/revision003/REVIEW.md`）独立审查P1/P2新增0，最终26原件根核同。

D1–D3满16 outstanding、cadence512准入及owner CPU取证仍在开发；R13全矩阵/R8生产首次及重连交接继续，Factory原入口、event_consumption_complete=0。上述局部结果不授完整实盘或整体迁移资格。
