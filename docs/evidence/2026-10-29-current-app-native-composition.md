# 当前完整App的原生策略组合

类型：开发验证。结果：限定主链、研究输入边界及离线搬迁通过，独立审查收尾。关联要求：[NRT-R15](../specs/native-realtime-strategy.md#nrt-r15-当前完整app安装与研究输入边界)、模块B的B-04/B-05/B-07/B-08。完整模块B保持in-progress。

## 实现与职责

本片将C当前App a19及完整35发行与B已交付原生运行组件组合。共享FrozenSessionInput已经支持显式研究模型，原实时构造器借用NSB准入时也能接收合法研究DTO：`research-before-001`实际发布ready并完成四查询，SDK调用0。这与严格实时profile的资格要求发生冲突。

B在原decode、输入SHA及DTO类型校验后，统一要求historical_model缺省或None，非空返回research_only_input。该检查发生在CtaRuntime装载及四查询之前，旧严格DTO保持原行为。唯一B生产修改位于execution_configured.py；execution_process、execution_strategy沿既有版本。策略计算、数量核、WT持仓/绩效和原保存恢复继续复用原owner，新增金融账本及WT核心修改均0，框架多线程调查保持停止。

当前V2依赖为core a7/signals a5/V2 a4。C根公共v2_package_profiles.json仍登记旧组合，本片保持根文件原字节，在独占候选内新增并选择精确组合，保留旧档案及严格版本校验。C先前V2 wheel中的重复依赖常量由C自行收敛；本片消费C INSTALLATION-003及其wheels-002，算法数学规则保持C原实现。公共资源候选须由C/A集成，隔离候选通过与根App统一生效分别登记。

## 固定输入与制品

原件根为`build/ms-app-current-001`，最终BUILD-003使用普通CPython3.12.14环境runtime-venv-003，App a19/core a7/signals a5/V2 a4/SDK0.15及其余完整35发行。实际4817个安装文件、4789项带摘要RECORD和4690个非RECORD wheel成员已核对，无.pth/pyc。原C App与候选wheel各89成员，差异仅execution_configured.py、V2公共资源及RECORD，其余App成员保持原字节。

| 固定项 | SHA256 |
|---|---|
| execution_configured.py | `4ef18d4d04e041e716ef9e6aed6ae62c4af29df7388550c63d9a824f202d1a11` |
| App a19候选wheel | `adefd23aeab21a90171bb3bc5283bbbac13d9715bb0134e5da084898ec1f736c` |
| C core a7 wheel | `bbc5465fca0fe41d5c0379f237e548ecdeb5f2af2ccf9824edc09ebc5e44de56` |
| 原Runtime | `241cdba18271b4c9a3800efdb97a2750b30326c571554fb3cf86125a5445ffcd` |
| C根V2资源原件 | `39a546a8f2c9773360f93577b0f026000d477150759b9b09eb8e653f7002fbdc` |
| 候选V2资源 | `abf4b2eb5083bcb6db95a1ac4dbb1f3f2c43a705e678db26168ed83adb50caae` |
| 003开发ZIP | `7292ff882ca094f1d3986d878ceec1289c78e5434af652bcc710352ce29ab4a1` |

003 ZIP含74成员、35个锁定wheel、原Runtime/Factory/执行器/交易插件、HTTP日线Reader/Helper、公共头及上游许可证，逐项摘要核验通过。公开依赖沿C固定版本及SHA从PyPI取得，包内完整锁文件可离线安装。CPython3.12 Windows x64另装；开发包没有实际账户配置，也没有自动部署或切换动作。

## 实际主链与恢复

| 最终原件 | 实际观察 | 结论 |
|---|---|---|
| configured-current-003 | 正式安装Python→原Session/Factory/ticker→双策略各700→原Local/Adapter/WinSHM SDK替身买1400；两代共24查询，恢复代新增SDK0 | pass |
| v2-current-003 | 同一安装及原生链，双策略各1200→净买2400；两代共24查询，恢复代新增SDK0 | pass |
| compare-configured-001 | 同安装原生BT124回调/两笔400+300；完整业务结果除实际knowledge_cutoff外逐项一致，经济目标除实例ID外一致，终态700 | pass |
| compare-v2-001 | 同安装原生BT124回调/两笔800+400；完整V2结果及经济目标一致，终态1200 | pass |
| research-after-003 | 合法研究DTO在构造阶段拒绝；ready/closed子收据未发布，原生运行/四查询/SDK均0；父完整回收拒绝子端 | pass |
| research-domain-003 | 同一合法DTO获C研究NSB准入且qualified=false；旧strict核保留invalid_time拒绝；B返回research_only_input且Runtime未claim | pass |
| research-bt-002及research-bt-verification-002 | 真实127来源9证券401日、原生BT400回调，当前纯核与C原结果及BT末次完整结果一致；研究schema/scope和qualified=false保留 | native pass，父采证失败后只读修正核验pass |

四个实时代均沿原控制停止，closed.ok/recovery_ready成立，原KV state_id保持、序号2→3；正常原保存流程额外save为0。两次BT均Host exit0、reaped/双管道join，forced=false。configured的BT价10元/现金43000与RT10.01元/42993元、V2的38000与37988元按原撮合模型分别记录，费用均为显式合成0。每策略理论初始资本为显式50000元，券商为SDK替身；这些结果没有取得真实账户资金或交易资格。

真实研究数据沿[HEM](../specs/historical-eod-model.md)：OHLC为CNY/份、volume从lot100归一为份、amount未知、真实received_at保留，历史首次可知/修订仍未知。显式研究假设仅供历史回放，报告scope明确历史研究及实时/券商/生产未获资格。后续实时观察版本历史输入由C定义领域契约，本片保持严格实时校验。

## 离线搬迁

`build/ms-app-current-relocated-003`从上述ZIP实际解包，在全新普通环境、空专用cache下以offline/no-index/require-hashes安装35发行并pip check通过。4830个安装文件、4802个带摘要RECORD已核对；4690个wheel有效载荷成员与原wheel及首安装逐字节相符。安装器生成的元数据数量差异单列，未宣称整棵site-packages字节一致。

搬迁configured-clean-001及v2-clean-001分别从包内App/Runtime/Reader/Helper跑完整两代，首代净买1400/2400、各24查询，恢复新增SDK均0；四个进程均正常closed及物理回收。行情/日线/预算与SDK均为明确隔离输入；测试专用Parser/策略夹具从显式QA路径装配。搬迁没有借用源环境的产品Python或Runtime。

## 历史失败与范围

原件保持：BUILD001的V2公共资源旧版本拒绝、BUILD002的旧C纯V2重复依赖常量拒绝，均在原生运行前且零查询/SDK；最终BUILD003消费C修正依赖和精确候选资源。research-before-001以父exit1记录原研究DTO准入缺口，后继前置拒绝关闭该条件。

research-bt-001因QA在隔离Python下导入兄弟脚本失败，原生未运行。research-bt-002实际Host exit0后，QA误将ValidatedSessionReport按字典访问，父exit1；后继使用已捕获INPUTS/HOST/安装摘要和相同binding只读验证，复用原成功native运行，没有重跑凑通过。verification-001另有QA asdict类型误用，修正后的002通过。实际native-run脚本按原记录SHA `ec9b1126258506b299253e0ce1ae8a9b93463a382c32058f2f32f6a2fbf2a1c9`恢复并完全匹配，最终QA与历史运行源码分开冻结。

最终源码、命令、原件、安装、搬迁、审查和检查由同根MATRIX/HANDOFF/REVIEW/DELIVERY绑定。其余V1/风险/AI/ETF包随完整发行安装，各自原生实时/BT资格继续待验；完整资金/T+1/费用、异常及跨根恢复、真实全部来源、统一A/C App/SPA和生产资格继续按模块B目标推进。冻结007及V2开发002保留，真实下撤单与生产切换均0。
