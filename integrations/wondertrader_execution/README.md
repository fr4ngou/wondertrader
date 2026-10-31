# 执行候选的已批准WT覆盖

本目录维护模块B执行候选的固定来源覆盖。上游基线为
`08b230dd05facf6d650d949bfe51054115a2ecb1`，许可证沿仓库根`LICENSE`及原上游。

`managed-cta-account.patch`固定既有受管CTA关闭、Ticker初始化及查询权威路径，
对应CORE-004、CORE-007、CORE-009和既有position_by_query批准范围。
股票借用引用覆盖继续使用相邻`wondertrader_stock_reference/stock-reference.patch`，
对应CORE-011。允许文件集合、原Git字节摘要、规范化后的结果摘要及两个覆盖摘要
统一列在`config/execution-product-build.json`。

这些覆盖与已验Native006选择的19份框架文件逐内容相同。本次把既有选择固化为永久
构建输入，框架工作树保持原状。构建器从固定Git对象开始，只在本次隔离快照的覆盖
文件内统一LF，关闭Git自动换行转换，严格检查覆盖范围及最终摘要。
旧build目录仅为历史核对依据，构建器不会读取旧源码、对象或库。

永久入口及实际资格见`docs/runbooks/standard-execution-build.md`。构建完成、安装后
业务验证和生产切换分别登记。
