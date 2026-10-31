# 真实账户四查询与提交组后继

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-27。类型：开发验证后继。整体目标 active；本轮真实下单、撤单、生产切换及新增 WT 框架改动均为 0。

## 真实账户只读链

[前序四秒失败](2026-10-27-qmt-return-trace.md)保留。源码核实：四秒是诊断 Task 配置，可信来源执行上限五秒；传递、排队与结果采用同样消耗 Task 原期限。仅配置对照采用 request6000/round25000/native total30000/Managed36秒，HTTP单交换4000、close5000、业务原220秒/外Job240秒保持。原生/Python原30秒上限未改，每请求最多一次POST，首次失败停止后项，未知只沿原ID读取。该对照不承诺五项各耗尽六秒的最坏时序。

新诊断002只修自有fixture，启动/后验显式引用原003完整观察器bundle。001相对路径缺件的静态P2原件保留，离线原bridge准入已复现旧FileNotFound并证明新路径核九封件通过，未启动Host或SDK。配置审查（外部历史/待归仓路径：`../../build/qmt-account-budget-comparison-review-001/revision002/REPORT.md`）。

根自行启动并停止 GH_WT_MEMORY_VERIFY；同一终端正文SHA74f4bc16…7f46b保持，其他策略与原18017保持。四查询实际complete：position四行、account一行、order/deal空列表。字段availability累计44 present、5 unknown、0 invalid，未知字段未虚构值。Native自然exit0，Host自然exit0，root30284自然exit0/158.561秒（包含等待UI停止，不能当SDK或扫描耗时）；原App/Host/Native/外Job的整树归零、双EOF、reader join与资源关闭均成立，无forced。

安全trace6944事件、1005scope，四POST对应内部1..4四终态；submit-return→terminal-return分别3859/4953/4937/4906ms。四批采用成功证明本轮六秒配置正常路径，未证明传递迟滞的全部原因或生产通用资格。根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/BUDGET-REAL-ROOT.json`）、独立动态报告（外部历史/待归仓路径：`../../build/qmt-account-budget-real-review-001/REPORT.md`）。

已有两次health.last_tick间隔1003.567ms。当前Host/Agent的control_profile.poll_seconds及transport.poll_seconds均0.005、io_seconds均2；配置投影只读AST和固定数字白名单，不执行正文或发新HTTP/SDK，manifest在根前后与原固定摘要一致。tick投影（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/REAL-TICK-DELTA.json`）、配置投影（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/CURRENT-TIMING-ROOT.json`）。上述不证明查询期间回调恒准，也不定位SDK/GIL/后台事务各段耗时。

## 自有提交组验证

原纯状态RED保留。当前MSVC重捕获异常记录的内部地址不适合作为原异常透传oracle；专属测试改为原异常类型/token/tag及真实end入口/出口严格零分配计数。仅测试及最小单目标构建修订，未改变产品逻辑。新ssr-001仅生成State EXE7362581a…590a，原sg002产品DLL91af40ee…5fedd仅为参照、未重编。根39324自然exit0/116.446秒、五后验通过；新EXE14场景/129断言通过，根25520自然exit0，正常资源关闭。旧失败、旧EXE和原DLL保留。根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/STATE-ROOT.json`）、独立动态复核（外部历史/待归仓路径：`../../build/qmt-submission-state-build-independent-delta-002/dynamic-001/REPORT.md`）。

