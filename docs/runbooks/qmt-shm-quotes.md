# 共享内存报价装配与停止

类型：运行手册。适用范围：报价组件装配、核验、停止与回退。

1. 从发行清单核完整组件、Native DLL 和解释器的 SHA，使用新的发布目录。保留历史 Reader、Writer、数据与既有模块。
2. 复用 WT 受管的 HPR full_tick Host。核原实际 signed binding、完整 profile 及 retention 状态。有限 v6 选择 guanheng.shm-quotes.v1；可回收 v6 选择 guanheng.shm-quotes.retained.v1。后者要求生产者完整 read_retention，容量按原生产者配置。
3. source-shm-quotes 的 quotes 固定 DLL 路径/SHA 和受控连接配置；history 采用原实际历史配置。SourceMarketProcess 的 entry 使用组件 source_market_service.py，运行解释器采用固定独立 Host 角色。descriptor 绑定 service/source/Native 摘要。
4. 沿 MarketClient 验证 capabilities、quotes.query 和原 history 请求。核来源绑定、来源时间、价格与量额单位。真实行情时效由实际来源验收；SDK 样本只用于隔离验证。
5. WT 按原 stop/closed 和有限截止关闭服务，组件不管理 QMT 登录与策略界面。报价未知时保持同一 Native owner/原请求身份；跨进程未知续接需单独验收。消费确认表达 Native 已持有完整快照，外层 HTTP 客户端收取状态由调用者处理。

回退时在原 owner 确认停止后切换固定旧组件与 source 配置，再由 WT 原装配启动。原 Host 读取责任、失败记录与旧数据保留。保持数据原时间，避免将旧快照显示成新来源结果。实机操作及金融权限沿系统受控授权。
