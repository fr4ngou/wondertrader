# 2026-10-25 未知委托 Host 准入与原目标取消引用

类型：限定验证记录。关联[UC主规格](../specs/qmt-unknown-cancel.md)。Host产品revision003及Journal测试revision004完成下列组合回归；C++客户端、标准插件、真实SHM完整后继及生产恢复另验。

## 根因与实现

Host显式状态v2分别保留未知、硬故障和关闭。Journal沿原文件、事务、身份和profile保存原命令及关联，不增加表、列或金融账本。当前真实proof与来源在提交和派发时分别核验；同一原insert至多一个未决cancel。已有未决cancel优先于新记录额度检查，返回完整精确cancel_pending；只读cancel lookup返回实际取消原记录，未受理申请不改成别名。

四项适配根因修正：额度检查后重新核原业务截止及剩余TTL；损坏关联元数据在所有lookup入口锁存硬故障；冲突返回前覆盖rollback、连接关闭与binding锁释放耗时，重核原HTTP截止；Runtime缓存尚未同步Journal硬故障时，原claim事务按唯一准入判断返回空领取，状态、回报与ACK继续。首次真实时钟、SQL、proof/身份损坏等异常继续传播，submit保持拒绝。

## 实际回归与失败原件

所有测试使用冻结源码、临时隔离通信数据库、SDK替身与隐藏有原截止的子进程。真实QMT会话、真实下撤单及生产运行均为0。

| 批次 | 实际结果 | 后继处理 |
|---|---|---|
| host-deadline-repro-001 | 原两项既有业务D回归均失败 | 保留反证；产品修正后在full002/full003通过 |
| host-full-002 | 219执行，4 ERROR、0failure、0skip | 三项测试broker错配，一项真实claim关闭门竞态；原批次保持failed |
| host-full-003 | 221执行，8 failure entries、0error、0skip | 失败属于5个Journal旧预期方法（含subTest）；产品根因回归及其他181项通过 |
| host-journal-004 | 40/40，0failure/error/skip | 仅迁移六处已知关闭门的旧异常断言；其余产品与测试保持003 |

最终覆盖由003其余六模块181项与004 Journal四十项组成，共221个唯一测试ID。未把failed批次改写为整批通过。原SQL/时钟/截止异常测试继续实际通过；首次时钟故障仍抛，恢复时钟数值后已锁存hard门的领取才返回None。

新增真实Runtime/Control回归使用原HostTradingRuntime、ControlPeer、TradingControlLoop、Source服务与SQLite：阻塞trade.stream后把原D claim排队，再锁存Journal硬故障，证明旧Runtime缓存仍允许取消；claim空值正常退休，之后真实事件页持久化及两层ACK继续。原unknown/queued/body/业务截止保持，agent.trade=0。负例验证真实存储异常原对象继续传播。

期限测试覆盖额度耗时导致原D过期时无记录/通知、冲突响应在rollback/close/锁释放耗时过D时不发布业务409。关联损坏测试覆盖event/query及WT/token/取消查找入口，并验证后继健康目标仍受hard门阻止。取消竞争、单目标唯一、快终态原引用、历史GET不能刷新proof、旧来源版本兼容与原身份回取在这七组中分别断言。

## 审查与身份

独立full及revision002/003/004 delta逐项保留。原H001–H003及后继H004测试数据、H005产品竞态、H006测试契约迁移均已静态闭合，004剩余已确认P1/P2为0。根核14份最终source/test原件；004六处断言逆转后整份Journaltest字节与003一致，其他13份保持003。

最终原件：build/guanheng-workspace/qmt-unknown-cancel-host-final-001；COMPOSITE-QUALIFICATION.json含全部221测试ID，SOURCES-ROOT-VERIFIED.json含14份身份。Journal为dcbf0e4891d999f2ccdf833bd0b933e318c548c24ec7fc57a544e6ae239630af；Journaltest为3620118e124b64d1e2755879151b92587dfa88dccb624d18ca4405dddcd16042。作者最终清单为build/qmt-unknown-cancel-host-001/revision004；独审为build/qmt-unknown-cancel-host-review-001/revision004/REVIEW.md。对应动态冻结来源在host-full-003及host-journal-004。

## 未覆盖范围

这些结果证明Python通信owner和隔离HTTP/事务/Control调用链，不授Common响应EOF、Standard自动审计/额度、原Adapter完整未知取消或真实券商SDK资格。C++接线继续开发；一般insert解除及生产query/live交接尚未闭合。源unknown不伪改为成功，Journal重启仍保留未知事实。生产Factory保持原入口，event_consumption_complete=0；无新增WT框架、旧QMT或生产变更，整体目标active。
