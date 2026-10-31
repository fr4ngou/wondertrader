# 独立分钟消费者与原行情持久接纳

类型：候选规格。状态：proposed，职责复核期间暂停默认接线。所有者：观衡行情接入维护者。范围：独立 SDK 中的分钟 worker、接纳客户端、部署工厂及跨服务验收；数据库接纳协议的唯一正文由观衡服务仓库 `docs/specs/retained-minute-admission.md` 维护。当前实施以[原生行情消费者](native-market-consumers.md)为准；本文保留未发布候选的契约，不把PG副本或其收据作为WT读取前置。已有代码和证据保留，整体业务链尚未验收。

## MWC-R1 系统位置

安装后的 `guanheng_market_client` 组合原 StrategyMarket、权威分钟日历、原生行情 HTTP 和 MarketData 接纳接口。MarketData 持有原 bar/feature/outbox、来源绑定和消费确认；worker 持有一次运行的订阅与待确认请求。账户、订单、成交和幂等事实继续归原业务所有者。基础 wheel 使用标准库，正式工厂的证据存储依赖通过 storage extra 显式安装。

## MWC-R2 扫描和接纳

启动读取并验证 owner checkpoint，从其 committed_after 建立订阅。扫描终点同时受真实闭合时刻、owner 与本地分钟跨度上限限制；预热阶段另受 live_after 限制。真实 as_of 与扫描 until 分离，历史追赶不能伪装当前分钟。成功批次携带稳定 batch_id、after/through/calendar_version；有权威证明的空段也需要接纳确认，未知空段保持未推进。

预热 HTTP 副本将 delivery 标记为 historical，保留 SDK batch_id。请求按公开契约规范化数值、冻结摘要并使用独立传输副本；来源、单位和时间语义沿[统一行情规格](strategy-market-access.md)。提交成功及收据字段完整匹配后才 ACK；收据只证明数据库事务及 outbox，后续发布、策略和交易分别验收。

## MWC-R3 恢复与并发

POST 超时、连接中断或解析失败时，先按原 batch_id 查询收据。未知结果期间保留原请求，不构造新的提交身份。CAS 冲突时重新读取 checkpoint 并重建订阅；已确认但 SDK ACK 不确定时，也从 owner 已提交位置恢复。进程重启以 owner 为准，来源调用和发布不能因重启重复。

SDK、订阅和 worker 在同一所有者线程创建、访问和关闭；同机进程按 stream 使用 OS 锁，跨机竞争由原 owner CAS 裁定。工厂构造不请求网络、不启动线程、不推进事实。信号只置停止标志，当前步骤完成后关闭；关闭只回查未知提交，停止新扫描和重新 POST。

## MWC-R4 预算与部署

严格配置、预算关系、退出码和凭据环境名字规则见[运行手册](../runbooks/minute-worker.md)。每步预留 market 的完整预算和四次 owner 交换；请求及响应分别有 1MiB 上限。错误和日志去敏，永久配置/协议错误与临时不可用分开处理。同步依赖有准入和返回检查；任意用户代码及系统 DNS/TLS 的强制截止由外部进程监督承担。

SDK 独立构建、安装和发布，通过显式源码清单及文件摘要验证制品。WT 原生包与观衡服务分别记录版本；单一 wheel 安装成功不授予整套服务发布资格。

## MWC-R5 验证与完整调用链

SDK 验收覆盖有界追赶、空段、预热/当前分类、冻结批次、回复丢失回查、CAS、ACK 不确定、重复关闭、线程归属、进程锁、真实回环 HTTP、独立安装和默认工厂。CTest 入口为 integration.minute_worker、integration.minute_factory、integration.minute_sdk_flow；新增有界 poll 行为覆盖 strategy_market 原回归。

服务端按其最终规格证明真实隔离 PostgreSQL 单事务与竞争、提交前后崩溃、来源归属及旧消息筛选。连续端到端用例从安装 wheel 出发，经原 HTTP/PG/outbox/NATS/Strategy 到原图表 API；至少覆盖已提交丢回复、进程重启、消息重复而策略意图仅一次。来源为合成值的用例明确标记，真实 QMT 来源及生产页面各自另验。

## MWC-R6 状态、审查与回滚

首次跨服务持久化与恢复契约变更进行独立 full 审查；审查同时提供本规格、owner 最终规格及双方源码，逐项登记行为证据和缺口。部署默认未启用接纳。首次来源切换按 owner 的停旧发布者、排空在途策略处理、绑定新流及恢复消费者顺序执行。回滚停止 worker 并保留已确认数据和游标；旧二进制的可用范围须与数据库绑定一致。

当前开发状态和证据分别见 [NOW](../roadmap/NOW.md) 与[验证索引](../evidence/README.md)，本规格不将测试代码存在视作通过。
