# 交易任务接续当前认证代际

类型：自有标准插件根因与合并后主链证据。日期：2026-11-04。状态：候选独立审查与合并DLL验证通过，已由线上WT加载；现场完整撤单及正常停止继续验收。

原真实停止失败的原因是Query/Event已进入新认证代际，新写及原命令审计仍复用初代金融客户端。Common正确拒绝旧完整binding，产生`qmt_trade_binding_changed`。修正将新Insert/Cancel/AuditOriginal接回原worker拥有的当前已认证代际；原Core仍钉住完整B，历史收据和取消proof继续按原身份核对。只允许认证连接的host_instance_id/transport_generation变化，业务session/profile/route及其他稳定字段保持。要求见[STQ-P31](../specs/native-qmt-standard-trader.md#stq-p31-认证换代后的新金融任务与原责任核查)。

固定目录：`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`。

- `trade-stop-binding-candidate001/REPORT.json`及EVIDENCE：原标准Factory/ITraderApi/SPI与签名HTTP主链，旧版认证换代后复现code7，新版仅一次取消原委托、零insert，回到recovery_ready并完整关闭。丢回复后只GET原取消UUID，未重POST；来源、profile、route及过期proof仍拒绝。
- `STOP-BINDING-REVIEW.json`：独立规范/规格delta均complete、findings=0。最终合并源码SHA `d763392c16f8c02b114dc58ba77376ac6507a505e232515afc7e478610fe7382`，保留已接受价格修正。
- `MERGED-TRADE-NATIVE.json`：以当前固定框架头与原链接清单仅重编自有Standard；保持最新mapper。DLL SHA `e9a049ed256cc5eea7ebe645a616d0ef266b1ea734c1f6f2f8f917d50169519c`，无新增框架差异。
- `trade-stop-binding-candidate001/STANDARD-merged-auth.json`、`STANDARD-merged-audit.json`：Root对最终DLL重跑原标准入口，正常认证换代取消一次、Pending清零并关闭；取消回复丢失后只GET原UUID，原unknown门禁继续保留。全部SDK替身，实际金融操作0次。

当前WT已加载该DLL，实际账户/策略和独立观衡读取恢复。该运行范围仍需自然行情下继续完整调仓、实际撤单和正常关闭验证；本记录没有扩大为上述未完成结果。