原默认12、共享内存3、未知提交与取消4，共19项兼容实际通过，所有受管进程正常退出/树0/EOF/join/资源闭，真实SDK0。新增group原首G01因测试把native原行为写成一次委派而失败，真实原生四tick为四委派/四笔各100；产品和C++未因此修改。新测试与其规格正在固定为G01 native4、G02/G03/G04 query_first1组，拆单与整组分别核，后续9项运输结果另行追加。原G01失败（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/SUITE-group-RED-ROOT.json`）。

## 历史源值接入与剩余

原WT Helper/DSB可保存double vol/money，自有canonical股/元/right转换与存储前置应分别表达。已接受[源值分钟历史合同](../specs/qmt-source-history.md)，复用现有CSV导入/原Helper/DSB/文件Reader，原值保留并返回单位/时间元数据，默认绑定现有成功导入收据，旧v1兼容。Python导入器/Reader和C++CLI v2开始实施，尚未验证；不新增数据库、不改WT或SHM业务协议。

当前无需用户决策或操作。继续完成新增运输/完整交易恢复、真实历史小样本及2021-11-01起全量1分钟导入、策略/保留业务与独立发行；本轮四查询通过不等于上述整体完成。

## 后继：运输九项与历史源值实测

新group四项、fault三项、cancel两项已实际通过；根三句柄21404/47384/55228均自然exit0，原180秒外预算内，无guard；原生子进程、fixture和整树/双EOF/join/资源关闭均确认。独立核2398原始byte块及175固定输入，原G01 RED保留；与已复核可复用的原19项合计28项，不表示旧19本次重跑。三组根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/ALL-TRANSPORT-ROOT.json`）、独立复核（外部历史/待归仓路径：`../../build/qmt-submission-transport-dynamic-review-003/REPORT.md`）。纯状态14场景/129断言另计，完整交易恢复与真实下撤单不在本结论内。

源值Python候选已实现：QMI manifest/sidecar v2保留源double及时间标签，复用原Helper/DSB/文件ABI；新增read_source_store返回独立SourceHistoryBar和SourceHistoryMetadata，绑定原成功导入收据，旧canonical入口明确拒绝源值。量额/区间可为unknown，coverage保持unknown；无需新增数据库或WT框架修改。

首轮26方法实际出现Windows CLI机器输出编码错误：24通过、1既有symlink权限skip、1错误；错误由GBK stderr被UTF-8接收方解码触发，原RED及根句柄64432正常收口记录保留。revision002仅将三个JSON结果分支统一ensure_ascii=True，保留Unicode JSON原义并新增实际GBK子进程三分支回归，旧26方法逐字保留。新根624自然exit0/6.533秒，Importer27方法中26通过/1既有权限skip；根58212自然exit0/2.650秒，Reader9/9通过，共35通过、1skip。两次均outer90/root100原预算、正常资源闭合、源码四份与实际DLL三份前后核SHA，真实SDK0。原失败根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-IMPORTER-RED-ROOT.json`）、新根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-PYTHON-ROOT-002.json`）、完整Python静审（外部历史/待归仓路径：`../../build/qmt-source-history-python-review-001/REPORT.md`）、编码delta及有限动态独审（外部历史/待归仓路径：`../../build/qmt-importer-cli-encoding-independent-002/REPORT.md`）。

同版WtDtHelper.dll为59696d42…45a，GuanhengNativeBarFile.dll为4f5e2696…62c，WtDataStorage.dll为12591cf9…838，来自已核repair-001/build-002。原值roundtrip含分数量、零量正额和unknown标签；实际文件SHA/回读、单侧元数据/DSB篡改、重复或错配收据、读取期间变化、整套替换的独立摘要条件及旧v1兼容均由上述方法覆盖。此处数据全部为合成材料，真实QMT小样本及全量2021-11-01起导入仍待执行。

C++导出v2及12项profile用例已实现并独立full，无本次新增必要P1/P2，正在准备固定上游隔离编译。原继承的末发布截止复核、flow相对timeout/输出与清理首因、标签校验交集限制已列明，不把profile测试资格外推为完整发行/策略消费。真实历史三能力pair需按实际Host解释器身份生成并由统一App管理；目前成功四查询pair仅含账户及快照两能力，不据此声称历史已可用。CLI独审（外部历史/待归仓路径：`../../build/qmt-source-history-cli-independent-001/REPORT.md`）。

源值历史真实闭环已形成后继：新C++、12方法/46CLI、两条合成文件链及真实QMT两分钟→原Helper/DSB/sourceReader通过；详细当前资格与剩余见[后继实测](2026-10-27-qmt-source-history-native.md)。上方阶段观察保留。
