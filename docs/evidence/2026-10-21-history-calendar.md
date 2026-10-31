# 2026-10-21 权威分钟计划与 SDK 0.5.0

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：pass（隔离开发验收）；真实数据与生产部署 pending-verification。[CAL-R1–R6](../specs/history-calendar-projection.md)本阶段验收完成，完整观衡迁移目标保持 active，剩余要求见[验收地图](../migration/acceptance-map.md)。

## 输入与制品

WT 为 `E:/workspace/wondertrader`、`codex/qmt-migration-plan`、HEAD `08b230dd05facf6d650d949bfe51054115a2ecb1`，保留既有未提交工作。最终源码输入指纹 `2ea46664a299d6b3a1f0417b7ad3a2a8ca4594f164862349c25b3add917a00d9`。生产者位于独立 `E:/workspace/qmt-worktrees/wondertrader-service-adapters`、`codex/wt-services`，源码提交 `e4f3637f2747343bc29fc65493f14a38907a8310`；受控生产源码闭包指纹 `9c7583714cd426256b7d3ff5ea3dafec1e447c7519ebba1c7e12252f7e306e89`。

最终开发包 `build/native/packages/dev-20261021T051351Z-ce9a30fa.zip`，5,027,545 字节，SHA-256 `271fb1917d6c678d3f76e9d7d43bf82f243e235aede4b96ec9eb8337d41ece30`。包内独立 SDK 0.5.0 wheel SHA-256 `fdad372302234cfead2051a8e6af7b1a3dd7d53ff0fb67dfed9a6289632f270e`。显式五源码全部与 wheel/安装目录逐字节一致；基础运行依赖为空，storage extra 保留 MinIO 7.2.20、urllib3 2.7.0。

原 QMT 主树保持只读且干净，最终观察 HEAD `0f9f3f2e6fd89c6d59d154785d9f0e36503386b5`。它相较本阶段起点 d6917230 仅增加另一项原生元数据任务登记与证据；本次使用的运行源保持。新日历接口只在隔离分支实现，原主树未合入或部署。

## 行为与职责

原 MarketData 新增鉴权 `POST /v1/market/calendar/minutes/query`，从既有 FactStore 精确读取版本及最多三天事实，复用唯一共享交易所会话转换。原 Portfolio 函数保持兼容转发，共享实现与旧实现 AST 一致。Postgres 使用一个参数化有序 SELECT、LIMIT 7；内存源沿原串行门复制。请求必须有完整两市场及截至 as_of 的来源，成功输出最多 720 个点、512 KiB。

标准库消费者验证公开契约、请求身份、来源与派生版本、时间/排序及规范摘要；完整响应经既有 EvidenceSink 写入并回读后返回 CalendarSlice。响应内容摘要排除自身，存储摘要包含完整响应，两种身份分别核验。没有新增日历事实库或作业账本，Operations 继续持有原作业/CAS/确认。

独立 wheel 进程串联真实原生产路由、原 Operations 纯归约器、实际 NativeMarket/市场 HTTP、签名合成 QMT Gateway、真实 DSB 写入回读及确认。数据均为合成事实；原生链覆盖完整 240 分钟、午休、右端时间和量额换算。日历缺失/版本漂移/证据丢回复在 prepare 前停止；恢复继续同一作业。闭市区间可以确认零 bar，开市尚无闭合分钟保留 Pending。活跃已确认段重新读取同一日历与证据，证据损坏阻断后续段，既有确认字节保持。

## 最终执行

