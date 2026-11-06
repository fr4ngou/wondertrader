# 运行日志与业务诊断

类型：模块说明。所有者：WT运行维护者。合同为[SDO-R5/R6](../specs/strategy-data-and-observability.md)，发布检查沿[发布手册](../runbooks/release.md)。

## 职责与入口

WT原生运行日志、委托/成交记录和既有通信Journal继续各自拥有原事实。运行状态描述当前阶段，事件日志描述发生过程；业务输入覆盖与无交易原因来自唯一策略诊断，观衡只读这些结果，不启动通信或承担日志采集。

自有`apps/wt_runtime/guanheng_wt_runtime/runtime_diagnostics.py`有两类接缝：`FailureDiagnostic`保留原CLI失败分类；`ProcessEventLog`由原ManagedLocalProcess的两条管道和监督线程共同调用，保存启动、ready、失败、关闭及两条输出流的字节数/摘要。固定异常类别、已知模块的有限行位置、errno/winerror可持久定位；原始stdout/stderr、异常正文、完整路径、参数和自定义异常类名不进入新日志。

## 结构与资源

`guanheng.process-event.v1`记录UTC时间、组件、control_id、事件及固定字段；可沿原状态/Journal身份关联。稳定控制根保存`process-events.jsonl`和三个轮转文件，默认每份1MiB、合计最多4MiB，跨运行代复用。每流未换行片段最多8192字节，超长行丢弃至换行；整流仅计算SHA和计数。原stdout/stderr内存前缀及原output_limit语义保持。

同一ManagedLocalProcess对象的锁只保护内存解析和计数。管道/监督者提交完整脱敏事件到全进程共用的256条队列，每条最多4096字节；一个daemon写线程承担磁盘操作，写入时不持有对象或进程状态锁。队满立即计records_dropped，停止通知和原首截止先发布。磁盘阻塞不新增写线程；最多256条排队加1条正在写入，整进程队列正文上限约1MiB。

稳定根另留1字节`process-events.lock`。写者用OS非阻塞排他锁完成容量检查、轮转、追加和fsync；锁竞争计write_failures，后续独立事件可再记录。锁文件保持原身份，轮转只管理本系列。全系统其他日志、既有控制代原件和清理仍按各owner策略维护，4MiB只属于本日志系列，不是全系统磁盘总量。

EOF在内存形成尾行/流摘要后沿原回收，日志异步留存。`snapshot()`分别返回records_written、write_failures、records_pending、records_dropped；业务关闭成功不授日志已落盘资格。独立`drain(timeout)`供验真等待，原start/close不调用；进程正常解释器退出时额外最多0.5秒排空，超时仍属未写完。发布检查核实际文件和计数，异常退出/磁盘长期阻塞可丢尾部事件，不能声称日志零丢失。

原审查的慢I/O及重叠轮转反例已加入回归：阻塞fsync时原停止/截止/管道EOF继续，两个实际隐藏进程共享系列仍守容量且记录写失败。七项及原CLI七项和独立delta复查通过；额外自然退出不调用drain也留下完整四条事件。实现已随[Runtime14.4](../releases/2026-11-06-runtime14-auxiliary-live.md)普通安装采用，保留原封存覆盖；Native与TradeHost新事件已实际落盘。[日线21](../releases/2026-11-06-daily21-reference-resume-live.md)的新版外部运行器同样沿此公共owner记录SourceMarketProcess，业务更新仍由日线状态及原请求/结果说明。

## 独立观衡Web日志

`scripts/runtime_templates/observer-web.py`的本运行代owner在原`web.log`入口接管stdout/stderr；沿标准库`RotatingFileHandler`同步追加和轮转，不增加服务、线程或队列。默认当前文件和三个数字备份各最多4MiB，本系列总量最多16MiB。按实际UTF-8字节计数，Windows换行不扩展字节；每次write按最多16384个字符分片，无换行长输出也有界。升级遇到本系列超限旧文件时保留最新可解码UTF-8尾部，文件名和原文本读取方式保持。单次旧尾部读取最多4MiB；日志owner不积累输入正文。

文件打开、轮转、追加或flush失败时，本代日志停止后续磁盘追加，只累计丢弃字符数；独立Web继续处理读取和正常停止，日志结果不控制WT。首次故障及关闭时尝试原子写入同代`web-log-status.json`，记录closed、ok/degraded、预算、确认追加字节、丢弃字符和固定错误类型。故障后的后续输出只更新内存计数，关闭状态给最终累计值；磁盘整体不可写时该状态文件也可能缺失，不能据缺失认定日志成功。

stdout/stderr重定向覆盖整个Runner和运行异常处理，在正常及异常路径恢复原流，关闭文件句柄。运行异常以固定类型写入日志，并保留原`failure.json`语义；日志故障与Web运行失败分别表达。原Web文本继续私有留存，不作为公开事件接口。同步磁盘I/O可能延迟本Web，不承诺磁盘挂起时HTTP仍立即完成；WT独立运行。正常关闭沿原App lifespan和OS退出证明，日志只在自己的私有目录留存。历史控制代仍归原控制证据保留策略，本次轮转不删除其他运行代、金融记录或来源Journal。该实现的隔离HTTP主链已核；已随[独立Web117](../releases/2026-11-06-observer117-runtime-live.md)正式采用，现场尚无输出时按延迟创建语义保留未发生实际追加的边界。

## 当前覆盖与采用边界

分钟collection/history的父运行器已随[program021/data-service006](../releases/2026-11-06-minute-counter-quality-live.md)采用Runtime18，两个ProcessEventLog系列均实际落盘。其他仍使用旧wrapper的独立角色继续保留原状态/失败收据；本次采集更新不授予全角色日志已升级资格。

| 调用链 | 当前已核覆盖 | 仍需完成 |
|---|---|---|
| QMT通信 | 请求/结果、原身份、终态及部分错误在原Journal/回执中 | 业务失败与运行日志的完整关联核查 |
| 原生日线/分钟和分析发布 | 原数据/快照、候选、发布身份、状态和失败文件；日线21的SourceMarketProcess启动/ready已落盘，分析来源票据过期及后继真实发布可沿原slot和capture_id关联 | 全范围价格覆盖及后继真实收盘辅助生效继续验真 |
| 唯一策略/回测 | 逐角色覆盖、分支缺失/无交易原因已交付；两份修正后Native长回测及正式读取器已采用，旧报告兼容 | 本代自然策略计算和模拟结果的实际诊断继续核验 |
| 受管进程 | 原CLI诊断、有界持久ProcessEventLog及独立复查通过；Runtime14.4和日线21已普通安装并核新日志落盘 | 其余仍运行旧版wrapper的独立角色保留原状态/失败收据；未声明全部角色均已升级事件记录器 |
| WT委托/成交与账户 | 原标准执行和券商查询/回报事实 | 继续核最新策略自然计算/目标到实际模拟结果 |
| 独立观衡 | 117版实时诊断/报告读取及有界Web日志已独立采用，实际API读回5份报告；本代日志尚未发生输出，真实轮转/写失败资格按匹配源码的HTTP隔离链复用 | 用户截图中的页面加载和市场观察更新问题按主线顺序后置 |

覆盖表分别表达已核范围与未核范围。原反例见[候选验证](../evidence/2026-11-05-process-log-retention.md)，采用身份和线上证据沿上述独立发布记录；历史异常原文与已回收的旧内存输出无法追回。
