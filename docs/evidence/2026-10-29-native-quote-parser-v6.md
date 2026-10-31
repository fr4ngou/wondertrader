# v6 原生实时行情插件验收

类型：验证记录。状态：限定开发模块已验收，真实来源由根集成继续。范围：[NPV6](../specs/qmt-native-parser-v6.md) 显式插件、协议准入及安装链。

根因为旧 Legacy 门面固定只接受 full_tick 三字段能力，当前来源显式公开 v6 五字段及历史准备组合。新增显式工厂和 FullTickV6 选择，在原 BoundCore 信任边界完整核验组合 descriptor，继续只发 full_tick。旧默认及账户 v3/v4 保持。

源码基线、候选与运行原件位于 `build/native-quote-parser-v6-001`。`SOURCE.json/INPUTS.json` 固定源码快照与原静态库输入；`BUILD.json` 固定新 DLL 和两探针。DLL SHA256：`bc082ee942970498829a4c725fac412826ead8838d1eb263bb33a0969920adc8`。隐藏受控构建 attempt003/004 exit0，Job树归零、EOF、读线程join及句柄关闭均确认。

正式 HPR e 安装 Host → 认证 WinSHM → 实际 CPython3.6.8 完整生成内存正文与 SDK 替身 → 新安装 DLL → 原 SPI 主链通过（`main003/RESULT.json`）；ZIP 摘要及全部解包文件回核后，搬迁安装重复整链通过（`relocated001/RESULT.json`）。两次 full_tick 共三次证券回调，价格/累计量/累计额分别为 SZSE.000001 4/10000份/400元、SSE.510300 5/10100份/505元、SSE.600000 6/10200份/612元，上海时间2021-11-01 09:31:00。stop/delete、来源原线程及内存正文 forbidden_attempts=0、Host监视线程/管道/Job/句柄关闭全部确认。

`build-contract002/result.json`：原绑定/签名/UUID、原结果字节、lost POST只GET、Unknown原ID保留/恢复、旧会话拒绝、预算/线程/容量及22组完整v6 descriptor坏例通过；最小两操作组合采用 full_tick 自身执行时限。11测试中1个专用异常注入可执行文件未供而skip，常规Unknown/网络中断链已覆盖。`build-legacy001/result.json` 同一新Common DLL旧Legacy完整矩阵通过（9测试1相同skip）；`build-account001/result.json` 原v3/v4绑定及公开交易profile codec向量exit0。无真实账户/交易请求。

`ParserQMTHostV6-001.zip` 是可搬迁安装包，制品目录含DLL、SPI与合成bound探针、许可和MANIFEST；`DEPENDENCIES.json`列出实际PE依赖（系统WinHTTP/bcrypt、MSVC140及UCRT）。`CONFIG-EXAMPLE.json/V6-PROFILE-EXAMPLE.json` 是显式合成配置/来源能力示例，真实单位与来源许可另核。`CHECK.json`记录文档检查通过。首次两轮合成夹具的证券批量参数/报价高低关系校正前失败原件保留，最终成功由003和搬迁001记录授资格。

真实 QMT、正式 CTA 宿主、全市场规模及生产发布资格由根集成另验。本轮新增 WT 框架差异0，历史准备/下载/账户/交易操作0；全部测试进程已终态。

最终统一候选：新增兼容探针触发同源码重新链接，五源码及完整快照保持；最终 DLL SHA256 为 `2d422159b21647fa18feed0e3020c735033502e8bbf40bd346b9c53c7bf6c059`，以 `BUILD-FINAL.json`、`INSTALL-FINAL.json`、`final-install/` 和 `ParserQMTHostV6-002.zip` 为交付身份，前述 bc082ee9 候选保留历史。ZIP加入脱敏配置、来源profile示例及实际PE依赖。

独立 full 审查 `REVIEW.json` 锁定相同五源码并核对构建快照一致，功能/安全/资源问题0；standards与规格源码符合性complete。Reviewer独立契约10通过/1相同fault-probe缺失skip，另核版本隔离、可选account descriptor、仅full_tick请求及Legacy/v3v4向量。其规格整体unknown专指安装/搬迁/文档门禁没有由Reviewer独立运行或读取；作者的实际安装原件分别闭合相应验收，不将源码审查写成运行证据。最终制品搬迁主链与全部摘要由 `HANDOFF.md`、`DELIVERY.json` 汇总。
