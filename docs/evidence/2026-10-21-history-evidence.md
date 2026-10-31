# 2026-10-21 历史证据存储与 SDK 0.3.0

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：pass（隔离开发验收），真实 MinIO/行情/业务切换 pending-verification。对应 [HES-R1–R5](../specs/history-evidence-storage.md)，整体目标保持 active；完整范围见[验收地图](../migration/acceptance-map.md)。

## 输入身份

WT 工作区 `E:/workspace/wondertrader`，分支 `codex/qmt-migration-plan`，HEAD `08b230dd05facf6d650d949bfe51054115a2ecb1`，含未提交开发差异。最终输入指纹 `207edb84fb85c1101d5a11befc204aafda9de7367d670c4df8c56eff2a9144c1`。收据（外部历史/待归仓路径：`hes-2026-10-21/receipt.json`）及包清单（外部历史/待归仓路径：`hes-2026-10-21/package-manifest.json`）记录逐文件摘要、Windows x64 工具链和依赖。

实际 SDK 为 minio 7.2.20、urllib3 2.7.0；安装源来自既有受管 Python 环境，本轮未安装或修改全局依赖。汇总（外部历史/待归仓路径：`hes-2026-10-21/summary.json`）另记 SDK 源码摘要；MinIO api.py SHA-256 `6b0374bf02609d547a5090934ff4b3dbc24171228c97f8621ff40fcc2ed6d3a2`。基础 wheel 仍为标准库，storage extra 单独声明两项固定依赖。

原 QMT 主树只读核查，最终 HEAD `3a2f97cbeb0127747f5f8d3cef5f8a3c467420ff` 且 Git 干净。测试只导入原 Operations 纯 DTO/内存归约器；未启动原服务、连接生产数据库或读取生产对象凭证。

## 行为与根因修复

MinioEvidenceSink 接原对象 owner，固定 bucket/prefix 与内容地址，不新增作业数据库。规范 JSON 和完整摘要验证、已有对象比对、缺失后单次 PUT、写后回读；resolve 只接受本命名空间引用。未知写回复保留核查，后续同摘要先 GET，不自动重发。流成功/异常/关闭异常都尝试 close 与 release_conn。

独立审查发现 SDK 的 RetryHead 内部路径绕过 urllib3 的关闭重试设置，会重发已执行 PUT。受管 factory 改在精确 SDK 版本下使用最小单次交换子类，复用官方 _get_region/_url_open、签名和错误解析；直接/继承原重试实现的 Minio 被拒绝。另一缺口是读取后规范校验耗时超预算仍返回成功，现校验后再次核截止。两项 P2 均由原故障条件独立复验关闭。

## 最终执行

| 命令/链路 | 实际结果 |
|---|---|
| `python -B scripts/native.py all --offline --jobs 4 --qmt-source D:/workspace/qmt` | exit 0，15 阶段全部 passed |
| CTest | 50 启用全部通过；另 1 个既有全天时段用例 Disabled；103.78 秒 |
| 构建流水线 | 30 项通过，含 SDK 6 项真实构建/缓存/源码范围/依赖 metadata 负向测试 |
| storage 集成 | 22 项通过、无 skip；真实锁定 SDK→本机隔离 S3 HTTP→原 Operations DTO/归约器与 runner |
| 已有消费链 | service 28、runner 25 场景及原生队列/分钟/执行/回放继续通过；场景数不与 CTest 注册数相加 |
| 独立 wheel | 离仓安装后 `-I -S` 导入三模块，不加载 minio/urllib3；缺 extra 工厂明确不可用；独立重建摘要一致 |
| 搬迁包 | 原生 Runner/回测、插件、Runtime/分钟/DSB、原业务影子回放、包内 wheel 安装与实际隔离 HTTP 消费通过 |
| Ruff / `project.py check` / `git diff --check` | 通过；Git 仅提示既有行尾转换 |

存储回归包括 6 MiB 规范对象仅 1 PUT/0 POST、相同内容重复/并发、三种明确缺失码、非缺失错误零写、损坏/超大/截断、响应资源释放、写后回复丢失和读回回复丢失、严格 URI、版本与类能力契约拒绝。真实 RetryHead 故障下首 PUT 结果未知且计数保持 1，下次同摘要 GET 恢复；GET RetryHead 也不重试、不触发写入。校验超时故障在 get/resolve 均正确返回截止诊断。

组合链在证据写入未知后恢复，再丢 Operations checkpoint 回复，最终原归约器只确认一段、源 work 一次、临时任务回收；实际 resolve 最终 result_ref，再逐个读取 segment_sha256 验证。此证明使用隔离 S3 与 Operations HTTP，生产网络及对象 ACL 另验。

## 制品和审查

开发包 `build/native/packages/dev-20261021T033719Z-6d384ee0.zip`，5,005,799 字节，SHA-256 `28dd4d7e5e0916db54820291b63cb6431cec96d18097998fdcf4b72d79a3608a`。

包内独立 SDK `clients/guanheng_market_client-0.3.0-py3-none-any.whl`，SHA-256 `80993a20c95a1c1848a32d56fa0d03ebb52ae5470cceddfebd848352ce3cd209`；SDK 收据（外部历史/待归仓路径：`hes-2026-10-21/client-sdk-receipt.json`）绑定三源码、许可证与固定 backend。本轮没有上传包或推送仓库。

首次 full、修复 delta：行为审查（外部历史/待归仓路径：`hes-2026-10-21/hes-independent-review.md`）覆盖 R1/R2/R4 及 factory/截止相关 R3；SDK 审查（外部历史/待归仓路径：`hes-2026-10-21/hes-sdk-independent-review.md`）覆盖依赖/extra、发行隔离及规范。各自最后 18/31 个输入与当前文件逐字节匹配，无遗留 P1/P2；范围外生产资格保留 unknown。原 HSA 不变行为按源码身份复用，本轮 all 仍重验受影响链。

原始收据、日志、CTest XML、审查和身份核对位于 summary.json（外部历史/待归仓路径：`hes-2026-10-21/summary.json`），文件摘要在 SHA256SUMS.json（外部历史/待归仓路径：`hes-2026-10-21/SHA256SUMS.json`）。[上一阶段证据](2026-10-21-history-lifecycle.md)及其原始 22 个文件保持原摘要。

## 运行缺项

真实 MinIO 的专用命名空间、最小权限、保留/WORM、读者 resolver 与部署监督尚未绑定。本模块明确不保证任意第三方写者下的原子 create-if-absent；强制抢占阻塞依赖由外部监督负责，超时后的诊断与业务确认分别处理。

[日历调查](../migration/calendar-owner-boundary.md)已找到可复用日级资产及原会话校验，公开分钟/历史停牌覆盖契约仍缺；旧日线 CLI 对新 family 的路由保护、实际 QMT HTTP profile、原 MarketData 单位/来源/因子升级和服务页面切换继续待验。共享内存绑定、TDX 交易按用户决定暂缓。本轮没有真实订单、撤单、账户操作或生产发布。
