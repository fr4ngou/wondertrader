# 受管分钟消费

类型：模块说明。状态：实现与隔离开发验证；真实业务和生产资格以对应证据登记。所有者：独立行情消费者维护者；持久事实所有者为原MarketData。

## 职责与接口

`guanheng_market_client.minute_worker.MinuteWorker` 组合 `StrategyMarket` 和 `minute_owner.MinuteOwnerClient`，从原owner已提交游标读取闭合分钟并等待持久确认。`minute_factory.build_worker/create` 构造受管依赖；部署见[操作手册](../runbooks/minute-worker.md)。来源读取和分钟语义遵循[策略统一行情规格](../specs/strategy-market-access.md)；接纳协议的唯一正文位于观衡服务仓库 `docs/specs/retained-minute-admission.md`。

```text
独立wheel worker → StrategyMarket/权威日历 → 原生行情HTTP/DSB
                 → MarketData checkpoint/batches/receipt
                 → 原bar/feature/outbox及持久游标
                 → 原消息与策略消费者
```

公开Python接口为 `MinuteWorker.step/close`、`run_worker`、`MinuteOwnerClient.checkpoint/submit/receipt`。实例在创建线程使用；无额外线程或本地行情/消费账本。闭合分钟来自源1m OHLCV，量额已经是股/元，来源系数仅保留为证据。客户端行为和跨服务验收要求见[独立分钟消费者规格](../specs/retained-minute-consumer.md)。

## 状态和恢复

第一次step读取checkpoint，核对stream、显式policy SHA及日历绑定。后续扫描从committed_after到本地与owner上限允许的until；预热限制在live_after，HTTP副本全部historical。当前分类仍取真实as_of，权威空范围也提交。

请求先规范化数值并计算摘要，传输使用脱离保留对象的副本。POST结果未知时先查相同batch收据；确认stream/policy/批次/请求摘要/前后游标/revision/数量后ACK。若ACK结果不确定，重读owner checkpoint重建本地订阅。CAS被其他worker推进时刷新checkpoint，丢弃旧本地订阅后继续；绑定或收据冲突保持明确失败。重启一律读取owner位置，禁止用最大bar时间替代游标。

Committed证明MarketData事务及outbox已接纳；消息发布、下游策略消费和交易另有状态。worker没有账户参数，未赋予交易权限。bars与来源谱系经原协议校验，批次级content_id不等同逐bar独立DSB证明。

## 并发、预算和退出

本机OS锁按stream隔离，跨主机依赖owner CAS。SDK、订阅及worker在同一线程创建、使用和关闭；signal handler只置Event。停止后不开始新poll；当前步骤结束后仅回查未知请求，关闭不重投POST。

每步容纳完整market预算及四次owner交换，HTTP请求/响应各1MiB。依赖调用前后检查截止；无抢占任意用户代码、DNS或TLS阻塞的承诺，硬截止归进程监督。关闭仍有未确认请求时退出码4，并由后续进程从owner恢复。

## 验证与边界

CTest入口为 `integration.minute_worker`、`integration.minute_factory`、`integration.minute_sdk_flow`。分别验证范围/未知结果/真实回环HTTP与CLI、实际依赖零副作用构造、实际wheel安装与依赖隔离。基础导入不加载minio/urllib3；工厂显式选择storage extra。源码/制品摘要由SDK构建收据绑定。

安装测试中的CLI刻意使用不足以准入一步的有限运行预算，验证入口和正常关闭；实际来源、MarketData事务、消息与页面完整调用链必须通过另行端到端证据证明。
