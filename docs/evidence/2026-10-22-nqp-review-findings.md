# NQP 独立审查发现：依赖内容核验与微软运行库材料

类型：后继修正与来源审计记录。范围：NQP-018 full 的 F1/F2。状态：F1源码修正与定向根因回归通过，独立delta待执行；F2分发材料条件保持gap。018冻结源码、收据、ZIP及审查报告保持原样。本轮未启动019编译、完整CTest或新开发包。

## F1 根因与实现

真实临时tar归档、锁定源码映射及默认固定profile的原 `native.py deps` CLI复现两种接受坏缓存的情况：同大小改写并恢复纳秒mtime；修改文件后伪造marker中的verified_metadata。两例均保持锁中期望内容摘要不变，旧入口返回passed。

根因位于固定profile调用唯一依赖owner时沿用可选audit参数，导致可改metadata跳过内容SHA。修正集中在原入口的同一调用：固定profile的deps/configure/build/test/package/all强制audit=True；原下载、解压、锁映射和文件集合校验继续由dependencies拥有。中文注释明确metadata不授固定内容身份。普通native的默认/显式profile及audit选项沿原语义，未新增依赖owner或缓存格式。

测试使用本仓库 `.venv/Scripts/python.exe`。新回归包含两项真实坏缓存拒绝、普通native隐式/显式/audit参数调用和显式audit拒绝。与原marker篡改、离线缺依赖、缺明确QMT外源、独立verify无工具发现组合，8项全部通过，0.346s。

证据根：`build/native/nqp-review-repair-001`。`paired-red.log`用018冻结native.py与当前相同两项负向测试重现2失败；`paired-red-input.json`绑定原owner和测试摘要；`targeted-green.log`保存8通过。`source-delta.patch`与`source/`绑定修正源码。旧018成功运行的实际依赖内容已由独立full逐项核验正确，本发现不改写其原事实。

F1后继独立delta已完成，报告为`build/native/nqp-review-repair-001/reviews/delta-001.md`：独立短重验4项通过，确认同size/mtime及伪造metadata两窗口均拒绝、普通native兼容，F1在源码层关闭。018的OWN72、handoff、ZIP及审查包身份保持原样；没有执行019 fresh编译、完整CTest/all或新包验收，因此本次关闭不授后继包资格，F2继续保持gap。

## F2 逐文件来源和材料

逐一核对018的54个运行库，包内字节均匹配当前本机原分发目录：

| 组 | 数量 | 原来源与实际版本 |
|---|---:|---|
| MSVC CRT | 8 | VS Build Tools 2026 Release 18.8.12009.203；VC/Redist/MSVC/14.51.36231/x64/Microsoft.VC145.CRT；DLL产品版本14.51.36247.0 |
| UCRT/API-set | 46 | Windows Kits/10/Redist/10.0.26100.0/ucrt/DLLs/x64；DLL产品版本10.0.26100.8249 |

本机产品状态为Release通道、RTW、非pre-release，编译器路径版本14.51.36231。逐文件source、SHA、文件/产品版本、与018包字节相等性及官方SDK逐名表匹配项记录在 `microsoft-runtime-audit.json`、`microsoft-runtime-inventory-with-versions.json`。

材料原件及SHA保存在同一证据根的 `microsoft-materials/`，含本机SDK原sdk_license.rtf与sdk_third_party_notices.rtf、微软官方2026 Build Tools和VC14 Runtime原DOCX、VS/SDK Redist网页及UCRT部署说明。sources.json记录原URL、最终URL或本机来源及文件摘要；DOCX文本提取仅供审阅，原DOCX字节单独保留。

适用依据分别是[VS2026分发列表](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution)、[Build Tools原条款](https://visualstudio.microsoft.com/license-terms/vs2026-ga-diagnostic-buildtools/)、[VC14 Runtime原条款](https://visualstudio.microsoft.com/license-terms/vs2026-ga-visualcpp-v14-redist-runtime/)、[SDK Redist列表](https://learn.microsoft.com/en-us/legal/windows-sdk/redist)和[UCRT部署说明](https://learn.microsoft.com/en-us/cpp/windows/universal-crt-deployment?view=msvc-170)。SDK本机条款中的LinkId=524842实际跳转到该SDK Redist列表。

## F2 尚未证实与后继选择

微软VS分发列表对VC/redist下未修改文件规定附带程序分发的条件，并要求适用的有效软件许可；当前仅确认安装身份，尚未确认受控VS产品许可条件。安装事实不替代该证明，也不据此判断使用者缺少许可。

当前SDK Redist逐名表覆盖41个实际UCRT文件，下列5个名字未列出：api-ms-win-core-console-l1-2-0.dll、api-ms-win-core-fibers-l1-1-0.dll、api-ms-win-core-fibers-l1-1-1.dll、api-ms-win-core-kernel32-legacy-l1-1-1.dll、api-ms-win-core-sysinfo-l1-2-0.dll。技术部署页说明SDK的本地UCRT部署方式，尚不足以替代这5项的具体分发材料核定。

F2保持gap，当前未授正式外发资格。内部开发运行结果记录技术行为；开发工具与对外分发的许可条件按原条款和受控证明核定。本轮没有把材料补入旧ZIP，没有删除DLL、修改ABI或改变原自包含要求。

新候选正式打包前比较两项可审方案：保留原运行库集合并补齐逐项材料及适用分发条件；明确支持的Windows及官方运行库安装前提，采用经验证的运行依赖方式。两项都须保证所需运行库实际可用、保持ABI并形成对应新包验证。当前未选择或实施任一替代打包方式。

## 后继输入

当前源码改动为scripts/native.py和新tests/build_pipeline/test_native_dependency_integrity.py，构建手册及工具链模块说明同步修正固定profile的audit语义。事实及摘要由本证据根的repair-manifest.json登记；该清单不修改018的旧manifest。后续由构建owner协调新候选与独立delta。真实QMT、生产、完整观衡迁入及旧QMT工程门禁不在本轮操作范围。
