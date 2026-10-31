# 唯一策略可卖等待的正式恢复与拒绝

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B验证证据。日期：2026-10-30。状态：同日等待两代恢复的单次整链通过，摘要漂移原生拒绝有同次证据；稳定股票关闭、次日解冻及完整模块继续。要求：[NRT-R26](../specs/native-realtime-strategy.md#nrt-r26-唯一策略可卖等待的同根恢复)、R18/R12/P21及[模块B](../migration/module-b-delivery.md)。

## 职责及输入

产品和WT框架修改0。普通无观衡WT 0.1.0a3六发行安装复用A的`build/wt-account-publication-composition-001/installation001`，本轮730条hashed RECORD逐项核对。实际Runtime/Host/标准Trader等沿R23 native002；12份编译生产源、各案实际安装文件与原BUILD均匹配。Runtime SHA `68d7c415837556ff7c3e2d180250dfb1e98c4d3051a0fd4133a9e4f5a3f1d86f`，原股票工厂SHA `8e0721f3c2d54621468a02fa6cf3a63640f7ec9218e7a2116bcfe8af5860a131`。

唯一正式1.1.2、原Factory/CTA/NSQ/执行器/Adapter及SHM均实际运行。历史、行情、账户与SDK明确为合成来源。QA增加显式`--feed-date`，本轮行情、原CTA及接管交易日均为20261030；缺省保留旧次工作日夹具。其余新增代码为隔离拒绝探针及原件复核，不新增金融账本、保存接口或行情串行。

原件根`build/ms-sellable-recovery-001`。FROZEN-SOURCES-002（外部历史/待归仓路径：`../../build/ms-sellable-recovery-001/FROZEN-SOURCES-002.json`）绑定四案实际QA摘要及物理副本、最终四份QA源、12份原生生产源、普通安装和运输快照。001/003保存实际QA原字节；002与003相同摘要复用；004的run_retained按003及已记录的目录定位差异重建，最终逐字节摘要等于实际INPUTS004，其余文件同摘要复用，方法见HISTORICAL-QA-FREEZE-001。各案Host/Agent与运输QA均读取各自冻结副本，不追认后续工作树。

## 实际运行与证据范围

| 原件 | 结果及范围 |
|---|---|
| main001 / RUN001 | 正式安装WRI同根两代全部通过：12次SDK替身只读查询、SDK写0；两代成功closed.v2/clean.v2，原接管收据SHA保持；内外Job/管道/Host/来源全部回收 |
| main002 / RUN002 | 首代waiting_sellable业务已形成；关闭时捕获c0005，6查询/SDK0；无clean，未进入二代或拒绝探针。整体失败，物理回收完成 |
| main003 / RUN003 | 两代正常恢复，第三代人为追加用户KV文件换行后，原生在cta阶段拒绝，累计16查询/SDK0。原QA因启动拒绝没有业务locator而误读controller路径，最终FileNotFoundError，整体仍失败 |
| main004 / RUN004 | QA改用本次新增控制目录的failure三身份；首代关闭再捕获c0005，6查询/SDK0，修正后的完整拒绝入口未执行，整体失败 |

四案合计40次SDK替身查询，真实下撤单0。001的PROOF-001（外部历史/待归仓路径：`../../build/ms-sellable-recovery-001/PROOF-001.json`）实际读取原件复核：持仓200/可卖100、独立券商200/100，整个原NSQ阶段对象、八证券raw观察和两证券周期元数据相等；保存序号2恢复并推进到3，原用户KV的state_id与原NSQ恢复器计算一致。核心结果除新的decision_cutoff/input_sha256外，其余18字段相等；提交向量为空，未产生重复委托。三份原金融JSON与二代clean逐项匹配，均由原WT保存/加载，停止额外save为0。

## 摘要拒绝与QA定位修正

main003的第三代与已成功二代使用相同配置SHA、安装和同根原金融状态，仅用户KV追加一个换行。原生failure/close-prepared三身份一致，stage=cta，ready及成功closed均不存在；原clean/consumed仍指向前两代，QA的finally恢复后，三份金融文件与原clean摘要全部相等。

RECORDED-REFUSAL-003（外部历史/待归仓路径：`../../build/ms-sellable-recovery-001/RECORDED-REFUSAL-003.json`）通过修正后的`locate_rejected_control`读取本次实际新增的第三目录，并核四次初始化查询、SDK0、三代WRI外层启动器退出码0/0/2及完整资源回收。该复核没有启动Native/Host或新增来源查询。注入摘要由实际冻结QA及恢复后的原字节推导；原CtaProcess在engine.init前确定性核原金融摘要，因此“未进入原策略初始化”属于绑定源码与该次输入的推断。本次没有在finally恢复前另外归档受损userdata的独立读取。

该收据仅证明上述已发生的拒绝及定位修正的纯读取行为；原main003整体失败记录保持，最终修正QA整条入口的通过资格为false。初次独立复核因`-I`不加入脚本目录而在import阶段退出，来源查询/Native启动0；显式加入同一QA目录后复核通过，原失败日志保留。

## 本次实际关闭异常

两份保存的dump分别经原只读OfflineStackWalk展开42帧。两次直接返回均为`WtExeFact.dll+0x1baff`，与[已定位释放链](2026-10-30-stock-close-release-trace.md)的商品release虚调用位置相同；同次工厂和Runtime SHA也相同，记录见OFFLINE-STACK-SUCCESSOR-002（外部历史/待归仓路径：`../../build/ms-sellable-recovery-001/OFFLINE-STACK-SUCCESSOR-002.json`）。原STACK与符号/对象匹配证据按原输入复用，本次不把完整首次释放历史提升为已知。

离线工具两进程均exit0、树零、EOF/join/资源完整，未新建交易运行实例。首个离线脚本误把工厂放在app根目录，实际位于executers子目录；该读取错误及前件保留，后继按实际路径完成。原始内存转储及完整POSTFLIGHT保留受控运行根，公开增量包只收限定摘要和SHA。

WT原on_session_begin负责跨日冻结释放；本次同日恢复不授次日解冻。两个新增关闭故障使稳定当前组合仍未通过；[最小股票引用方案](../migration/native-stock-metadata-ownership-proposal.md)保持提案及原审批状态，生产未应用或重编。后续仍需完整跨会话T+1、成交后稳定两代、异常/未知责任恢复、全周期BT/RT及统一候选。独立审查、制品、SHA和最终交接以本原件根收据为准。
