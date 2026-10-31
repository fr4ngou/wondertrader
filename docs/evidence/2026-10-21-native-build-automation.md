# 2026-10-21 原生构建、开发包与自动测试

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：pass（限定 NBA 开发工具链范围；已知全天用例和环境资格单列）。关联：[NBA-R1–R6](../specs/native-build-automation.md)。

## 输入身份

- 工作区：`E:\workspace\wondertrader`；分支 `codex/qmt-migration-plan`。
- HEAD/上游基线：`08b230dd05facf6d650d949bfe51054115a2ecb1`；候选有未提交修改。实际输入文件 SHA-256 与聚合摘要保存在对应 receipt/manifest，Git HEAD 单独不足以识别候选。
- Windows 11 x64，MSVC Build Tools 18 / cl 19.51.36248，Windows SDK 10.0.26100.0，CMake 4.3.1-msvc1，Ninja 1.13.2；文档与编排工具使用本机既有 Python 3.14.6。CI 定义使用 windows-2022 / Python 3.12，托管执行尚未发生。
- 固定依赖：Boost 1.85.0、spdlog 1.9.2、RapidJSON 1.1.0；来源、归档及裁剪后文件映射摘要以 [lock](../../config/native-dependencies.json) 为准。
- 生成文件、缓存、临时目录、日志与包位于 `E:\workspace\wondertrader\build\native`；未安装或修改全局工具。

## 已观察的完整链

原生编译实际产出 WtRunner/WtBtRunner、WtBtPorter、数据/风险/执行及模拟插件。独立构建入口直接组合原生源码，保持上游总入口。

实际回放使用虚构 `CFFEX.IF.2401` 的固定 CSV：历史预热 2 根、策略计算/分钟回调各 9 次，932 分以 102 开 1 手、935 分以 105 平 1 手，最终持仓 0，结束事件与 trades.csv 自动断言。开发 ZIP 解压到另一目录后，包内 Runner 与 WtBtPorter 回放已实际成功；该结果只证明回测链，不授予业务/券商 E2E 资格。

首次原生测试发现公共头文件全局 `using namespace std` 与 Windows RPC `byte` 冲突，已将导入范围收敛，并显式补全受影响 VWap 源文件的 std 名称；[CORE-001](../maintenance/upstream-overrides.md) 跟踪退出条件。新增编译回归保持 `std::byte` 可用并同时包含 Windows RPC 头。

中文 MSVC 配合 `/utf-8` 需要正确的 Ninja include 前缀。实际探测、嵌套 project 恢复与公开头依赖检查共同验证增量编译；SDK 目录按 Ninja 系统头过滤规则管理，SDK 版本归工具链身份。

## 已知上游失败及资格

原始 `test_session.test_allday` 在时段逻辑未修改时实跑失败：`minuteToTime(1440)` 返回 2400（预期 0）、`isLastOfSection(0)` 返回 false（预期 true）、`offsetTime(0,false)` 返回 0（预期 2400）。当前框架区分原始边界、零偏移与偏移对齐语义，完整全天约定需独立核定。

本任务保持时段实现，CTest 显式登记 `known_failure.session_allday` 为 Disabled，不计入通过数。新增并启用日间分段时段回归，覆盖 240 分钟、午休两侧、午休排除与 15:00 收盘。重新启用条件：明确 0/2400 契约、按受影响调用链修正根因并通过跨日回归。全天/跨日资格保留缺口。

## 验证命令与报告

主入口：`python -B scripts/native.py all --offline --jobs 4`；干净重编译添加 `--clean-first`；全量依赖字节复核添加 `--audit-deps`。

最终命令 `python -B scripts/native.py all --offline --jobs 4` 退出 0，源码输入摘要与独立审查完全一致：`91659f64584ae219dc4f9625147d05ff465203bc207a07410059afae729e21de`。

| 检查 | 实际结果 | 冻结证据 |
|---|---|---|
| configure/build | 成功；本轮已实际干净重编译，最终以同一原生源/依赖复用产物 | 收据（外部历史/待归仓路径：`native-build-2026-10-21/receipt.json`） |
| CTest | 12 项启用通过，1 项 Disabled；0.96 秒 | JUnit（外部历史/待归仓路径：`native-build-2026-10-21/ctest.xml`） |
| 流水线测试 | 22 项通过，14.009 秒；含实际 CMake 新增/删除源文件编译、超时后代清理、缓存/身份/输出/包失败路径 | 报告（外部历史/待归仓路径：`native-build-2026-10-21/pipeline-tests.log`） |
| 搬迁后 Runner | 包内 EXE --help 成功 | 冒烟（外部历史/待归仓路径：`native-build-2026-10-21/package-smoke.log`） |
| 搬迁后回放 | 历史 2 根、9 次计算及 9 次分钟回调、2 笔模拟开平、最终持仓 0 | 回放（外部历史/待归仓路径：`native-build-2026-10-21/package-backtest.log`） |
| 接收端独立 verify | 正确外部摘要退出 0；错误摘要退出 1 | 通过（外部历史/待归仓路径：`native-build-2026-10-21/receiver-verify.json`）、拒绝（外部历史/待归仓路径：`native-build-2026-10-21/receiver-reject.json`） |
| 原始全天用例 | 显式单独复现，退出 1；未计入通过数 | 失败 XML（外部历史/待归仓路径：`native-build-2026-10-21/known-failure-session.xml`）、日志（外部历史/待归仓路径：`native-build-2026-10-21/known-failure-session.log`） |
| 文档/差异 | project.py check 通过；diff --check 按上游 CRLF 格式检查通过 | 本记录及实际命令 |

本轮另已运行 `all --offline --audit-deps --jobs 4` 并退出 0，全量复核三项依赖源码；最终仅调整编译器缓存路径/类型和资格绑定，依赖 lock、归档与源码缓存未变，最终重跑复用已验证元数据。干净重编译使用 `--clean-first`，实际编译 253 个构建步骤；后续编排修正按不变的原生源码复用有效产物。

开发包：`E:\workspace\wondertrader\build\native\packages\dev-20261020T163209Z-1fee55a9.zip`，3,710,811 字节（约 3.54 MiB）。外部 SHA-256：`3b1b76a46a0888ba154fcaee51244ac098f85c70fa656cbbe96c9f88814ba234`。包标记 development，带完整输入映射、工具链、依赖、文件大小及摘要；尚未提交的源状态明确记录，正式发行资格另验。

原始生成报告位于 `build/native/receipt.json`、`ctest.xml`、`logs/`、`packages/`。单独阶段会替换当前 receipt，本记录引用上表冻结副本。

## 审查范围与限制

full：新增构建、打包、生命周期及身份校验工具首次审查。独立审查只使用最终规格、规范和源码；随后按同一规格修复并进行 delta 复审，要求审查者确认全部适用要求影响。最终源码审查无剩余阻断，见独立审查记录（外部历史/待归仓路径：`native-build-2026-10-21/review.md`）。

本任务没有连接账户、真实交易、生产部署、上游升级演练、进程监督/切换或完整观衡业务 E2E。托管 CI 已写工作流定义，远端执行结果尚未提供；Linux、其他工具链及其他实际终端资格分别验证。包搬迁验证在同一构建主机的独立目录完成，尚无全新 Windows 主机验收。
