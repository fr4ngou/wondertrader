# 持续分析窗口同配置正常重启

类型：验证证据。范围：[AWP4](../specs/qmt-analysis-window-producer.md#awp4-同配置重启与唯一发布者)。状态：模块 SDK 主链完成，独立审查及最终系统包继续。

旧 a3 使用 `OWNER.json` 的排他创建表示拥有权，正常退出保留该文件，第二代同配置 WT 在创建阶段失败。`build/root-analysis-restart-001/red004` 实际两代 ready 为 true/false、退出为 0/2，未启动 Source。

a4 在 AWP 层直接复用 WT `_InstanceLease` 的 OS 文件租约，持有到发布线程及 Native 资源确认关闭。OWNER/status 转为代际记录，旧 REQUEST 和成功窗口保留；重启恢复原 Pending 身份、核旧发布 SHA，原实收时间保持。WT 框架、Host 和 Native/QNA 算法保持。

`build/root-analysis-restart-001/normal005` 使用普通 a4/WT a10/Host a11/Agent a9，同一 WT 配置及其 SHA、owner 根和发布位置四代运行：前两代无 Source ready 等待；第三代沿原 Pending 经真实 WinSHM、3.6.8 正文的 32 个 SDK 替身调用，原 Import/Reader 生成 8870 日线、QNA/R24 读取 3208 行；第四代无 Source 恢复同文件 SHA 和原实收时间。四代正常 exit0，全部组件闭合。`RESULT.json` 与 `ACTUAL-001.json` 分别保留两代重启和后继业务证据，输入前后逐项相等。

普通安装回归使用真实 OS 租约，核竞争者无法改写活动状态、关闭尚未 join 时继续持锁、释放后恢复原 capture，以及进程直接退出后允许新 owner。单轮预算和首次关闭截止保持原实现。

包声明稳定 API 范围 WT `>=0.1.0a9,<0.2`、bound Host `>=0.1.0a11,<0.2`。本次安装 lock 精确固定每个 wheel 版本和 SHA；当前证据仅授上述具体组合，后继 WT/Host 安装由根单独组合验证。真实 QMT、交易、生产及最终发行资格继续单列。早期 QA 状态读取准备失败原件保留，未作为产品失败或通过证据。
