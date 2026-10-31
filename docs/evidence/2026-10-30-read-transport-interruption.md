# 只读共享内存中断：逐代双端诊断

日期：2026-10-30。状态：实际根因 unknown；诊断模块离线准备和 SDK 验证完成，真实诊断与产品修复待验。

原件为 `wt-real-four-connection-diagnostic-003/real`。唯一 position 请求于 UTC 22:39:48.133630 受理、50.008350 派发、52.014249 返回 Host 合成的 `operation_interrupted`，没有原生结果绑定。旧全局首 OSError 于 42.015912，早于该请求受理约 6.118 秒、派发约 7.992 秒。其记录缺少该异常所属 runtime/transport generation，当前证据不足以把它关联到此请求。原数据库 SHA `159b8746882b522f6329e8384f469c6fd38476069be9ab735c31b0065ac4adb1` 保持；仅复制到新的受控目录并使用 immutable/query_only 冷读副本。

准备根 `build/wt-read-transport-rootcause-001` 保留冷证据和旧诊断；`v2` 验证逐代反馈，`final` 保留前一冻结材料，当前交接使用下文 `final2`。产品源码、WT 框架、原协议、额度、Journal 和未知请求责任保持。Host QA 记录实际加载的共享 Agent 库深层帧、有限 Windows 错误码、本端 stop/对端关闭位；逐 runtime 对象记录 worker 进入、每代首异常、active 请求原 UUID 摘要、原 binding/transport generation 摘要及退休时间。

QMT 临时诊断正文保留原正式 pair 完整前缀，再追加独立有 SHA 的纯内存观察尾段。原 SDK callable 只在原策略线程调用一次；观察器记录进入/返回/异常及同 UUID/运输代际摘要、read worker 首异常和显式 close 调用栈。已有 print 输出固定 schema 的元数据；账户参数、金额、行值、异常文字和凭据均不打印。文件与网络入口调用仍为 0，原单 timer/单订阅保持。原正式 pair/body 验证不变，诊断正文身份另列。

五条紧凑 SDK 链已完成：正常全链 12.062 秒；来源主动关闭 10.469 秒；Host 本机注入 10.516 秒；SDK 抛错 10.657 秒；先断一代再由第二代派发并中断 10.391 秒。各链 715/716 输入前后及当前相同，所有逻辑 owner、子树、双 EOF、线程 join 和句柄完整收尾。正常 65 项事实/30 个 ABI 槽逐值逐位相同；异常链保持原生失败退出，外层判别器按明确原件验证预期触发。

SDK 抛错产生原生 `qmt_call_failed` 并保持运输，来源主动关闭和 Host 本机故障分别产生原 Host 中断终态。双代用例明确显示：首代无请求 OSError 早于受理，失败请求属于另一代；原 UUID/binding/generation 摘要与原关闭 SDK Journal、来源 SDK 事件严格一一对应。此用例验证诊断能够识别误关联，没有证明旧实际故障也由同一原因造成。

最终 `final` 增补显式 close 调用栈和 worker 确已进入标记，普通隔离 SDK 全链 11.453 秒通过，715 输入保持、65 项事实/30 ABI 精确一致；提取 24 条连续固定元数据事件。新真实配对生成、verify 和 check-only 已通过，真实 owner、Journal、来源和请求均未启动。顶层 `FINAL-READY-001.json` SHA `c67eb4668026ec8a79a905d75b5924fc620c3f6ecd142920515afd70af0208e1` 固定 61 项；根操作和判读见该根 `ROOT-OPERATIONS.md`。

上述前一冻结曾指定 `final/real/private/diagnostic-strategy.py`，当前操作已转入下文 final2；原 Probe 备份、临时启停、日志、停止恢复和精确正文 SHA 仍由根统一保存。先按请求和通信代际匹配，再判断具体责任层。没有同次双端证据时保留 unknown，SDK 诊断成功不转授产品修复、完整恢复、交易或生产资格。

## 最终 final2 接口与观测补齐

当前唯一操作入口为准备根的 `CURRENT-OPERATIONS.md` 和 `ROOT-OPERATIONS-002.md`。旧 `final`、`FINAL-READY-001.json` 与 `ROOT-OPERATIONS.md` 保留冻结历史；根取消旧 final1 时来源与查询均未启动，并已正常回收外部 owner、恢复原文。其取消后的连接拒绝归入操作收尾。

最终 `final2` 将 `<guanheng-memory-entry>` 回调帧映射到原正式完整前缀 SHA，保留原 `_check_context`、`_check` 与 close 调用位置；tick 异常仅增加同 Context/同原线程两个布尔。实际 Python 3.6.8 纯回调回归触发原 guard，记录四次关闭通知、0 SDK、0 运输 owner。该结果授观察能力，实际根因保持 unknown。

final2 完整普通 SDK 链 11.453 秒通过，718 项输入前后及当前一致，65 项事实/30 ABI 严格相同、24 条连续固定元数据事件，内外所有 owner 与物理资源正常关闭。提取器适用于冻结发射器和固定 QA schema，嵌套去敏依据同一发射器。`FINAL-READY-002.json` SHA `cc7933d345c9f2fc664e7f6571096961d98ad824ef75fb17f9b74cceca54c8be` 固定 67 项；本次正文为 `final2/real/private/diagnostic-strategy.py`，新真实材料仅生成、verify 与 check-only，尚未启动真实 owner、Journal、来源或请求。原产品与 WT 源码保持。

独立双轴审查最终原件为准备根 `review/REVIEW-002.json`，SHA `e54b408a4f208dc1976c2baa4b91b560b3a864127e7f29bb28aaec43b74e42b4`，开放 P0–P3 均为 0；原初报告保留，审查者误选旧操作文档所提 P2 已由 `CORRECTION-001.json` 明确撤回。模块交付为 `DELIVERY-001.json`，SHA `68f1939ad0733e0a095e692db88fc414e53c0949c78a043f94f05e5bcc0ff58c`。文档导航检查通过；实际现场根因、产品修复、恢复和生产资格继续待验。
