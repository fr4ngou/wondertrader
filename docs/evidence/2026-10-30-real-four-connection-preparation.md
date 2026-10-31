# 真实四连接只读准备

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-30。范围：候选安装的只读联调材料和 SDK 主链。原 QAC 产品源码、WT 框架、当前策略、活动服务与下载保持；真实操作由根会话另行执行并留证。

准备根为 `build/wt-real-four-connection-preparation-001`，固定 `wt-trade-system-candidate-004/installed001` 的 Host/WT 角色和 payload。原真实 read v3 设置来自已验 006 配对；QST/HPR 设置来自 ETF generation-003。每个新配对使用新通信文件名、内存名称、凭据和实例身份。生成与 verify 使用候选 Host 解释器。准备交接时尚未创建真实 Journal 或启动真实 owner；根随后执行了下述一次真实验收。

原 `validate_trade_binding` 在 `trading_contract.py` 要求非空证券规则、live 环境和完整 binding。`trading_kernel.py:trade_admission_error` 在使用 symbol grid 前检查禁止写入；Host `trade_runtime.py:_trade_submit` 对新命令先返回 `writes_disabled`。账户查询通过原 account adapter 的独立绑定，使用完整账户 scope，证券规则不作为账户查询过滤。

根提供的 `RULE-SOURCE-001.json` 记录上交所 ETF FAQ 与 2026 规则链接：510300.SH 正常 100 份网格、价格单位 0.001。真实 trade 只读初始化保留原账户/环境与 read 额度，使用新 binding ID；通信/事件容量复用原产品技术设置，规则只取该来源。Host 和源均禁止写入，协调器没有交易命令 POST。read v3 owner 保持；新增 trade owner 沿原显式 v4/policy2 投影初始化。零股处置、完整交易规则和交易许可未授。

SDK 在完全分离的 `sdk` 目录中使用明确合成身份和行值，同一协调器消费正式单正文、三个 Host、QST 原 Receiver、HPR full_tick，以及候选包内 Scanner/DLL。单轮 15.5670596 秒正常退出，711 输入前后相同，账户 2 持仓/1 订单/1 成交/1 资金的 65 项事实与 30 个 ABI 槽严格一致；浮点逐 IEEE 位相等。SDK passorder/cancel 调用均 0，源码守卫文件/网络计数 0，单 timer/订阅、所有 child/WT/原 owner 与外层物理清理成立。

真实材料、根 `*.py` 和 READY 已按 FROZEN-HANDOFF-001.json（外部历史/待归仓路径：`../../build/wt-real-four-connection-preparation-001/FROZEN-HANDOFF-001.json`） 固定 47 项，SHA `5f33a4bab86dd038fd1548a64042ccd5c329876ad8341ebbb9885e77da98ef0e`。入口和断言见 ROOT-OPERATIONS.md（外部历史/待归仓路径：`../../build/wt-real-four-connection-preparation-001/ROOT-OPERATIONS.md`）。独立审查通过冻结准备材料和 SDK 主链，真实验收单列。

根使用同一冻结安装和正文执行一次真实联调。前三批取得 4 条持仓、空委托、空成交；资金请求终态为 `operation_interrupted`。原生 Scanner 19749 毫秒退出 3，协调器在 `main.py:168` 检测失败，未继续提交 HPR full_tick。四个账户请求各提交一次，交易命令、下单及撤单均为 0。资金中断发生于 UTC 22:23:17；根在本地 06:23:42 停源，相差约 25 秒，当前证据要求保留独立的中断根因。

QST 已真实认证并接收行情批及心跳。收尾后的 QST 状态包含 36 批、6929 ticks 和 15 次心跳；关闭导致的 `connection_ended` 与业务期间的资金中断分别记录。WT、QST 退出 0，逻辑组件全部关闭；内外子树为 0、双 EOF、线程 join 和句柄关闭完整。外层 95.797 秒退出 1，711 输入前后相同。根已停止本次正文并逐字恢复原探针正文，恢复 SHA `35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae`。

实际原件见 `real/RESULT.json`、`real/FAILURE-BOUNDARY-001.json`、`real/PROBE-STOPPED.json` 和 `control-real/RESULT.json`。准备模块已交付，真实四类账户与市场读取全链仍为 `pending-verification`；资金原值审计和 HPR full_tick 未完成。下一步只在新的诊断根捕获原 read Host/Agent 的首故障类型与源码帧，保持本次 Journal 和材料原件。真实交易、完整恢复、分钟新归档及生产资格继续独立验收。

定向诊断材料已在 `build/wt-real-four-connection-diagnostic-003` 完成。它复用原 read Host 首故障 QA 包装器，正式 QMT 正文、原产品和预算保持；仅调整三个 QA 接线文件。固定 600 秒入口的隔离 SDK 链 11.110 秒退出 0，713 输入前后及当前相同，65 项事实/30 个 ABI 槽严格一致、全关闭。唯一 OSError 在 SDK 停源命令之后约 22 毫秒，仅记录为收尾观测。独立 delta 审查无 P0–P3；55 项材料已冻结，真实配对核验及 check-only 通过，真实 owner、Journal、来源与请求均未启动。`diagnostic-001/002` 的解释器匹配、私有诊断父目录两项 QA 准备失败各自保留。

诊断入口及根操作清单见该目录 `README.md`，交付 `DELIVERY-001.json` SHA `cfdf95a4c779b13f745749cdd48d7e27e3a84e72186f97158e43d0b8df1e16b1`；独审 JSON SHA `fb7ba61b2961579cb2f9ad994a236ac54aafd9dfe1ed8780c101f737883a487b`。根单独决定是否执行一次真实诊断。原资金中断根因和完整真实四读资格继续保留 unknown/pending，SDK 诊断成功没有转授修复结论。
