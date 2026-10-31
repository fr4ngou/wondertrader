# 中文只读运行状态工作区

类型：功能规格。状态：accepted。前缀：OPS。任务状态：done（当前公开进程与详细采集状态的隔离安装开发验收）；真实QMT、完整F20及生产资格另验，模块C保持active。

2026-10-28 后继授权：采集进程的只读观察接缝、唯一读取器抽取及SDK发行接线交开发者2实施，已完成本切片真实WinSHM/原生Writer/HTTP/生产SPA及独立full/delta。原 ManagedLocalProcess、QMT协议和原生采集行为保持其原owner。

## 目标、根因与复用

F20 的 `/operations` 当前落到 IndependentApp 通用占位。受管进程已有公开 `status()`，独立 SDK 已有 `capabilities()`；缺口在业务投影及生产页面接线。复用 [WT-O01/O02](../development/wondertrader-capabilities.md) 和本仓 ManagedLocalProcess、BoundedReader 与 SDK；不新增进程守护、日志库、存储、交易动作或 WT 核心修改。

## OPS-R1 状态主链

`IndependentApp → OperationsWorkspace → GET /v1/ui/operations/status → 现有采集/Host status 与 SDK capabilities`。进程状态来自当前 App 持有的 owner；页面读取不启动、停止或重启来源。查询服务调用原 SDK capabilities，沿既有读池及一次绝对截止；无配置不联网，错误保持固定中文。capabilities 成功仅证明本次服务响应及声明能力，数据新鲜度和完整分钟另验。

## OPS-R2 时间、计数与覆盖

接口观察时间为本次 HTTP 投影的 UTC 时刻，页面以北京时间显示。来源时间、最近接收时间、状态文件更新时间分别为独立可空字段；缺失显示“未知”及具体原因，禁止用 API 时间或文件时间代替源时间。采集活跃度、接收/处理计数、证券覆盖仅消费公开 owner 契约；现有 App `status()` 未提供时保留 null，禁止读取历史测试结果推断当前运行。

采集 owner 后续接缝需求：绑定当前 control_id、pid、configuration_sha256 的原 status 快照；原始 latest_source_time_ms、回调 observed_wall_time、发布 observed_wall_time、connected、phase、received_ticks、pushed_ticks、native_counts、source_heartbeat、错误枚举及快照新鲜度。共享删除/原子替换继续复用 collection_status 唯一读取器；独立 App 发行接线由采集任务 owner 提供。本切片不越权修改采集核心或扫描历史控制目录。

后继接缝：SDK0.13.0的`runtime_status.read_status_snapshot`提供JSON及同一读句柄文件修改epoch纳秒，旧`guanheng.collection_status`转发到同一模块对象。采集发行闭包与App依赖同时包含唯一实现，App版本0.1.0a4；不依赖源码PYTHONPATH。`QuoteCollectionProcess.observe(deadline)`在读锁外有界读取当前目录，核schema/control_id/实际pid/configuration_sha256，前后续核同一owner身份。未配置不读盘；身份/格式错误及超过65秒或超前5秒的发布快照拒绝。65秒来自子服务合法发布间隔最大60秒及5秒时钟容差，不是报价新鲜度阈值。

API版本`guanheng.operations.v2`。telemetry保留原始`latest_source_time_ms`，`received_at`来自最近行情回调墙钟，`published_at`来自子服务外层墙钟，`status_file_updated_at`来自同句柄文件stat，`observed_at`仅为本次接口观察；全部墙钟ISO值以UTC传输。来源原始毫秒不推导实时行情资格。新字段分别提供快照状态、连接、代际、phase、接收/推送/原生处理数、源心跳覆盖/缺失/队列/溢出及固定原因；缺失保持null。

`active`只表达当前owner监听就绪、有效新鲜快照、connected=true、phase=running且无当前采集/接收失败；页面标为“当前连接状态”，明确持续报价与完整分钟另看相应时间和覆盖。connected=false显示等待或断连，不据累计计数推定当前连接。停止/失败owner优先：允许展示同实例仍新鲜的最后快照，标为停止前记录，active=false；过期则隐藏其值。读取后owner状态再次变化时API重核并降级当前连接。failure.json仅经同一唯一读取器与三重身份校验，公开阶段/异常类别枚举与有限WinError，原消息/路径保留受控环境。

## OPS-R3 故障与处理

显示进程未配置、启动中、就绪、停止中、已停止、失败、未知，标明事实 owner、原因、影响与人工处理说明。仅公开固定白名单进程字段和错误类别；原日志、配置、路径、凭证和上游 reason 不进入响应。某个来源失败保留其他状态。各只读查询刷新中或失败时保留自己的上次成功状态及原观察时间，并明确刷新状态；首次失败提供重读，成功结果按当前返回更新。页面移除pid、资源收束及强制回收明细，这些字段保留于内部诊断材料。

## OPS-R4 验收与边界

先跑独立安装的真实 App HTTP→原 owner→生产构建 SPA 主链，再覆盖未配置、停止、失败、超时、恢复及未知契约。API 只注册 GET；页面只有重新读取按钮。核中文、无旧系统请求、窄屏、控制台异常、关闭后监听与线程收束。复用既有采集生命周期证据；本次不连接实际 QMT 端口/共享内存，不启用常驻生产采集，不下撤单或发布。

## 实施步骤与完成状态

1. 冻结本规格与公共接线范围：app.py 导入/注册专用 router、将已有配置错误事实传给 router、operations capability；IndependentApp 懒加载及明确路由。
2. 实现只读投影、原 SDK 查询及中文页面，验证安装主路径。
3. 集中边界回归、审查与文档检查，将实际证据回写 [专项证据](../evidence/2026-10-28-operations-workspace.md)。本任务状态独立登记，公共 NOW/CURRENT 保持其汇总 owner。

已完成上述实现及详细状态接缝的隔离安装验收，实际模拟报价、时间/计数/覆盖、连接/断连/停止及重读均已取证；当前真实QMT来源与完整F20继续独立验收，不据此声明生产启用。
