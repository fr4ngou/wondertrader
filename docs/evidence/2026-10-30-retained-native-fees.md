# 正式1.1.2实时费用准入与原生卖出费用

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B开发证据。状态：NRT-R25费用能力准入和限定业务链已验，独审/交付范围见下文；完整费用、稳定关闭及模块继续。要求沿[实时费用规格](../specs/native-realtime-strategy.md#nrt-r25-原生实时费用能力与策略资本)。全部新增运行、缓存、临时文件和制品位于E盘。

## 根因与实现

固定上游08b230dd的HisDataReplayer读取minfee并调用apply_fee_minimum，实时WTSCommodityInfo::setFeeRates/calcFee只接byvolume和open/close/closetoday。自有execution_facts此前把BT的费用配置准入原样用于实时，接受正minfee和缺品种费用项；实际实时引擎不应用该最低费用，缺品种费用则沿原默认零值。

旧R24普通安装的minimum-old002是正式运行反例：原配置minfee7，唯一1.1.2由原Factory/CTA/NSQ/股票执行器/Adapter/WinSHM实际卖200@90，原CSV/fund/flag0费用4元，SDK替身账户查询按声明最低费用返回commission7元。两个原owner分别保留其事实，差额3元没有被人工补入任一账本；FEE-PROOF.passed=false，明确失败。

生产修改仅在[execution_facts.py](../../apps/wt_runtime/guanheng_wt_runtime/execution_facts.py)：每配置品种必须有费用项，正minfee在原CtaRuntime构造前明确拒绝；缺省/0及原费率语义保持。原BT接缝strategy_replay_facts保持原字节并继续接受合法正minfee。没有新增费用计算、金融账本或WT框架源码变化，原生库未重编。实时最低费用能力继续作为完整模块缺口。

## 普通安装与主链

根build/ms-retained-fees-001。原R23 native002的23文件保持，普通venv --without-pip离线六发行、732条hashed RECORD，唯一1.1.2/a7，观衡/Web未安装。保留R24与独立回测全部16个B模块，只更新实时费用准入。

| 身份 | SHA256 |
| --- | --- |
| INSTALLATION-001.json | 2c70ce44fd9985a0e6a6bdc3a099b14359b2a0166e29f6f385d83f1d67d18fea |
| Runtime开发wheel | eebe3e94a17f874a751d762c0a0bc70e8f93a6f258ab3acabf128277a15489db |
| MAIN-SUMMARY-001.json | cdeccdbe3de49375384b5f684efa47bce08150fa9cde43896f75823519ef997d |
| admission001 RESULT.json | fd69688a164f0687dcced8d47e715e820aa36190ce7b4d5d87cb213a0df2c608 |

R25-C1各案都从正式独立WT入口运行。初始模型明确本金120000元、原持仓510050/510300各200份、原WT接管mark分别90/100元，模型现金82000元，策略费用预留20元。原核触发510050清仓，原数量核保持510300的200份；原股票算法经SDK替身仅卖一次200。券商commission/balance/available由源模型独立返回；理论NAV/现金由原WT损益及完整理论市值派生。价格与账户均为隔离模型。

| 案例 | 原生及查询业务事实 | 完整关闭 |
| --- | --- | --- |
| amount001 | 按成交金额费率0.0002，卖18000元；原费用3.60、flag0=-3.6、NAV119996.4、现金99996.4；源commission3.6/available99996.4，原核及NSQ收敛 | 同次final closed.v2与clean、实际子进程exit0及内外Job/EOF/join/资源关闭 |
| volume002 | 按份费率0.02，卖200份；原费用4、flag0=-4、NAV119996、现金99996；源commission4/available99996，原核及NSQ收敛 | 同次c0005、记录的wrapper退出2，成功clean未发；物理回收成立，正常关闭资格失败 |
| minimum-refusal002 | 正minfee7在账户/原生运行初始化前拒绝，源查询0/SDK0/callback0、未创建stradata | 预期拒绝，不授正常业务运行；QA记录sold0/real_algorithm=false，受管失败与外部资源回收分别保持 |

两正例FEE-PROOF采证时各24查询；最终POSTFLIGHT各27查询/1SDK/2callback，两个时点分别保留。原fund JSON及trades.csv在financial-model-snapshots逐字保存，摘要与采证时、最终原文件三方一致。原件与退出层级沿主链摘要（外部历史/待归仓路径：`../../build/ms-retained-fees-001/MAIN-SUMMARY-001.json`）及独立审查读取，不把wrapper退出码赋给未核实的WRI/native PID。

首轮minimum-old001在等待账户观察交付前即核available失败；后继minimum-old002取得真正费用反例。volume001在五次快速模拟分钟内未等到SPI观察发布，费用原件已有但整体失败；volume002按实际8秒截止等待原owner推进再触发原调度，未改变生产代码/查询规则。qa-main001/002/003各十个准确文件按当时输入摘要冻结，最后一代仅修正预期拒绝的RESULT标签。所有失败原件保留，未用重启覆盖。

## 边界与当前资格

R25-C2共13组安装准入回归：缺省、0、正7、小正值、负值、bool、字符串、null、非有限数、缺SSE/缺SZSE/空费用表、未知字段；同时核旧实时/新实时及未改BT准入。旧实时接受正minfee/缺品种，新实时明确拒绝；合法正minfee的BT准入保持。该矩阵不冒称重新验证BT原成交最低费用。

受管minimum-refusal002本身只保留未Ready、0查询/0SDK/0callback和无原stradata的现场，WRI通用failure没有保存子进程具体SessionError；该次具体启动错误正文保持unknown。另以constructor003独立安装进程调用实际ExecutionProcessConfig.load及完整RetainedStrategy构造器，同一模型只更新当前周期有效时间：minfee7实际触发固定最低费用SessionError，minfee0接受，原生入口未调用。两份证据分别记录。constructor001/002保留夹具的清单已存在/控制目录缺失错误，修正夹具后的003正常通过。

同一R25安装还复验原R24窗口/同日修订/等待/原KV模型恢复17项，全部通过；该回归仍保持原Context模型范围，原BT十模块及回测费用准入源字节保持。

R25-C3的amount001单次完整关闭成立；volume002仍失败，稳定两代及全候选继续待验。已有股票引用修复提案仍未批准、应用或编译；本轮费用准入与其框架差异独立。

真实来源另行复用根的精度四查询交付：B的复核收据（外部历史/待归仓路径：`../../build/ms-real-account-consumer-001/SUCCESSOR-002.json`）绑定22原件、两个原生制品和三源，4P/0O/0D/1A、67事实/39ABI/24浮点精确，新增现场查询0。该真实来源资格与本轮合成费用模型分开；旧资金中断unknown及无包装修正版、真实四owner、v4策略执行接管继续保留范围。

原生Scan四组事实到WT常驻发布、C只读投影的公共接缝已形成[提案](../migration/native-account-publication-proposal.md)，待A/B/C冻结后实施；R20继续按其原策略观察范围供C消费，观衡不启动Scan或Host。

独立执行/财务审查（外部历史/待归仓路径：`../../build/ms-retained-fees-001/REVIEW-EXECUTION-001.json`）及接口/生命周期审查（外部历史/待归仓路径：`../../build/ms-retained-fees-001/REVIEW-PROTOCOL-001.json`）按实际安装、源码、逐代QA和原金融文件身份记录，无新增确定P1/P2。最终开发包身份沿DELIVERY-001（外部历史/待归仓路径：`../../build/ms-retained-fees-001/DELIVERY-001.json`）和同根PACKAGE-MANIFEST-001.json登记；包名B-RETAINED-NATIVE-FEES-DEVELOPMENT-001.zip。私有真实源材料、原始大型POSTFLIGHT和转储不入包。静态总检与最终逐件复核沿同根FINALPOSTFLIGHT-001.json记录，变动中的并行资料按各自检查时点保留。当前记录不授完整模块、实时最低费用、平今/跨日T+1、真实券商费率、全周期BT/RT或生产资格。
