# 标准 QMT 插件与查询优先运行组件

类型：开发操作手册。范围：正式可选插件、原生执行上下文及正向整链。状态：开发主路径已验；生产策略宿主、完整交易恢复与独立发行继续。合同见 [STQ-P10](../specs/native-qmt-standard-trader.md)。

## 构建

使用既有固定来源工具准备上游加已批准差异的快照与自有快照；依赖沿原锁定目录。以下为配置示例，路径替换为该次可信快照；在已有 MSVC x64 受管构建环境执行：

```powershell
cmake -S "<owned>/cmake/native/qmt_standard_product" -B "<new-build>" -G Ninja `
  -DCMAKE_BUILD_TYPE=Release `
  -DGH_FIXED_UPSTREAM_ROOT="<approved-upstream>" `
  -DGH_FIXED_OWN_ROOT="<owned>" `
  -DWT_DEPS_DIR="<locked-dependencies>" `
  -DBUILD_TESTING=OFF
cmake --build "<new-build>" --target GuanhengStandardTrader GuanhengBrokerQueryContext --parallel 2
```

产物为 `bin/traders/TraderQMTStandard.dll` 与 `lib/GuanhengBrokerQueryContext.lib`，未带测试注入宏。旧 TraderQMT 工厂与原默认模块保持。该独立 CMake 入口尚未接入 native.py 的统一 profile/package 路由，正式发行流程继续；开发构建不能当作发布完成。

正向驱动只在显式 `GH_STANDARD_CONTEXT_MAIN=ON` 时构建，目标为 GuanhengBrokerContextMain；它不随产品安装。运行 [run.py](../../tests/integration/qmt_broker_context/run.py) 必须提供实际 exe/dll、独占新输出目录及原 uptime 截止；使用原有真实 WinSHM 夹具与 SDK 替身，禁止借用实际券商配置。

## 宿主接线

同一份交易配置显式选择 `module=TraderQMTStandard`、`order_context=query_first`、`position_by_query=true`，其余固定账户、绑定、权限和资源字段沿 [TraderQMT说明](../../src/TraderQMT/README.md)。配置本身不授予真实委托权限。

1. owner创建 BrokerQueryAdapter 和 BrokerQueryLocalExecuter，维持BaseDataMgr、策略sink及DLL的生命周期。
2. 原 Adapter.init 成功后，从实际Standard DLL取得实例API及begin/end/inspect函数，在run之前bind_context；模式只读同一份配置。
3. 调用原run，之后在owner循环pump/wait，原WT依次推进P/O/D/A，ready后策略才能执行。query_first执行器采用poolsize=0。
4. 执行器原getPosition使用已批准查询持仓模式；getOrders/getUndoneQty使用完整券商ORDER投影；buy/sell由原WT执行并经过同一次提交组。当前取消仍走原Adapter，完整取消刷新与终态组释放继续。
5. 停止新业务后原release，确认Standard已Closed/join/drain后再通过实际Factory删除API；随后释放上下文、BaseDataMgr和DLL。超时保留实际借用资源。

缺省/native选择原订单上下文。断开后查询投影不可用；完整重连与再次调仓不得由手工清零责任或重新生成命令ID绕过。当前正向结果见[验证记录](../evidence/2026-10-27-qmt-standard-product-main.md)。

后继 [STQ-P11](../specs/native-qmt-standard-trader.md) 已提供确定SDK返回后的终态O→自动后继P→WT交付→下一组，成功实证见[连续两轮](../evidence/2026-10-27-qmt-next-cycle-main.md)。它采用券商P，不按成交计算；当前查询订单直接撤单的入口仍是待批准提案，完整恢复继续。
