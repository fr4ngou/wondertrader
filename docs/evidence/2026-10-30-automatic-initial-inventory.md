# WT启动时自动建立当前库存

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B NRT-R30自动主路径证据。状态：in-progress。[规格](../specs/native-realtime-strategy.md#nrt-r30-当前持仓初始库存与新的运行基准)及[唯一方案](../migration/retained-strategy-takeover-proposal.md)约束当前库存保留、旧交易退出与新的启用基准，操作见[手册](../runbooks/initial-inventory.md#wt启动时自动准备)。

## 实现与候选身份

新增initial_inventory_execution.py，由原execution_process固定工厂的显式initial_inventory部署项选择。原监督线程在原启动截止内运行原ManagedAccountScan四查询，取得数量/可卖、资金及订单/成交来源，再向原行情SDK查询标价；业务层不维护账本。prepare_initial_inventory生成C明确initial_inventory/baseline_at周期和原P23输入。当前原始查询的历史成交只用于来源/未决责任核对，不迁入策略或新交易文件。原Native加载前再核当次持仓及未决责任。

首次独占写准备根、原输入及BASELINE收据；原实际配置写在每代控制目录，原ready/关闭证明绑定实际配置SHA。正常resume只读核同源模板/来源配置/文件摘要，复用首次输入和基准；原clean按去掉recovery后的相同配置准入。原KV对实际held周期保留三字段编码，对initial_inventory保存明确status和baseline_at；部分增减保持原基准，清空后新买入沿原实际来源。原WRI runtime、Host协议、行情等待与WT框架源码保持。

C交接为build/initial-inventory-kernel-001/INTEGRATION-HANDOFF-001.json，SHA0f1f090bf755f01e1f5705cec6be8688e6c3f69befd5680cc1d47a6b44c64ef8；V1a8 wheel SHA3ad9a9de4c7605c1528fdc64b8ed927cf6fafc782542bfb69f746e907e67896e。运行侧execution依赖改为精确a8，App冻结读取角色保持。首普通七发行候选为build/ms-inventory-auto-install-001，开发本地版本0.1.0a12+initialinventoryauto.1；以根接受A12为基线，仅组合B四个文件和C新wheel。既有400期模型封存证据不重复运行。

## 首个自动主链

安装候选的values001公开API/CLI及显式C类型通过，Job54448 exit0/7.146秒；receipt001两类最终回读故障通过，Job50152 exit0/3.098秒；均树零、EOF、reader join及资源关闭。构建/安装Job54108 exit0/11.052秒，完整回收，普通RECORD和固定源按INSTALLATION.json登记。

native001已完成原Scan四查询和一次标价HTTP；标价替身漏发Content-Type，原SDK严格准入拒绝，尚未启动Native执行/写入金融文件。原输入及失败保留，外层Job57708 exit1但完整回收。后继只修正QA服务器声明application/json，原生产SDK验证保持。

native002从普通WT独立安装的原WRI/固定工厂启动，显式不传库存数量或takeover JSON。原Scan经独立Host/真实SHM/SDK替身四查询，行情SDK实际HTTP取得标价，原准备/Configured/P23/CTA/NSQ/标准Trader/WinSHM主链完成已有库存载入和两次正式计算。正常关闭后同金融根恢复，初始来源和baseline保持、数量阶段接续；原C类型沿KV保存。共16次SDK替身查询、金融写0，标价HTTP1次；实际券商调用0。原Native/WRI、两Host/Agent、server/proxy/行情线程均正常关闭；外层Job47692 exit0/65.193秒，树零、EOF、reader join、资源关闭通过。该场景为模型目标相符的一只沪深300初始库存，数量200/可卖200。

原执行与账户扫描使用根已接收Native006同批组件，指向root-account-read-retirement-001/native-packaging/final002的固定接口；各源成员SHA按原接口核后复制。当前SDK、行情标价及时间为明确隔离模型。主链入口运行前后九份QA及原执行组件摘要相符，实际副本与原关闭收据保留在各自独占根。

## 后继验证范围

主链后新增来源配置递归不可变快照、停止准备的明确取消路径，以及原执行Job已回收后仍续核准备Scan的close逻辑。后继普通版本.2正在重验，首.1主链不替代这些改动的关闭验证。可卖受限非沪深300初始化/恢复、准备期间停止、已存在/失配准备根、无当前标价/源和未知责任等随后核对；当前自动主链尚未最终封存、离线搬迁或独审。

当前交易日字段为现金ETF的启用日期，原P23用原ExecutionEnvironment日历核对。周末、跨日及来源实际交易日unknown保持明确范围，当前工作日模型不授这些资格。后继实际差额、新成交周期、首分析价、新日线/真实来源、统一候选及整个B继续。

## .2当前候选及停止/搬迁

普通后继ms-inventory-auto-install-002使用0.1.0a12+initialinventoryauto.2，四生产源与stage/wheel/安装完全绑定，七发行760条带摘要RECORD及依赖检查通过。Job41924 exit0/7.066秒；安装values002 Job69304/4.938秒、receipt002 Job20680/3.007秒均exit0且完整回收。

native003同版重验原计算后两代通过，16查询/SDK0，Job48360 exit0/49.797秒，全关闭。native004在SDK第一笔position查询已经进入时调用原执行owner.request_close，Scan正常受管回收，原执行进程尚未启动、无金融目录/BASELINE，ready=false、close=true、pending/forced=false，inventory_state=stopped_before_execution。仅1次SDK替身查询/0金融写，来源/HTTP及原监督者全部关闭，外层Job67776 exit0/8.377秒。该停止证据覆盖组件原公开API，WRI信号/准备过程中停止文件轮询分别属于外层调用范围。

native005同版由原Scan实际读取两只库存，其中510050总量200/可卖100，经自动标价/准备和原P23完成首次调度前停止及同根恢复；新baseline/原KV保持，原收益费用0、冻结量100。16查询/SDK0，标价一次，Job63900 exit0/24.514秒/全回收。该项仍只授受限可卖库存加载/恢复，不授受限可卖的NSQ调度。

ms-inventory-auto-package-001将七个原wheel、hash requirements、四源码及说明固定为17成员/590554字节ZIP，SHA8f4135c49a6dd1b34d58e05b09879f2ac3d84e05e4e446aa6f9e533398d3b588。实际解压、新E前缀require-hashes/offline安装、753摘要RECORD、依赖检查和安装API/CLI/收据故障通过；普通760与搬迁753的差为七个发行的direct_url元数据，产品源码逐项一致。外层Job30828 exit0/13.548秒，全回收。搬迁前缀的自动原生两代后继正在运行，最终独审与交接继续。文档检查通过。

## .3停止时效修正及最终主链后继

.2的搬迁原生native006已完成，16查询/SDK0/标价1及同根两代，Job35324 exit0/46.765秒且完整回收。native007沿同一搬迁安装省略initial_inventory配置，原held三字段元数据、一次SDK替身卖出及同根恢复通过，24查询/SDK1、Job10324 exit0/51.755秒，实际券商调用0。

独立审查定位自有新owner的停止时效P2：准备Scan已启动而执行Job尚未建立，首次短close到期后Scan才回收，原父close按“执行Job未建立”返回成功，再次空Scan回收也为true。根因在新owner尚未把Scan准入计入关闭时效。修正限定initial_inventory_execution.py，在原condition内登记Scan准入，独立确认首次stop截止内完整关闭资格；超期续回收保持stop_timeout，及时完成允许幂等成功。公共ManagedLocal/Scan、WT框架及金融计算保持原实现。

initial_inventory_close_deadline.py沿原start/监督线程/准备取消/close执行受控回归，省略无关文件准入并注入延迟Scan。red001的普通.2精确复现首次false、后两次true；green001的普通.3保持晚回收后false/stop_timeout、pending=false；及时关闭及后续幂等均true。两次外层Job16420 exit1、19332 exit0，树零/EOF/join/资源关闭均成立；这是受控生命周期回归，实际SDK停止另由native009覆盖。

后继普通ms-inventory-auto-install-003版本0.1.0a12+initialinventoryauto.3，四生产源按安装收据核同，七发行760摘要RECORD通过。Job75972 exit0/9.409秒。native008普通安装原自动两代通过，16查询/SDK0，Job57168 exit0/67.421秒；native009在实际SDK第一笔查询内停止，1查询/SDK0、原生执行未启动、Scan/pending/forced均false，Job63008 exit0/26.424秒；两案完整回收。

package002新ZIP仍为17成员，590996字节，SHA67a76f61cc505e05d140888381c45e416801497b59d542e23c849f8de67063ad；离线搬迁753摘要RECORD/API/CLI/收据故障通过，Job73140 exit0/30.669秒。该搬迁安装的native010自动原生两代通过，Job63740 exit0/52.024秒，完整回收。最终delta审查及固定交接继续；已验范围为当前库存新起点、初始化和恢复，后继实际差额、受限可卖调度、新成交周期、周末/跨日与真实来源仍单列待验。

## .4最早停止截止与固定交接

delta审查发现同一停止要求的并发窗口：较长close在Scan回收前读到旧截止，另一close期间收紧首次D；前者随后仍按旧值确认成功。最终确认的原condition内重新取min(局部截止,实时最早截止)，保持一处成功锁存。并发回归red002的.3为short=false/long=true，green002的.4为short=false/long=false、stop_timeout/pending=false，及时关闭三次true保持；外层Job42352 exit1与58328 exit0均完整回收。新回归QA副本与结果保存在两独占根。

普通install004使用0.1.0a12+initialinventoryauto.4，Job35472 exit0/11.354秒，七发行760摘要RECORD。package003离线搬迁753摘要RECORD、公开准备API/CLI/回读故障通过，Job63328 exit0/16.090秒；ZIP17成员/591030字节，SHAb4df8107e60091ae68ec613402e4b947eb6790fc12c48031e577675ab6461ce0。搬迁原自动两代native011通过，Job73800 exit0/52.047秒；实际SDK查询中停止native012通过，Job33972 exit0/12.155秒，均全回收。四生产源与原生身份按固定接口（外部历史/待归仓路径：`../../build/ms-inventory-auto-delivery-001/INTERFACE-003.json`）登记，最终delta输入为SOURCES004。旧版本/报告保留原身份，完整B及真实来源资格保持后续要求。

最终协议delta REVIEW-PROTOCOL-002 SHAece1a01299750c9965318f55a18b28a58774b16a97033970f8e2c593e7f2b061绑定259项，规范/规格delta REVIEW-EXECUTION-002 SHA4899984690dba6ba80cb9a5cdbc190d183183b9fc6f9ffafb7f7657ecfda46a7绑定313项，两项停止时效问题关闭，当前增量开放P1/P2为0。完整矩阵缺口继续单列。最终交接（外部历史/待归仓路径：`../../build/ms-inventory-auto-delivery-001/HANDOFF-002.json`）在SOURCES004的123项0漂移后固定四源/包、两报告及最终文档副本；HANDOFF001对演进正文的绑定由此取代。原full和先前开发版本保持原件。
