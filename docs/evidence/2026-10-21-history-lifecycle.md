# 2026-10-21 长历史生命周期与独立消费者

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：pass（隔离开发验收），真实来源和业务切换 pending-verification。关联 [HSA-R1–R8](../specs/history-lifecycle-and-service-adapters.md)。整体移植 goal 保持 active；本记录限定隔离开发资格。

## 输入与事实边界

工作区 `E:/workspace/wondertrader`，分支 `codex/qmt-migration-plan`，HEAD `08b230dd05facf6d650d949bfe51054115a2ecb1`，含未提交开发差异。沿 QMT HTTP 主链开发；共享内存绑定和 TDX 交易保持暂缓。原 QMT 工作区只读，续接时他人已将主干推进到 `3a2f97cbeb0127747f5f8d3cef5f8a3c467420ff`；本轮 Operations DTO/repository 输入摘要仍匹配原 oracle。

DSB 是数据 owner，原 Operations 是持久作业和确认 owner，原生 queue 只保存有界短期任务。客户端与 runner 统一位于独立 SDK，旧路径只兼容转发；观衡服务可独立安装 wheel，不需要 WT DLL 或 QMT checkout。

最终源码指纹 `f9526b3de3c7a31735393c05f8cb3d8a379f540fd884d8a5460579935561ea1d`；实际工具链、依赖和逐文件摘要见构建收据（外部历史/待归仓路径：`hsa-2026-10-21/receipt.json`）和制品清单（外部历史/待归仓路径：`hsa-2026-10-21/package-manifest.json`）。SDK 使用 Flit 3.12.0 固定 backend，标准库运行依赖；工具链资格限 Windows x64 SDK-independent profile。

## 当前已验行为

- 原生生命周期七项回归：两证券 130 窗口回收与回读、定向工作、并发释放背压、重复释放、终态修订/损坏重检及重建恢复。
- 服务 28 项：原协议兼容、新任务身份、200 种 code/state 组合、服务重启旧身份拒绝、已有 DSB 离线恢复；缺少日历依据的三种请求保持 Pending，源 HTTP 请求为零。
- runner 25 项 owner/独立复验：原 Operations DTO/归约器、70 段顺序处理、CAS/stop/resume、确认回复丢失、源工作回复丢失、显式 Releasing、释放前后断线、背压/未知/重启、完整回读只确认一次。独立增加七个释放恢复组合，均通过。
- 构建收敛显式 SDK 源清单、固定 Flit 版本/摘要与实际 wheel 成员/字节；未声明材料、构建中新加源码及输出篡改负向验证通过。最终 wheel 与 receipt/两份源码/许可证一致，已离仓安装并以独立进程消费真实隔离 HTTP。

## 最终命令与制品

| 命令/验证 | 实际结果 |
|---|---|
| `python -B scripts/native.py all --offline --jobs 4 --qmt-source D:/workspace/qmt` | exit 0，15 阶段全部 passed |
| CTest | 49 启用通过，0 失败；另 1 个既有全天时段用例 Disabled；87.79 秒 |
| 构建流水线 unittest | 28 项通过，含 4 项 SDK 负向验证，0 skip |
| CTest 内部场景 | service 28、runner 25、queue lifecycle 7；这些场景不与注册测试数相加 |
| 搬迁包 HTTP 链 | 合成源真实 HTTP→原生 DSB→独立行情服务→离仓安装 wheel，3 个闭合分钟，股/元与预期一致；认证与私有 IO 原因泄露负向通过 |
| 搬迁包原生/业务回放 | 工厂、Runtime、分钟链、历史、原业务与 Console 契约、指定原纯核心 WT 回放均通过；原 Portfolio shadow 零委托 |
| Ruff / `scripts/project.py check` / `git diff --check` | 通过；Git 仅提示原有行尾转换 |

开发包：`build/native/packages/dev-20261021T030409Z-a6127597.zip`，4,996,672 字节，SHA-256 `78504f100de80225286560103682cf8d722c2a4a0632289be6ba6ca597207b06`。

独立 SDK：包内 `clients/guanheng_market_client-0.2.0-py3-none-any.whl`，SHA-256 `249b1a51f1801dc5eab611933daa00045c9a2b79840322eebd4e7a6ae57a7672`；SDK 收据（外部历史/待归仓路径：`hsa-2026-10-21/client-sdk-receipt.json`）固定唯一实现与锁定 backend 身份。最终 all 重新生成并验过本轮制品，中间包不作为最终修复证据。

首次审查 full，修复按 delta：生命周期/协议/发行报告覆盖 HSA-R1–R4/R7/R8；runner 报告覆盖适用 R1/R3/R5–R8，原生/发行实现另由前者证明。已发现问题均修复并复验，无遗留 P1/P2。前者（外部历史/待归仓路径：`hsa-2026-10-21/hsa-lifecycle-sdk-review.md`）最后 35 个输入和后者（外部历史/待归仓路径：`hsa-2026-10-21/hsa-runner-independent-review.md`）最后 14 个输入逐字节匹配最终文件；原报告保留轮次边界。SDK/ABI/队列/构建不变部分按输入复用，runner 变化重新审查与生成 wheel。

原始日志、最终测试 XML、清单、审查与输入核对汇总在 summary.json（外部历史/待归仓路径：`hsa-2026-10-21/summary.json`），文件摘要见 SHA256SUMS.json（外部历史/待归仓路径：`hsa-2026-10-21/SHA256SUMS.json`）。上一阶段 [HTTP 冻结证据](2026-10-21-qmt-http-market.md)保留当时制品和资格。

## 限制与后继

本机 HTTP 18010 当前无监听。真实 QMT profile/单位/源时间、权威日历与 EvidenceSink 的正式接线、原旧日线 CLI 的新 family 路由保护、实际 Operations 可达性及业务服务切换继续待验。新 Host 元数据内部接口尚未成为公开 HTTP/bootstrap 能力。原 MarketData 的来源/量额/因子契约须由原 owner 升级后才可进入真实分析窗口。

本轮没有真实委托、撤单、账户操作、数据库写入、生产切换或 Git 推送。隔离正向与故障测试不能代表真实十年或全市场数据已导入，也不能代表页面已上线。
