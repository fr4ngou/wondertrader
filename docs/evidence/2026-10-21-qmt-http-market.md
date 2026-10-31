# QMT HTTP 行情与独立服务验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-21。范围：[HTTP-R1–R7](../specs/qmt-http-market.md)。本轮开发与隔离制品验收通过，真实 QMT 来源和生产服务切换保持 pending-verification。

## 结果与源码身份

仓库 `E:\workspace\wondertrader`，分支 `codex/qmt-migration-plan`，HEAD `08b230dd05facf6d650d949bfe51054115a2ecb1`。保留原工作区变更。本轮没有提交、推送、账户操作或生产发布。

最终原生输入摘要 `8b02bf15cb1db2522f5dae35afbdf530b1fb61a3f5fa60ec9f618f0c4bb1c894`。独立 full+delta 审查批准，四项 P2 均已关闭，32 个审查输入逐字节复核匹配。最终 DLL SHA-256 为 `e6d377240d9c990ff0cf5ad4de8c05d4cae80982044aa4b48db7269314c9beab`。审查报告与原始收据（外部历史/待归仓路径：`qmt-http-2026-10-21/README.md`）。

## 完整实现与根因

原生 `QmtHttpClient` 对现有 Gateway 协议签名，固定两项只读操作、显式 false 参数、单次 POST 和同 ID 有界结果领取；异步 WinHTTP 保证总截止及取消后的对象生命周期。`QmtHttpEndpoint` 接入原 Parser、补数队列和 DSB，单位/分钟边界/许可由显式 profile 提供。

源码核实 `qmt_agent/gateway/core.py` 的 `_last_tick_at` 来源是 `_utc_now_text()`；这是 Host 回调存活时间。历史闭合因此改用同会话、同证券 `market.full_tick.time`，实际反例证明较新的 Host 时间不能把较旧源 tick 尚未证明的分钟授予闭合资格。DataFrame records 缺 time 时明确拒绝，保持真实源语义待验。

独立 `guanheng.market.v1` 服务通过 JSON C ABI 调用原生模块，观衡标准库客户端只依赖 HTTP。存储初始空状态转换为明确 Unavailable；成功窗口保留来源、资格、单位和覆盖。补数范围单次最多 72 小时，长历史由受管作业分窗；QMT 主来源、TDX 可选辅助，来源不静默混合。

独立审查关闭四项根因：快照证据在公共投影丢失、成功回复遗漏请求证券、原生 Store 错误泄露配置根路径、Tushare 成功响应可能回显凭证。修正分别位于公共 DTO/严格客户端、ABI 错误出口和辅助源响应边界，均包含原触发条件回归。

## 实际验证

执行 `python -B scripts/native.py all --offline --jobs 4 --qmt-source D:/workspace/qmt`，14 个阶段全部 passed：编译、CTest、流水线测试、安装及全部搬迁包链路。CTest 41 个启用项通过、0 失败，另 1 个既有全天用例 Disabled。流水线 24 项通过。文档门禁、适用 Ruff 和差异检查通过。

新 HTTP 协议 14 项、原生端点 6 项、服务/客户端及辅助源 19 项均通过；这些属于上述 CTest 的内部场景，不与 CTest 总数重复相加。独立审查也实际运行这些入口，纯原 QMT HMAC/DTO oracle 已开启且无跳过。

实际隔离链路为真实本机 HTTP Gateway 替身 → 原生适配/补数队列 → 原生 DSB → 独立 HTTP 服务 → 标准库客户端。搬迁包独立运行得到 3 条 Complete 分钟，数量 `200/300/400` 股、金额 `22000/33000/44000` 元；快照保留 NativeVerified 与 profile/单位，401 认证负向和真实坏 lease gate 的 IO 脱敏负向通过。既有分钟、受管执行、原 Console/Portfolio shadow 与 WT 原核心回放继续通过。

## 开发制品

制品 `build/native/packages/dev-20261021T020435Z-6bb44131.zip`，4,961,947 字节，SHA-256 `1b9ce2e53c2950b0579e5c1ea5db220ea083f01e939a279465c6dfb877fd9e54`。解包校验及包内独立行情服务全链路通过；这是开发制品，正式发布与真实服务切换分别验收。

## 实机及 Tushare 观察

只读核对原受管配置的 Gateway 地址为 `host.docker.internal:18010`；本机两次核查该端口均无监听。原生探针使用合成凭证对 `127.0.0.1:18010` prepare，约 1014ms 返回 Timeout，未产生来源身份或能力。本轮未启动或修改原 QMT 服务，因此没有真实 QMT 连通、真实十年数据导入或生产行情资格证据。

已私下核对运行环境 Tushare 凭证与用户提供的一致，不输出值。HTTPS 固定历史样本首次股票日线返回 1 条、股票 1 分钟返回 2 条；ETF 分钟被拒绝。后续探测股票分钟受到限频/额度拒绝，ETF 分钟受到权限拒绝，来源码均为 40203。首次条数来自工具 stdout 摘要，后续脱敏原始收据已归档；未保存原始行情或凭证。此结果证明有限样本读取，不证明全量历史、分钟边界、实时权限或生产许可。最终凭证回显回归使用合成密钥，仓库 1223 个文件检查无实际 token 匹配。

## 剩余边界

- 共享内存与 WT 绑定、通达信交易依用户决定暂缓；HTTP 受管交易仍需原子快照已吸收游标和连续恢复契约，保持禁写。
- 真实 QMT 的 epoch/time-column、单位/profile/许可、源会话恢复及分钟覆盖需终端验真，十年历史按分窗作业导入。
- 观衡服务保持独立发布；本轮交付的是接口和[逐服务适配地图](../migration/business-adaptation-map.md)。完整策略的组合上下文、持仓周期、检查点及 QMT-only DTO 等仍需分别接线；没有切换现有业务服务或页面。
- 当前独立服务仅绑定回环；跨主机/容器访问需要受管 TLS 入口及网络验收。历史持久来源严格校验，来源变化后的版本衔接需显式核实，不能静默改写旧来源。
