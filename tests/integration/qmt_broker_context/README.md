# 标准交易链端到端验证

类型：测试入口说明。当前范围：撤单结果后的订单、持仓、资金查询与执行器续接。

`run_cancel_refresh.py`启动真实Host、HMAC、Windows命名共享内存及Source Agent，加载当前候选标准交易DLL和实际WT股票执行器。SDK的查询、下单和撤单由明确的`SYNTHETIC`替身实现；测试账户、共享内存、端口、运行目录各自独立。

原生入口为`cancel_refresh_probe.cpp`。由WT执行器接收目标并下单，下一笔行情触发其原生超时撤单；测试随后核对原WT订单表、查询持仓、实际可用现金、原提交责任及再次委托数量。三个完成场景均不发送order/deal终态推送，要求实际查询取得终态。

| 参数scenario | 柜台替身行为 | 必须取得的结果 |
|---|---|---|
| cancel-false | 原单已撤，撤单函数返回false | WT原订单表清空、现金恢复、通道继续、原执行器再次下单 |
| cancel-error | 原单已撤，撤单函数返回true并产生有账户身份的异步错误事件 | 查询确认终态，通道继续，执行器再次下单 |
| partial | 1000股委托成交200股，余量已撤 | 原持仓100变300、可用现金97998、再次只报800股 |
| missing-current | 当前委托查询省略旧单，未提供历史查询 | 保留原未决身份；新insert在测试中保持暂停。本例只验证身份保留，未证明放开后行为或跨日恢复完成 |

## 运行

使用已验证Windows C++工具链构建同一候选DLL和probe，并提供同批真实`WtExeFact.dll`。probe复用显式历史夹具的`standard_probe.cpp`帮助函数；这份帮助文件应在独立构建目录冻结并登记摘要。Python入口的`--legacy-fixtures`当前仍依赖外部历史测试目录，尚未形成独立CI配方；它提供测试编排，产品模块从当前仓库加载。

```text
<Python绝对路径> -I -B tests/integration/qmt_broker_context/run_cancel_refresh.py --legacy-fixtures <历史tests/integration绝对路径> --exe <新probe.exe绝对路径> --dll <当前TraderQMTStandard.dll绝对路径> --factory <WtExeFact.dll绝对路径> --scenario cancel-false --output <全新结果目录>
```

分别指定其余三个scenario及全新输出目录。外层使用项目`native.run(..., private_console=True)`，保留每次日志并管理进程树。测试有55秒总截止，原生业务阶段24秒；这些值仅属于测试执行预算。失败保留目录，修正后使用新目录。

每例输出`native-result.json`、`fixture.json`和成功时的`RESULT.json`。结果包含业务断言、实际查询次序、SDK替身调用、制品及外部夹具摘要、资源关闭结果。输入文件包含仅本次测试使用的认证参数，按受控测试资料保存。

此入口未运行CTA业务策略、NSQ、观衡页面、真实国信SDK或真实日期切换。上述层分别验收，详见[执行链E2E证据](../../../docs/evidence/2026-11-06-cancel-refresh-e2e.md)。
