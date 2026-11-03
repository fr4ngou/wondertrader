# ADR-0024 Host HTTP读取生命周期与终态占用

类型：架构决策。状态：accepted。日期：2026-11-03。范围：自有v4交易通信Host及Native账户读取客户端。

## 背景

常驻交易Journal对已经完成的读取持续按最大结果预留计费。现有来源保持运行时，累计预留达到容量上限，后续读取在持久准入前返回503。读取结果的消费与存留由Host和Native负责；来源继续拥有SDK调用。

## 决策

Host配置显式选择http_read_retention，经认证的read-binding公布能力。该选择与Source-profile的read_retention互斥，保持原Source正文、profile、能力摘要及SDK请求。Native复用原票据、内容UUID、原截止、结果校验、消费确认及未知责任保留。

HTTP模式中，Journal对不可变且具有完整结果的terminal行按原请求长度、原结果长度及既有元数据上限计费，在途和缺结果行保留最大预留。原reserved_bytes字段、既有读取行及金融表保持。新读取沿原规则，在已确认消费、票据结束、结果确认且无金融proof引用时回收。预算上限、旧无票据行和未知责任保持。

HTTP能力、Source profile及预算共同冻结到独立Journal保留身份；重开须一致。默认模式和既有Source-profile模式保持原契约。

## 影响与验证

终态占用及结果生命周期有单一Host owner，策略与金融账本保持原owner。原满额数据库副本验证旧行和金融表逐字节一致；Native、Host、WinSHM、策略双代SDK替身链路验证超过容量的查询与消费回收。现场只读恢复和模拟柜台写权限分别验收。接口正文见[AAR6](../../specs/qmt-account-read-retirement.md#aar6-host-http拥有的读取生命周期模式)。
