# 观衡a91与统一指数日线

类型：实际独立发布。入口仍为 http://127.0.0.1:18143/ ，版本`0.1.0a91+sources.1`、源码`79b8c5c`。总览沿a90紧凑账户布局，策略内容保留在策略页。

## 读取侧与数据来源

SDK0.16接收已冻结的日线公开提供者及分段证据，App仅扩展日线provider；分钟和快照沿原合同。已安装App通过常驻WT18148读取全部50指数最近60根，均到2026-11-02；同一实际调用链复验原股票300308和ETF588170日/周/月共6项，尾日与数值保持。公开提供者和Mixed不标成QMT，unknown价量额单位保持unknown。

8张指数背景已采用到市场观察7668快照，24组指标覆盖到11月2日；年、季、月报按实际报告期保留。高管资料为已披露变动的回溯统计，非盘中实时；本轮外部来源共享登录超时仍保留旧值，独立盘后更新后继继续。

## 实际制品与运行定位

- ZIP SHA256：`dd139219d4b0bfc425249eb5f5d62a5900dd8ae155e00fb6120d8165a64de539`；清单SHA256：`d1b47c3fa28c0c8549d25c23ccf6d0b4b121fb20df8f43d9985e929f48df1be3`。
- 安装收据SHA256：`b473790263062fed8516a8830f0bc7ef49c7b33f20a958fcb0a5b6bfaeb66f09`。读侧WT纯包为`0.1.0a11+read5`，仅更新SDK依赖元数据，不升级正式交易运行实例。
- 稳定维护定位：`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`；实际profile为`observer-controlled-web-20261102-a91-sources-001/web-profile.json`。当前Web PID8076，创建时间与控制身份沿DEPLOYMENT共同核对。
- 指数历史WT：`E:/workspace/wondertrader-data/wt-index-daily-20261102-001/DEPLOYMENT.json`，控制`b8cfd471-eca2-4ccd-8fc5-6ef37ccb169f`，实例`10ff828e-aa90-4828-aa96-d9c2f1417731`，配置SHA256为`e50cc7eb888e6c8857df20d864c0d2fe1d36f19de647abdd157eb47f9a9d115e`；运行PID36972、启动器53656。
- 指数组件及配置沿已冻结SOURCE-CAS-003。首次启动因操作脚本缺少控制父目录而在组件创建前退出；补齐原要求目录后按新控制身份启动，原失败记录保留，未修改WT框架。

新App实际HTTP已核上证、深证成指、中证全指和原股票/ETF五项；真实浏览器核上证60根、11月2日、来源日线，pageerror=0。a90关闭时Web与启动器均exit0、shutdown_complete=true。个人观察原件保持，QMT、原行情采集和正式WT生命周期均未由Root更改。证据在`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`的INDEX-APP-CONSUMED、A91-DEPLOYED及A91-PAGE-VERIFIED。

## 仍在处理的交易故障

a90接收resume11时账户和策略已就绪；其执行器在21:01:43再次意外退出，原运行监督链随后关闭其他组件。本次a91接收保留此真实故障状态：现金余额633,075.20元仍可读，当前可用资格取消，不显示为在线。

交易侧已将失败摘要核对到`qmt_trade_binding_changed / StaleSession`：账户读取接受新绑定后，交易查询/事件仍持旧绑定。自有只读连接换代修正及恢复继续，当前不把正常启动后的短时就绪当成持续运行完成。QMT策略分析输入的v7/v8接线亦继续；本次未发单、撤单或修改WT框架。

维护、独立启停和回退沿[观衡运行手册](../runbooks/observer-runtime.md)。a90原profile仍可在正常关闭a91后使用；它绑定原18147和同一故障交易身份，回退不会修复交易故障。后继正式WT身份须先通过实际来源读取，再准备新观衡profile接收；已安装版本与交易生命周期分别管理。
