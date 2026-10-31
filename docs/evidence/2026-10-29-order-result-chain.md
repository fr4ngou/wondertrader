# 模块B：正式安装宿主的订单结果与多策略组合

类型：隔离开发证据。日期：2026-10-29。状态：所列订单/组合/未知提交路径通过，完整模块B继续。关联：[P19-O1–O5](../specs/native-qmt-standard-trader.md#stq-p19-受管多策略产品宿主与干净停止恢复accepted开发中)、[模块B](../migration/module-b-delivery.md)。原件根：`build/ms-order-results-001`。

## 固定产品与事实归属

实际安装Appa10薄宿主启动原GuanhengCtaHost.exe，加载BUILD003 Runtime `241cdba18271b4c9a3800efdb97a2750b30326c571554fb3cf86125a5445ffcd`，经过原策略Factory/CTA ticker/组合汇总/Local/通用MinImpact/TraderAdapter/Standard及真实WinSHM，到独立SDK替身。实际账户、行情、策略目标及成交均为明确合成样本。股票T+1专用算法的退出资格不由本轮通用执行器结果覆盖。

本轮生产源码和运行DLL均保持，变更仅在专用测试及文档。测试策略通过正式JSON声明两个原生上下文及初始/后继目标；后继A800来自测试目标文件，由下一次原主K线调度读取。测试没有直接调用调度/撤单接口。券商源模型仅保存自己的总持仓、订单和成交事实，WT原策略及组合文件保留理论状态；不引入策略真实成交分摊或第二账本。

## 订单终态后继续

| 验收/用例 | 实际SDK操作 | 查询与结果 |
|---|---|---|
| O1 `filled-late-001` | 买1000、买200 | 16查询；先查询持仓1000，再收到迟到600及重复TradeID，下一调度仅补200，最终1200 |
| O2 `partial-cancel-replace-002` | 买1000、撤余500、买500、买200 | 28查询；原1秒expire自动撤余并补500，后续迟到100及重复未形成额外仓位；最终1200 |
| O3 `full-cancel-replace-001` | 买1000、全撤1000、买1000、买200 | 21查询；原首单54/P0后续买，续单完成后重复其真实TradeID，再仅补200；首单没有伪造成交 |
| O4 `insert-rejected-001` | 买1000被拒57、买1000、买200 | 20查询；查询确认首单终态/P0后以不同原命令继续；续单成交重放后仍仅补200 |
| O5 `cancel-refused-001` | 买1000部成500、撤单返回false、原单补成500、买200 | 21查询；原Journal保存sdk_returned/signal_sent=false。原订单55/余500/已撤0期间继续两轮行情，SDK仍只有首买和撤单；原单全成后才进入目标增200，最终1200 |

五案均最终A800/B400，唯一来源成交量合计1200，原重复成交身份去重，原来源发布水位全部确认；原件中`execution-outcome-proof.json`、RESULT、POSTFLIGHT、原stradata/portfolio及完整fixture分别绑定。调用返回、订单终态、券商持仓和策略目标分别核验。

## 正式入口的五组合与未知提交

| 用例 | 结果 |
|---|---|
| `build/ms-trade-rules-001/native-add-001` | 同Runtime，A600+B400、券商P0，唯一净买1000，四查询；复用仍匹配的原正式入口证据 |
| `exit-001` | 券商P1000/全可卖，A退出保B400，仅卖600，四查询 |
| `net-001` | 券商P1000，A600→800、B400→200，净额0，SDK0，四查询 |
| `pending-001` | 券商P600，买400后活动未成400，后继行情不重复提交；六查询 |
| `partial-001` | 买1000部成500，查询P500及未成500，后继行情不重买；七查询 |
| `unknown-001` | 真正进入SDK后抛出明确合成异常；原Journal保留同一UUID、command SHA、result SHA和unknown；SDK总1/额外0，原来源unknown_fenced。关闭以recovery_drain失败、recovery_ready=false，无clean证明；物理回收完成 |

策略600/400等属于各自原理论账本，账户P500及未成500属于独立券商源事实。本组不把部成500自动分摊为策略真实成交，也不授予人工同标的混用资格。

## 测试预算、源码身份与关闭

O2首轮001被旧单代测试代理的32条查询进度采证上限阻断，退出1、代理first_error为query progress transcript capacity。该原件保留为失败；002按该有限长链配置128条采证预算后通过，Host原64条查询Journal、产品队列和原运行截止均保持。本轮没有调查或修改WT多线程。

O3/O4实际测试源为run SHA `2d17f419e046300cb8fdb4d59a284f2721e4e997cf85287455cb1dcd08e94edc`、outcomes SHA `95ad87502dba1bdd1c457d14ac74f86d7d120a0e222a5101e770b15e4929bd8f`；O5及后继定义增加相应分支，O2后继另增加上述测试预算。每案启动前`*-input.json`记录当时摘要，`test-source/<SHA>/`冻结精确对应字节；早期两版按已有启动摘要重建并验证逐字相同，不改写原运行结果。最终定义按受影响分支delta/reuse，不声称所有较早进程使用同一最终测试字节。

所有通过案first_error/proxy_first_error为空、forced/pending=false，Host、源、HTTP/代理线程、产品进程树、双EOF及reader join均完成；未知提交的故障状态与成功物理关闭分别记录。真实券商调用、QMT界面操作、生产切换及新增WT核心修改均为0。

独立审查、文件SHA矩阵及交接沿本构建根登记。真实账户/行情统一A/C安装、股票完整T+1/费用、异常跨进程/跨根责任及所有保留业务算法继续原模块目标；本轮不替代冻结007发行候选。
