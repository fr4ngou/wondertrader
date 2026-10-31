# 当前库存清仓后的财务可卖观察

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B开发验证证据。状态：affected-main-reviewed / whole-module-pending-verification。范围：唯一共振1.1.2、当前库存新起点、原WT原生账本与SDK替身；完整模块和统一候选仍在验收。适用规格为[NRT-R30/R31](../specs/native-realtime-strategy.md#nrt-r31-实时执行阶段按券商实际数量确认)，初始库存要求沿[唯一方案](../migration/retained-strategy-takeover-proposal.md)。

## 根因与实现

当前库存200股、可卖100股，首次调度等待可卖。显式未来行情日期与券商可卖改为200的隔离模型随后实际卖出200股，并产生对应成交。原失败现场已经空仓，WT文件为volume=0、frozen=100，原财务观察返回raw_valid=-100。自有execution_configured._capture在判断财务实际空仓之后，仍对这个未使用的理论可卖字段执行非负数量校验，抛出native_quantity，终止后续完整回调。

责任层修改为：财务实际空仓的可卖量为0；原raw_valid要求数值有限，并原样保留于raw_positions。有持仓时继续核非负整数及可卖不超过总量。执行观察的数量、可卖仍采用当次券商完整P。WT持仓、冻结量、成本、费用和损益保持原实现。生产变化仅execution_configured.py，SHA `4bfc570ea9d89a463a5db96593c2384214d772570b3c726d9531a1e864768772`；本轮新增WT核心行为0，真实券商操作0。

原两个失败模型分别保留：第一个模型未触发下一次计算，SDK0；第二个实际卖200、源成交1笔，随后在上述自有财务校验退出。原物理清理均完成，业务正常关闭资格分别按原失败登记。`build/ms-inventory-reference-delivery-001/FAILURE-BOUNDARY-001.json`绑定原件和直接观察；同次未来tick与实际wall clock没有建立完整次日会话证明，根因结论限自有观察转换。

## 安装后实际主链

普通安装0.1.0a12+inventorysession.2及搬迁安装分别运行原Factory/CTA/Reader/唯一算法/NSQ/执行器/Adapter/WinSHM/Host/Agent。均先waiting_sellable，再由原查询确认可卖200，实际卖200：各1次SDK替身调用、1笔映射成交、2条Host事件，源/Host/策略的成交ID集合相等。最终converged、执行与财务观察均空仓/可卖0，清仓同次诊断raw_valid=-100保持。随后各自同根正常停止及恢复，原目标/周期/NAV/资金/费用保持，恢复新增SDK0。

| 原件 | 实际结果 |
|---|---|
| `build/ms-inventory-release-native-003`，外Job8256 | exit0，46.837秒，普通安装两代正常关闭 |
| `build/ms-inventory-release-native-004`，外Job48672 | exit0，46.654秒，搬迁安装两代正常关闭 |
| `build/ms-flat-theory-proof-002/PROOF-001.json` | 冷只读核对原金融文件、查询先于SDK、回报身份、关闭及安装身份，无新增查询或交易 |

两代各自clean与closed.v2匹配PID/control_id，closed/ok/recovery_ready成立，exit0、资源关闭；WRI外层进程树归零、EOF、reader join及资源关闭。第一代清仓后-100由原发布直接核对；第二代恢复后的最终原WT文件volume=0/frozen=0，两个阶段按原时间分别记录。

原费用配置卖出200×0.02=4元，WT总profit/dynamic profit均0、费用4，原PnL=-4，NAV从120000变为119996；恢复保持。SDK替身available按毛成交额变化、commission为0，券商净费用与净可用资金尚未验收。未来日期行情+实际wall clock的本模型只验券商可卖变化及清仓观察，完整次日原生会话/交易前解冻仍为gap。

## 定向回归与首分析参考价

`flat_theory_availability.py`直接读取原失败现场，旧安装拒绝native_quantity，新安装通过8项：空仓负值/正值、未执行目标、正常有仓可卖、持仓负数/超过总量、非有限值和非法entry配对。新绿例在`build/ms-flat-theory-green-003`，旧红例在`build/ms-flat-theory-red-002`；两外Job均exit0且完整回收。`ms-broker-execution-matrix-008`复用同次正式纯核输出，运行原完整callback/NSQ/KV并通过已有实际数量确认/部分卖出/可卖/挂单/新代际矩阵；它授回调行为资格，SDK操作0。

首根合格分析价使用明确的新基准输入模型，当前库存年龄0、旧峰值和退出记忆为空。前一已审.1安装在收盘前1秒/同一秒/后1秒三案通过：只有收盘前形成90元参考价；同秒和后1秒保持空，三案均原生正常两代、SDK0。最终.2安装再次跑通收盘前模型和同根恢复，外Job58084 exit0/44.865秒。证明分别为`build/ms-inventory-reference-delivery-001/REFERENCE-PROOF-001.json`及`REFERENCE-PROOF-002.json`。这些是安装后完整原生消费者的显式起点模型；自动生产者真实时钟的新日分析发布尚待统一链验收。

## 制品、来源及接口

固定检查点（外部历史/待归仓路径：`../../build/ms-inventory-reference-delivery-001/INTEGRATION-CHECKPOINT-002.json`）绑定普通23发行/1355条摘要RECORD，搬迁23发行/1332条摘要RECORD及57成员ZIP。制品`build/ms-inventory-session-package-002/B-INVENTORY-SESSION-002.zip` SHA `3099242d2f87e9010e17ea2b8dfacfef326caae2baf1c5913f55fbc58cec6780`；安装后原CLI、离线校验、搬迁主链及运行后RECORD/ZIP/26成员Native均无漂移。各安装生成项按各自RECORD核对；共同产品模块保持精确身份。

`FULL-NATIVE-ORIGINS-002.json`登记最终主链实际加载的全部8个执行EXE/DLL及独立Scan进程2个组件。Host/Runtime使用c05005原生日期消费后继，Standard使用ef04最终候选；其原Native006链接源和原库依赖保持，Reader/Helper来自明确的400源冻结构建，QA行情Parser标为测试专用。原生640及Reader400源的来源核验沿原记录复用，本轮核最终组件与已绑定来源摘要，未重跑整个源码审计。

统一候选须使用配套Host+Runtime+inventorysession.2 wheel，沿固定Standard/Host索引及C V1a8，不可仅替换Standard。自动库存仍由同次WT会话日历确定账本日期，facts.v2不猜自然日；旧v1显式日期严格核对。该三源变化与普通/搬迁卖200买200、费用6及可卖等待的.1四报告资格沿[前一证据](2026-10-31-initial-inventory-evolution.md)保留，不将旧安装实跑称为.2全量重跑。

最终65份冻结输入位于`build/ms-flat-theory-review-001/SOURCES-003.json`，影响源、旧源、规格、实际回归、来源和资格检查点交两位独立审查。`FULL-NATIVE-ORIGINS-003.json`同时将Runner/Runtime便利别名对齐已核最终运行目录；002清单及其相同文件摘要保留。最新检查点004（外部历史/待归仓路径：`../../build/ms-inventory-reference-delivery-001/INTEGRATION-CHECKPOINT-004.json`）汇总最终来源及下述新失败。

最终.2另补跑unknown同根重启场景。旧QA手写v1自然日材料先在CTA初始化拒绝，SDK0；后继仅将冻结QA字典改用已支持的v2并移除外部trading_date，生产源码/仓库QA保持。后继实际原生启动及SDK1进入，原Journal保留unknown身份且没有clean；第一代关闭在原10秒出现stop_timeout/pending/forced，第二代未启动。外Job71180 exit1，进程树零、EOF/join及资源关闭全部完成；业务正常关闭资格未通过。直接原件及`build/ms-final-unknown-restart-002/FAILURE-BOUNDARY-001.json`保留，后续沿自有关闭链定位，不推断WT根因。

完整次日会话、真实净费用、自动实时新日分析、统一SHM当前报价/历史/账户主链、最终撤单/多策略/异常组合及模块逐项完成核验继续；整体B active。生产切换与真实交易保持原授权边界。

## 最终独立审查与交付

协议001报告SHA `6b848a93a529b9e19b9a8b3ef2205df38f186875e96b23c18f348875fee08a9f`，绑定原58输入及668摘要；协议002保留001原件，新增unknown失败和检查点004的92绑定，SHA `11bcbfa32ec1f6aa28c85f6ed6cd2a21e3b0907aa858daf36ebcbda265179134`。执行001独立核最终65输入、207绑定，SHA `5b78d44d41751420900707afb7e45b524202652ae6285fb646e7ca0f73b855e0`。三报告对本轮实现变化未发现新增P1/P2，明确保留unknown首次停止失败/第二代未启动等模块缺口；审查不增加运行或真实交易资格。

最终HANDOFF-001（外部历史/待归仓路径：`../../build/ms-inventory-reference-delivery-001/HANDOFF-001.json`） SHA `d74f3cf803b0edcdd593844e52c618cf3e62e1beac98e2d02a29e8149c912b5c`绑定生产源、23发行版本、Native完整来源、原普通/搬迁回归、制品及三审查。交接脚本核所有65冻结原件/副本与报告内969摘要引用，外Job42196 exit0/0.525秒且物理回收完整。首次交接脚本只识别统一open_P1/P2字段而拒绝执行报告的分级finding数组，尚未写交接文件；后继按实际报告结构核空数组后通过，该工具失败保持原件。

交接状态ready_for_candidate_development=true、ready_for_root_candidate_integration=false、whole_module_qualified=false；固定材料可用于根当前库存主线的开发装配，完整集成资格继续待验。旧broker目录新增INTEGRATION-SUCCESSOR-004指向本后继，旧.1及broker交接保持原件。后继优先定位自有关闭链同次停止阶段，保持原10秒截止与原命令/金融根，不据停止现象研究或修改WT线程框架。

## 独立SDK净费用与资金观察后继

沿[P28固定搬迁安装](2026-10-31-unknown-write-stop.md)补充`build/ms-inventory-net-fees-native-003`，不修改产品、WT或原费用计算。SDK替身独立完成卖200/买200并分别扣4元/2元费用，以实际替身现金加当前库存标价给出账户净资产；原WT自行计算费用及收益，QA不计算或写入策略目标和理论账本。当前只是明确的两笔费用模型，真实券商费用、税项及部分成交最低费另验。

源端初始账户净资产100000元，成交后99994元、可用79994元、commission字段6元。原配置策略预算为120000元，WT NAV119994元、理论现金99994元、PnL为-6元；两者本期收益变化均-6元，保留原预算与账户起始资产的20000元差额，不把两个不同口径的总额强行核为相等。原数量/可卖继续来自券商观察，持仓市值及费用没有重复扣计。

原P/成交达到converged时，账户A仍可能是较早快照。002旧QA在该阶段立即断言净可用而失败：P/成交已经完成，A仍为卖出后的99996元。003在原185秒总界内继续推进原Source及Parser，等原账户查询更新后再核；没有从QA直接增加账户请求或产生额外委托。首个P收敛决策序号8，资金更新后决策序号9，新增正常观察1轮。

最终SDK2/Native映射2/Host事件4，源端正常ACK/gap为空。原同金融根正常两代，恢复SDK仍为2、没有重复交易；两份原closed.v2均ok/recovery_ready/exit0。外Job12292 exit0/51.895秒，Host/Source/server/proxy及执行子进程树零、EOF、reader join、资源关闭。已安装模块来源、原QA、包文件摘要均无漂移，P28制品身份保持；初始旧持仓历史仍未导入。

净费用证明（外部历史/待归仓路径：`../../build/ms-inventory-net-fees-proof-003/PROOF-001.json`） SHA `1e3976f1d509dc09a5e011adc87f43d45b7c140876c23582324fd9149ed35ef5`绑定16项原件及P28交接。该后继只新增隔离验证范围，完整统一调仓吞吐、真实次日/自动分析、实际券商费用、冷重启/unknown解除及整个B继续待验，真实下撤单与生产切换保持原授权边界。

独立费用执行审查（外部历史/待归仓路径：`../../build/ms-inventory-net-fees-proof-003/REVIEW-EXECUTION-001.json`） SHA `c4c5baf62fdfb849cf41c9fc78a11e5b91c36aa180c0d74f881ac348c13e6035`核56项绑定、新增P1/P2为0，确认2笔SDK/2笔精确成交映射/4条Host事件、原预算差额和两代正常恢复。最终输入与范围已进入验证交接（外部历史/待归仓路径：`../../build/ms-b-io-net-fee-delivery-001/HANDOFF-001.json`），复用原P28制品，本次新增产品和WT修改均0。
