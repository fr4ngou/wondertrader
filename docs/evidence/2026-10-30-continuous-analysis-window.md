# 持续分析窗口 SDK 与普通安装主链

类型：验证证据。日期：2026-10-30。状态：SDK 主链已通过，独立审查和根来源组合分别登记。规格为 [AWP](../specs/qmt-analysis-window-producer.md)、[provider](../specs/qmt-analysis-window-provider.md)、[QAS](../specs/qmt-analysis-source.md)。源码/依赖冻结入口位于 `build/root-analysis-window-producer-001`。

新增独立 producer a2、固定原 QNA/Import core a1，依赖 WT a8；显式 bound extra 使用普通 Host a11/Agent a9。原 QNA、Import、Reader、R24 和 WT 核心保持。普通安装主链 `E:/workspace/wondertrader-qa/root-analysis-window-producer-001/installed002` 在独立解释器和空 worker cwd 运行，产品与消费模块来自 site-packages，791 项输入前后相同。

三轮分别导入/完整回读 8870、8878、8878 根原日线，经原 IDataReader 与 QNA 发布；R24 消费 3208、3216、3216 条八证券分析记录，基准为 2026-10-28、2026-10-29、2026-10-29。同日修订改变实际收盘/量额并形成新发布 SHA。每轮均保留原候选、NativeRead 和工作进程 Job 收据；三个 Job 退出0、双 EOF、join、整树0及句柄关闭。服务正常停止。

独立 SDK 方法计数共96：每轮8原日线、8原因子、16基准参考；下载/真实 QMT/账户/交易均0。原始市场值取自固定 QNA 市场夹具，新增日期和修订为明确合成源值；算法价格仍由原 Reader 计算。本证据没有历史首次可见或实际交易资格。

普通 a2 `edges002` 在同一服务中实际验证缺源和过旧保留旧窗口字节、两次 Pending 保留同 capture ID，以及后续新实收成功发布。六个合同回归通过；两个 bound 回归证明已执行读取失回执后只 GET 原 UUID（SDK1次），真实本地非法 HTTP 状态行按协议失败。首次 bound 测试夹具使用了错误 route 类型，在任何 SDK 前失败；修正为原 route 三字段后通过，原工具记录保留。

`installation003` 另普通安装了 bound extra 的完整22发行闭包，留供根做认证 WinSHM/3.6.8 正文→本 provider→原 Native/QNA→R24 的组合。本页不把该安装或既有 QAS 三调用证据当成本模块完整来源实测。共享 WRI 接线、实际 QMT、长期存储归档、交易及生产由根单列验收。
