# 2026-10-21 分钟持久接纳与业务链进展

类型：开发验证记录。状态：pending-verification；数据库整链、独立审查及生产部署尚未完成。客户端规格为 [MWC](../specs/retained-minute-consumer.md)，owner 最终规格位于观衡服务仓库 `docs/specs/retained-minute-admission.md`。

## 当前实现

SDK 0.9.0 新增独立分钟接纳客户端、worker 和显式部署工厂。原 MarketData 增加单事务接纳、来源绑定、批次收据和消费游标，复用原 bar/feature/outbox；原 Strategy 核对持久来源与收据事件归属。受管证券的分钟图表选择绑定版本，缺数据返回空，停止拼接另一来源的报价。

本轮服务修改位于 `E:/workspace/qmt-worktrees/wondertrader-service-adapters`，原 QMT 主工作树保持只读。全部分钟业务接纳测试使用隔离配置和合成行情；真实 428 条 QMT 样本属于独立来源证据，不用于代替本轮恢复验证。

## 可复用证据

SDK wheel：`build/native/client-sdk/artifacts/dd3654275fd0436eb5a6db5a3abd09f1/guanheng_market_client-0.9.0-py3-none-any.whl`，SHA-256 `390563af115c7cfa13cc5cd1315eb2597f32b075035685f2e6aed0097d5fa475`。同目录 receipt 绑定13项打包输入。既有SDK构建6项、安装隔离3项结果位于 `build/native/minute-sdk-validation/c75db5a144364fca8b895bb3642f9641/`；安装CLI场景只证明构造与有限正常关闭。

本轮重新通过官方构建脚本 configure，随后执行已注册的 integration.minute_worker、integration.minute_factory、integration.minute_sdk_flow，3个CTest组全部通过，8.17秒。原始XML、日志及当前输入摘要位于 `build/native/minute-ctest/3bacf15023b54a83b1a16661a76f2a73/`。执行前逐项核对 wheel 收据中的全部源码摘要及 wheel 摘要一致。这证明新注册的SDK测试可由CTest执行；未据此刷新原生完整包资格。

QMT普通回归执行 `pytest tests/phase4 tests/phase2/test_market_features.py tests/phase2/test_rule_strategy_consumer.py tests/phase22/test_market_chart_projection.py -q -p no:cacheprovider`，观察为315通过、10跳过；跳过的外部DSN用例不计入真实PG资格。该次控制台观察尚未形成最终送审输入收据，正式审查前需由工作流登记匹配证据。

## 数据库验证及恢复缺口

工作流真实隔离PG运行 `20261021T134539-f85a6faf3533` 收集并执行22项，因日历fixture未提供开闭市时间而失败；已补正确时段，尚待重验。收尾恢复物理快照时文件材料化超时，5,844个文件完成5,839个，恢复目标容器尚未创建；源容器、快照和partial保留。

后续运行 `20261021T135148-16873c6c152c` 在测试准入前被原current资源占用阻止，没有执行pytest。原恢复API缺少创建目标之前失败的完整保留收尾入口；正在原设施所有者中补齐并验证。归档容量为8，当前7份；停止并封存源后下一次新建将触发最旧归档清理。未删除归档、改容量或绕开原provider。

运行记录根为 `E:/workspace/qmt/generated-worktrees/23e357a17262e143/workflow/minute-owner-check/wt-minute-admission/`。开发阻塞归测试设施恢复，不能将这些失败记为分钟业务已通过或生产故障。

## 后续验证

完成测试设施恢复后，通过原provider执行接纳并发/崩溃、真实HTTP、安装wheel及NATS/原策略/图表用例；新连续场景覆盖提交成功丢回复和进程重启。执行跨仓独立full审查，并将最新SDK与业务改动纳入重新打包的匹配证据。当前未部署、未重启生产终端、未下单或撤单。
