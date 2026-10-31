# 自有挂单撤清后的正式策略重新计算

类型：模块B安装后主路径验证。日期：2026-11-01。状态：NRT-R33-C1/C2主链及定向回归通过，两项独立delta审查开放P1/P2均为0；可交Root纳入统一候选，整模块资格继续核对。

## 要求及实现范围

按用户要求采用[NRT-R33简版](../specs/native-realtime-strategy.md#nrt-r33-自有委托撤单收束与重新计算简版)：暂停新增委托，使用原Host映射及原WT订单表定向撤清自有活动单，确认券商终态，再查询持仓、可卖和资金。正常停止在保存前完成同一收束。重启保留WT必要策略记忆，原数量执行阶段从当次券商持仓重新计算。首次库存继续使用[当前持仓的新基准](../migration/retained-strategy-takeover-proposal.md)，旧开仓历史和旧交易记录不迁入。

修改限定于自有Standard、执行宿主和CTA装配，以及正式Configured桥的旧数量阶段重算。原WT订单、策略账本、用户变量、费用与绩效保持原有职责；Host/Source/Journal没有新增状态或数据库结构。`is_cancel_unmanaged_order=false`，人工及其他系统委托保持。暂停新增委托与通信故障分别表达，原unknown和硬故障围栏继续生效。

## 实际普通安装主链

唯一业务场景使用普通离线23-wheel WT角色，启动安装中的公开WT CLI，再经原生CTA、正式`resonance-regime-v1@1.1.2`、原执行器、Standard、原Host/WinSHM及原线程SDK替身执行。观衡App未参与。

初始券商持仓为510050.SH的200股、可卖200股；另有无本系统Host记录的人工买单`manual.keep.1`，冻结资金10,000元。首代正式策略产生卖出200股目标，SDK替身成交40股、余160股活动。正常停止沿原订单身份撤清160股，后继完整订单查询为终态54，持仓查询为160股/可卖160股，随后资金查询可用75,599.2元。人工单原字段保持。

第二代直接消费首代真实clean证明和原WT金融/用户文件。原策略序号、周期及必要记忆接续，旧数量计划的起点200股更新为当次券商160股；新正式回调完成前没有新增委托。下一行情只提交160股差额。第二代正常停止将该单余量撤清。全程SDK顺序为`insert200 → cancel_original160 → insert160 → cancel_remaining160`，原单没有重复提交。

原Journal保留四个不同命令ID，操作为`order.insert/order.cancel/order.insert/order.cancel`，两个撤单各指向自己的原insert。四条源结果均为`sdk_returned`，两次撤单都得到终态ORDER、后继POSITION和ACCOUNT查询。原账户持仓最终仍为160股，可卖160股；人工单保持活动。

两代Native PID为22844、62556，均由原监督者发布`closed.v2`，退出码0、资源关闭及真实恢复证明齐全；额外QA只打开这两个明确PID的查询句柄，独立观察退出码0并关闭句柄，没有附加调试器。外层PID39780退出0，47.411秒，根进程回收、树归零、双管EOF、reader join及资源关闭均成立。Source及代理的first_error均为空。

原WT理论费用4元在两代间保持，SDK替身实际40股成交费用0.8元单独保留为券商模型事实。本次核对保存连续性及事实边界，未将理论费用改写为券商费用，也未引入成交分摊账本。

## 源码、构建及原件

冻结检查点为`build/ms-simple-recovery-checkpoint-001/INTERFACE-001.json`，SHA256为`6ec49fbfe4afc4b68186920396d300e7d8325d2c61e34d2790a3ffc81f8f93ae`。它绑定12份精确源码/规格快照及Root原摘要、121份Native自有输入、25个安装组件、23个wheel与335份实际业务/回收原件。当前源码位于隔离`build/sc-src1`，主工作树的产品源码尚未采用此增量，Root负责最终集成。

当前Native为`build/sri1/installation`，其`RESULT.json`明确登记在已归档的全新源码构建基础上进行同源增量构建及实际链接审计，不声明本次增量为全新零旧对象构建。WT wheel版本为`0.1.0a12+integrated.2.reconcile.1`，SHA256为`745f6c1561911a19c1e5b3e6b7440af254ad2ec0d30b07b119333c408cdbd85c`；Host/Agent复用已合入R32的原版本及证据。

普通安装及依赖身份由`build/ms-simple-recovery-install-001/RESULT.json`登记；实际场景原件为`build/ms-simple-recovery-main-005/RESULT.json`、`NATIVE-EXITS.json`、`run/POSTFLIGHT.json`及原金融目录；外层回收原件为`build/ms-simple-recovery-main-job-005/RUN.json`。输入、驱动、各代clean/closed及原Journal的逐文件SHA均沿检查点核对。上述build路径是本机受控证据，不随源码自动分发。

## 失败原件与剩余

### 审查修正后的最终主链

独立协议审查在原sc候选指出两项P2：收束helper只在等待入口核截止，pump晚返回后可能继续派发后继操作；资金等待只看account_revision，较早ACCOUNT的晚交付也可能使其增长。后继`build/sf-src1`只在自有薄层修正：每次查询/撤单入队前及pump返回后检查同一原截止；沿原Query/Resolve任务ID，在完整ACCOUNT交原SPI并返回后记录last_account_query，并以P后的next_task屏障等待本次A。

恢复观察结构从64字节增至72字节，原version/size检查继续先于写出，宿主及插件同批重编；query_first非事件模式的驻留预算相应增加8字节，事件模式沿实际sizeof。没有新增持久字段、数据库或WT核心行为。实际helper的定向入口为`tests/integration/qmt_cta_product/reconcile_order_barriers.py`及相邻C++夹具：晚ORDER、晚POSITION、晚cancel与旧ACCOUNT四项原红新绿，结构大小分别实测64/72；外39528退出0、4.735秒并完整回收。原件为`build/ms-simple-recovery-barrier-001/RESULT.json`。

最终匹配Native为`build/sr2/installation`，基于归档原对象及安装的四输入增量同批构建；外7888退出0、20.813秒/完整回收，121自有输入及25输出均绑定。Python wheel与普通23-wheel安装的全部字节保持，直接复用。最终同一正式场景006的两代Native为21240、33104，各退出0；外46472退出0、41.0秒/完整回收。撤清、P/A顺序、160股重新计算、原策略记忆、人工单保持及原clean消费全部通过。`build/ms-simple-recovery-review-input-002/BUSINESS-006.json`以335原件绑定该终态，SHA256为`e3736a0b6cc54a05fd173a44dcb67996da5cbf0361ffc169c00680bf0157716a`。

此前005检查点保持原字节和已验范围；最终采用以这份sf/sr2显式增量及后继审查、交接清单为准。

协议最终报告`build/ms-simple-recovery-protocol-review-001/REVIEW-002.json`绑定364项，SHA256为`40ccedd508c85cde6d2c88e11fa4b996e8bebd37b54c7bfa040f6bf3abc72175`；执行报告`build/ms-simple-recovery-execution-review-001/REVIEW-001.json`含54直接绑定并复核335项业务引用，SHA256为`d595c8e256c41cc841b7b938744e2899f7d8f7b8631c282fdb769defaa383fb3`。两者开放P1/P2均为0，原sc首审两项P2及其最终关闭分别保留报告。

最终统一交接入口为`build/ms-simple-recovery-delivery-001/INTERFACE-001.json`，候选制品为`build/ms-simple-recovery-package-001/B-SIMPLE-RECOVERY-R33-001.zip`；准确SHA由交接清单登记。制品复用已验23个wheel及锁，配套25个最终Native组件、原许可证、源码差异和验证/审查身份。相同字节的普通安装及006业务直接复用，打包只做成员/摘要核对。共享主树产品源码由Root按该显式后继合入，已有运行安装保持原状。

main001在SDK前因自有临时暂停位被误计入通信故障而失败；已将暂停限定于新增委托准入，通信诊断沿原语义。main002的SDK测试替身完成撤单后漏返接口规定的bool，原接入层正确保留`invalid_sdk_return`及unknown；修正仅涉及QA返回值。

main003实际完成原单撤清及P/A刷新，后续缺正常关闭证明，原生退出码当时未记录，同次原因仍unknown。main004的两代实际业务、正常关闭和调试器观察退出码均通过；其外层随后因QA将Journal操作误认作SDK方法名而失败，已只读修正校验并保留原件，业务没有重跑。main005沿相同产品的普通退出句柄观察及完整断言全部通过；这些后继结果保留各自范围，main003的历史失败继续保持未定位。

Root统一候选接收及整模块逐项资格仍在继续。脏金融状态自动恢复、跨版本重放没有新增实现；状态损坏或原命令身份不明时，原保护和原ID核查继续生效。既有正常53笔与R32两类unknown主链复用输入匹配的原证据。自然跨夜及真实费税按已有模型/真实来源范围另列。QMT保持用户关闭，本次真实查询、下单、撤单和生产切换均为0，新增WT核心行为为0，所有新输出位于E盘。
