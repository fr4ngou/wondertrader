# V2同核原生实时、回测与恢复

类型：开发验证。状态：限定主链与搬迁通过，独立审查收尾；完整模块B保持in-progress。

## 职责与实现

此前正式Python CTA入口只接configured1.2.0，V2已有独立纯核、冻结DTO、V2Binding及原生BT。按[NRT-R13](../specs/native-realtime-strategy.md#nrt-r13-固定v2同核实时接线)，本轮在B所有的execution_configured增加固定`guanheng.v2-cta.v1`，复用原StrategyBacktestSession准入及V2Binding/evaluate_v2_history，直接将原经济目标交NSQ和原完整setter。实例只改strategy_id，权重、超配判断、资金、持仓及绩效仍由原owner计算。新增金融账本及WT核心行为均0，WT多线程调查保持停止。

V2输入为`nsb-v2-input-v1`，与原configured DTO严格配对。此profile是显式冻结历史窗口，求值截止取原上下文时间与窗口最后日15:00的较早者；报告单独记录实际native_knowledge_cutoff。原signal核继续核逐行可获知时间，窗口更新与真实连续行情分别验收。execution_process同时绑定原七包的Python源码及JSON资源，V2发行profile不再处于身份清单外。

独立审查发现预编码可能耗尽本轮期限后仍进入setter。最终实现令预编码、setter前后、原KV及最终发布共用同一截止，超过时沿health失败并拒clean。旧值上下文实际进入setter1次，修正后0次。这里采用同步调用边界检查；原生同步调用内部继续沿原生命周期处理。

## 自有观察文件根因

V2恢复003/004及observed001遇到自有strategies.json替换PermissionError；观察子端保留原winerror5/errno13。独立单线程Windows句柄实验复现：原MLP._open_read持有前代文件时Path.replace报5，读句柄归还后，同一个pending立即成功；没有WT或SDK参与。

自有投影发布统一使用_replace_projection，只在5/32/33窗口沿原evaluation截止等候；其他错误立即传播。替换失败到期保留最后原生错误、前代及pending，成功后才发现超时则保留已提交投影；两者均拒clean。最终真实句柄回归覆盖释放后成功、跨D保持前代、5/32/33下一轮顶部到期保留原错误和其他错误单次传播。原持仓、用户变量和已发生setter保持原事实，未加回滚或额外保存。

## 最终固定安装与实际主链

原件根为`build/ms-v2-native-001`。BUILD005的普通非editable Python3.12环境`runtime-venv-005`离线安装22发行，pip check通过，1975项带摘要RECORD及1904个非RECORD wheel成员逐字节一致；1993个安装文件，无.pth/pyc。固定Appa10的60个公共文件沿先前冻结快照，B三薄适配同步当前源；当前C的Appa18及其新算法包保持原状。本次资格不转授统一Appa18。

| 固定项 | SHA256 |
|---|---|
| App wheel004 | `f000daac02bfd22f5e004d9b8ff570cf1ac91ef94a17c82b534ab30ba4142cc8` |
| execution_configured.py | `e4fccba76a619ebad036e8d69abf2c6aca08bdde26a92ee8f4b243086fa97513` |
| execution_process.py | `17b955fe7db786a2e9321126e78a2088dc7858b6206b606d69115b7bd04e7a60` |
| 原Runtime BUILD003 | `241cdba18271b4c9a3800efdb97a2750b30326c571554fb3cf86125a5445ffcd` |
| 002开发ZIP | `9fa8f245c01a6f25c770155ee033628851d23bd32ae17a759cf8227f167d8298` |

该002 ZIP含57成员、22锁定wheels、原Runtime/Factory/执行器/交易插件、Reader/Helper、公共头及四上游许可证；逐项解包SHA通过。CPython3.12须另装，生产账户/Parser配置由A/C提供。它是本片开发包，冻结007候选保持，真实交易和生产切换均0。

最终`recovery-006`从正式安装模块进入原DLL/标准Factory/CTA ticker/Local/MinImpact/Adapter及WinSHM SDK替身。125日九读取证券、八信号证券的原V2三分配事件给CSI300权重0.25，其余显式0；两策略各显式理论资本50000元，目标各1200股，原组合净买2400股一单。24次四类查询、后继原调度收敛，两代原KV序号2→3、state_id不变，恢复代新增SDK0。两代closed.ok/recovery_ready成立，Host/来源/Job/管道EOF及reader均正常回收。

最终比较器先沿RT正式配置核输入路径、原字节SHA和profile，再按最终进程PID及配置摘要选择唯一closed收据与Python绑定，BT后重核原件。`compare-007`由同一安装及输入进入原CtaMocker/StrategyHost，124次原回调、两笔原生成交800+400，最终1200股；完整V2 pipeline、signal_trace、metadata、经济目标（除实例strategy_id）与实时逐项一致。BT价10元/现金38000元，RT价10.01元/现金37988元；两种原撮合模型分别记录。Host exit0、reap/双管道join成立。原compare006实际输入经独审核对相同；比较器的身份准入缺口通过原DTO的manifest单字段变更反例关闭，反例在BT前拒绝且零原生调用。

`boundaries-003`为安装领域核与值上下文验证：profile/DTO错配、输入SHA、布尔预算拒绝；原V2超配给target=None、零setter、原阶段不变；预编码后到期零setter；发行JSON漂移及额外资源在Job前拒绝，最终还原字节。它不单独授原生超配或真实账户资格。`projection-publish-002`为真实Windows文件句柄验证，WT/SDK调用均0。

002 ZIP在独立`build/ms-v2-relocated-002`实际解包、普通环境离线按SHA锁安装22包，1904个wheel有效载荷成员与原安装逐字节一致。`v2-clean-002`和`configured-clean-002`分别完整跑两代，首代各净买2400/1400股，两案恢复代新增SDK均0、各24次查询，四个进程均完整正常关闭。外层driver正常返回，各有原native.run收尾记录；没有据文件存在推断存活。

## 保留失败及资格范围

原件均保留：compare001因uv venv隐式启动文件被BT准入拒绝、未启动子进程；compare002/003的原生回放成功而比较器误用typed报告/前缀schema，后继沿公开validator/project/reconstruct修正；compare004因依赖失败RT原件缺失未进入BT。realtime003为原查询运输超时、零SDK，故障实例保留；recovery001两代已成功而采证正文超过2MiB，后继复用已有运输摘要。recovery002测试直接读文件遇共享窗口，后继测试消费原控制读取器。recovery003/004/observed001为上述自有投影根因，后继根因回归及最终006通过。

搬迁首轮的configured观察沿静态metadata读取器，在句柄关闭后恰逢路径原子换代时拒绝文件身份。后继测试明确使用可替换投影的单句柄快照，完整核句柄读前后身份/长度/大小、单链接与JSON，保留同一截止；路径可以在快照复制后进入下一代。确定性单线程close后替换反例验证原静态准入仍拒绝、投影获得完整前代且当前路径为完整后代。该修改位于测试观察层，公共App读取器保持原合同。

recovery005出现原进程C0000005，首四查询后已进入一次SDK替身；无clean资格。该原件继续保留，不调查WT线程或修改核心，也不以最终006成功转授此失败实例资格。最终主链通过范围为所列合成冻结窗口、通用MinImpact及明确资本模型；持续来源、完整资金/T+1/费用、其余算法、异常跨根责任、统一A/C安装与生产稳定性继续按完整模块B目标推进。

最终矩阵、测试源码快照、搬迁结果和独立审查以同根MATRIX/HANDOFF/REVIEW/DELIVERY为准。代码实现、隔离运行与发行生效分别登记。