| 验证 | 实际结果 |
|---|---|
| `native.py all --offline --jobs 4 --qmt-source D:/workspace/qmt --calendar-owner-source E:/workspace/qmt-worktrees/wondertrader-service-adapters` | exit 0，18 阶段全部 passed |
| CTest | 53 启用全部通过，185.29 秒；另 1 既有全天时段用例 Disabled |
| 构建流水线 | 32 项通过，15.610 秒；包含源选择错配、生产闭包变化、发行输入与负向制品检查 |
| 客户端与跨仓链 | 20 项客户端回归；9 个跨仓方法/10 场景，无 skip；原生 240 点及 PUT/GET 丢回复同作业恢复 |
| 搬迁包 | 解压后实际 DLL/市场模块、包内 wheel 独立安装；9 方法/10 场景通过，41.866 秒；独立 worker 13 项继续通过 |
| 原观衡送审与门禁 | 134 项精确影响测试通过；准备 9/9、最终门禁 9/9；正式审查 R1–R6 complete，阶段 ready_for_integration |
| 原端覆盖诊断 | 当前修改代码 175/178，98.31%，无缺测文件；该比例不代表全系统或生产覆盖 |
| 静态与身份 | Ruff、适用原端静态检查及文档导航通过；61 项制品清单逐文件校验 |

原端共享会话提取触发安装制品源码身份变化，标准构建器追加六个 `calendar-projection-dev-20261021-v1` 候选记录并显式纳入新共享依赖，旧 488 条不可变记录保留。候选登记没有激活生产策略或自动交易。独立数据库用例所需专用配置缺失，原阶段 9 项 PostgreSQL 用例保持未执行；当前正式门禁按声明精确模块运行。

## 独立审查与证据

生产者正式 full 报告（外部历史/待归仓路径：`cal-2026-10-21/calendar-owner-independent-review.json`）绑定原项目最终规格包，零 findings；独立执行 55 原端、20 SDK、9 跨仓测试。消费者 full/delta 报告（外部历史/待归仓路径：`cal-2026-10-21/calendar-consumer-independent-review.md`）关闭三项 P2：巨大整数预算验证、不可编码源版本及测试子进程诊断丢失/Windows 连接收尾。修复覆盖原触发条件，34 项最终机读输入（外部历史/待归仓路径：`cal-2026-10-21/calendar-consumer-final-inputs.json`）逐文件匹配。审查中的一次临时微型 Ninja 构建偏差和早期非冻结诊断保留在报告中，后续仅按明确入口复验。

最终静态检查补齐两处测试延后导入标注后，完整流程重新绑定最终源码与制品；注释差异已独立逐字节核验。此前通过运行保存在开发工作记录中，其制品保持原身份，本记录只引用最终包。原端复用准备时的精确隔离环境字符串后导入审查成功，代码、报告及九项既有回执本身保持有效。

冻结汇总（外部历史/待归仓路径：`cal-2026-10-21/summary.json`）、完整收据（外部历史/待归仓路径：`cal-2026-10-21/receipt.json`）、原端工作流（外部历史/待归仓路径：`cal-2026-10-21/owner-workflow.json`）、正式规格包原文（外部历史/待归仓路径：`cal-2026-10-21/owner-review-pack.txt`）、SDK 收据（外部历史/待归仓路径：`cal-2026-10-21/client-sdk-receipt.json`）和制品清单（外部历史/待归仓路径：`cal-2026-10-21/package-manifest.json`）保留实际身份；外部规格包按原字节保存为文本附件，其相对链接继续属于原仓库。摘要清单（外部历史/待归仓路径：`cal-2026-10-21/SHA256SUMS.json`）保护全部原始文件。HSA/HES/HW 三阶段的原始证据分别 22/22/24 项摘要保持一致。

## 剩余运行边界

交易所计划 scope=exchange_plan、security_exclusions=not_applied，证券历史停牌及上市/退市排除未接入；缺 bar 保持缺口。实际日历入库/十年覆盖、真实 QMT HTTP profile、PostgreSQL、MinIO namespace/ACL/保留与结果 resolver、原日线 family 保护、生产工厂/监督及真实业务页面继续按完整地图推进。当前隔离测试不授真实源或生产资格。

观衡服务独立受管发布；原 QMT 主树与生产服务保持。共享内存与 WT 绑定、TDX 交易继续暂缓。未执行真实下单、撤单、账户变更、生产发布或 Git 推送。
