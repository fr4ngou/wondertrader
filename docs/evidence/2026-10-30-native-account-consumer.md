# 独立 WT 到原生账户扫描的真实只读主链

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发隔离验收。状态：主链与正常关闭通过，精确浮点投影待修正。产品源码和 WT 核心改动 0；实际下单、撤单和生产切换 0。

普通安装的独立 WT CLI 管理只读 QMT Host，原 `GuanhengAccountScan.exe` 加载 `TraderQMTReadOnly.dll`，沿原 WT TraderAdapter 发起 position、order、deal、account 四次查询。来源使用新配对和 Journal，保留已验真实 v3 / account policy 1.0 账户范围；QMT 正文继续完全内存通信。真实证券基础资料复用原采集的三份固定文件。观衡包、SPA 和服务不参与。

先以真实 Windows SHM、3.6.8 完整正文及原线程 SDK 替身跑同一原生入口，四查询 2/1/1/1，65 项事实和 30 个 ABI 槽对照一致，原文件/网络守卫调用计数 0。原生 close 和全部进程树、EOF、读线程、句柄实际关闭，164 输入前后与当前摘要相同。

根会话统一执行真实探针启停。四类来源返回持仓 4、委托 0、成交 0、资金 1。原生 20.177 秒 exit0，completion 为 closed/joined=true、worker_live=false、queued=0、error_code=ok。WT 与外层 59.180 秒正常退出，实际树空、双 EOF、读线程 join 和资源关闭；原探针停止并逐字恢复，HPR 实例保持。160 项业务输入及 644 个安装成员前后相同。账户明细、原生 stdout、凭据和 Journal 仅存私有 ACL 目录。

停止后的只读不可变 Journal 核对发现，4 个 position 浮点 facts 与原始值存在 1 ULP 差异；原请求 ID、结果 SHA、执行区间、运输绑定，以及资金/持仓数量保持一致。严格等值审计保留失败。冻结原 RapidJSON 头的有限复现表明，默认解析/编码两轮准确重现全部 4 处变化，完整精度往返保留全部 36 个来源数值。这是自有 JSON 数值读取边界的精度问题；后继统一修正 Common、Bootstrap 与 AccountScan 的 DOM 读取，使用新制品和独立身份复验。现有 WT 框架保持原样。

原件位于 验收目录（外部历史/待归仓路径：`../../build/wt-native-account-consumer-001/README.md`）：`sdk/{RESULT,AUDIT}.json`、`real/{RESULT,EXACT-AUDIT-FAILED}.json`、`precision002/run.log`、各 `control-*/build-trade-product-main009/result.json`、`INSTALLED-BEFORE/AFTER.json` 和 `DELIVERY-001.json`。原构建总 receipt 的 pipeline 阶段失败仍单列，本轮复用已实际通过既往真实账户验收的固定 EXE/DLL，不授原 pipeline 或完整 45 场景资格。

本轮四查询各有独立执行区间，继续保持账户聚合观察与交易日/券商会话未知语义。不授完整恢复、策略运行、观衡页面、真实交易或生产资格；004 旧 Host 故障根因继续 unknown。

## 后继精度修正

三处自有 DOM 边界现已统一启用 FullPrecision 并补中文注释，WT 核心保持原样。新制品、红绿根因回归、原两个 CTest、独立普通安装 SDK 主链及原真实数值的合成绑定 replay 均通过；replay 的 67 facts/39 ABI 精确相同。离线 ZIP 在新根安装后，实际执行同一 SDK 原生四查询并正常关闭。具体源/制品/安装身份和回退步骤见精度切片交付（外部历史/待归仓路径：`../../build/wt-native-account-precision-001/README.md`）。修正制品的真实 QMT 资格由根在新私有配对中独立验收；旧失败审计继续保留。
