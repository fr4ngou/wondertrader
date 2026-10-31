# 正式WT入口的账户重连与在途停止

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B验证证据。日期：2026-10-30。状态：限定SDK来源与C实际文件消费者主链通过；HTTP/页面、真实来源及完整模块继续。要求沿[NAP-v1](../migration/native-account-publication-proposal.md)、[WRI](../specs/independent-wt-runtime.md)及[模块B](../migration/module-b-delivery.md)。

## 实现与输入

本次产品修改0，新增WT核心修改0。B的四个账户生产者源码继续与原005/a2相同；公共运行装配采用A已普通安装和独审接收的WT 0.1.0a3，见[正式入口组合](2026-10-30-wt-account-publication-composition.md)。原账户Host、Scan、TraderQMTReadOnly和C金融投影保持各自职责。

QA入口为`tests/integration/native_account_publication/wri_lifecycle.py`，装配沿A已验夹具，原件摘要记录在入口注释。实际子进程使用普通安装的`guanheng_wt_runtime`正式CLI。SDK替身在外部QA线程提供账户四查询；该线程同时驱动原ReconnectingReadAgent。WT环境无观衡/Web，C消费者由外部QA解释器加载工作树中的原实现。本次取得C实际文件定位与金融投影资格，独立安装的C HTTP及浏览器页面分别待验。

原件根`build/native-account-wri-lifecycle-001`。冻结输入（外部历史/待归仓路径：`../../build/native-account-wri-lifecycle-001/FROZEN-INPUTS-002.json`）绑定main002全部1367份运行输入、18份物理冻结的QA/C消费者及四个生产者源码、A安装与接收的7份收据。1367份输入在实际运行前后完全一致。四个生产者同时与本次安装site-packages及原交接摘要一致。当前工作树的后续修改按各自版本处理。

## 实际主链

main002结果（外部历史/待归仓路径：`../../build/native-account-wri-lifecycle-001/main-002/RESULT.json`）通过，外层运行（外部历史/待归仓路径：`../../build/native-account-wri-lifecycle-001/RUN-002.json`）正常结束。全部文件、临时目录和缓存写入E盘。

| 阶段 | SDK替身累计查询 | 实际业务结果 |
|---|---:|---|
| 初始两轮 | 8 | 原四查询每轮取得2持仓/1订单/1成交/1资金；每轮50项原事实、6项浮点逐位一致，可用资金82000→82100 |
| 运输重新认证 | 12 | 关闭旧Agent后，同凭据通过原常驻入口重新认证；四组共同来源一致，运输代及绑定摘要改变，原Journal文件身份保持 |
| 来源失败 | 13 | 下一轮首项SDK查询明确抛错；发布degraded，保留此前成功scan_id、四组原帧、completion、close和last_success_at；本轮attempt独立且物理资源全回收 |
| 成功空批恢复 | 17 | SDK明确返回空持仓/订单/成交及一行资金；新成功批清除旧行，更新时间与成功scan_id推进 |
| 在途停止 | 21 | 下一轮SDK查询正在执行时提交本代WT停止请求；原四查询排空后发布stopped，原Host按逆序关闭，未启动后继轮 |

C的`observe_published_account`沿实际WT status → account_observation locator → ready身份 → 原账户帧读取，五次分别取得ready、重连ready、degraded、恢复ready及stopped。每次核schema4.0、原成功时间、分组行数、账户掩码和同一scope；最后runtime_state为closed。C读取期间SDK调用数保持不变。该消费者没有创建Scan、Host或WT owner。

正式CLI启动器14832的OS退出码为0，正常等待阶段无提前强杀；实际WT Python46244有同身份closed/status，Host7888有原关闭证明，整Job树零、两管道EOF、读线程join及句柄关闭全部通过。WT Python46244的单独OS退出码未归档。原close_reaped随后仍会对已空Job调用TerminateJobObject，本次不授全程API零调用。原SDK Agent正常关闭。原生每轮completion/close与外部物理回收分别留证，不合并成账户同一时点事务保证。真实下单/撤单0。

## 失败保留和适用范围

main001已经执行相同21次查询并正常回收，但QA恢复环境变量时复用了局部名`value`，覆盖最后成功快照，导致最终停止断言TypeError。根因修在QA变量职责，改用`previous_value`；main002在最终源码上重跑通过。main001结果保持failed，运行资料保留。

本次证明运输同凭据重新认证，券商登录会话换代仍unknown；没有轮换凭据或对旧unknown请求逐ID恢复。原[a2父死亡/Native暂停超时](2026-10-30-native-account-publication-faults.md)继续只授原安装范围，本次a3没有重授这两项资格。原a2包的最终复核见FINALPOSTFLIGHT（外部历史/待归仓路径：`../../build/native-account-publication-faults-001/FINALPOSTFLIGHT-001.json`）：旧C投影源码已物理冻结，当前C更新在收据中单独列出。

同进程执行策略与账户发布的组合、实际C HTTP/页面、真实QMT四连接、完整交易未知责任恢复、唯一1.1.2全周期BT/RT和稳定两代恢复继续。单次账户生命周期通过不提升整个模块或生产资格。独立审查、最终文件身份及交付结论以本原件根中的报告和收据为准。
