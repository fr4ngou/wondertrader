# 2026-10-29 完整 App 与 MRC 真实缓存读链

类型：验证记录。结果：pass（已存在缓存正常读链）。关联：[FHR 规格](../specs/qmt-full-app-real-history.md) FHR-01 至 FHR-04。真实市场完整覆盖、异步下载、真实交易及生产发布均未授资格。

## 固定输入与安装身份

- 完整业务输入：`build/ms-app-current-001/BUILD-003.json`，真正 App `0.1.0a19` wheel SHA256 `adefd23aeab21a90171bb3bc5283bbbac13d9715bb0134e5da084898ec1f736c`，保留完整 35 发行闭包。
- 统一行情包：根已验 `build/qmt-market-root-acceptance-283/installed`；MRC 清单 SHA256 `1a7c8bc72a30e06353c97f68b2a608df50b769dd0e8561c6a52798a6e3793578`。HPR、来源服务、Reader 和 Helper 从 `RESOLVED.json` 取得正式路径并核摘要。
- 独立普通安装：`build/qmt-full-app-real-history-001/runtime`。最终 SDK216 为 `guanheng_market_client-0.15.0`，wheel SHA256 `34579862be4dc777bf2f10cceff64d0df2a242a7ee78f368c06e9a4c744287ab`；BUILD003 原 SDK205 同为 0.15.0，其 SHA 为 `33bf4675a063c0cd46d6a510d582d7c2f4f9755b9e3b46d4e3a69cc121cdc335`。本次在新环境普通安装最终216，未覆盖 B/C 环境。全部 35 个 wheel 的 4690 个非目录、非 RECORD 成员逐字节相符，App/SDK 加载路径均位于本环境。
- 实际 QMT 正文：`D:/software/guoxin/python/GH_WT_MEMORY_VERIFY.py`，运行前后 SHA256 `6be3b6e5d9b41fc6861b40972192e31d7aae72bc73933ca65bddad7ed0a9b89b`。正文、策略状态和既有采集均未修改。

## 完整主链与结果

原 QMT 已存在缓存 → 原命名 SHM → MRC 正式 HPR → MRC 来源服务/Helper/原生文件 Reader → 普通安装完整 App 的正常 `ConsoleSettings.from_environment()` / lifespan → 实际 HTTP 图表和正式 SDK。

测试专用本地转发层保持原签名、请求及响应字节，只允许历史只读 POST、绑定和结果 GET；`history_prepare`、账户和交易 POST 在到达 HPR 前拒绝。它没有替换生产 App 工厂、来源响应或 WT 代码。本轮拒绝数为 0，实际调用全部符合读范围。

| 步骤 | 实际结果 | 证据 |
|---|---|---|
| 原库存图表 | 510300 原库存五根，尾部 2026-10-26 11:30；零实际源调用 | `run-002/ARCHIVE-CHART.json` |
| 实际昨日缓存 | QMT 2026-10-28 14:51–14:55 五根，正常获得 | `run-002/BOUND-RESPONSES.json`、`TAIL-CHART.json` |
| 完整合成 | App 十根 = 原库存五根 + 新缓存五根；时间唯一、无重复 | `MERGED-CHART.json` |
| SDK 原值 | 真实回包 OHLC、量、额共 30 个数值，与 SDK 尾段逐值完全相同；五个时间戳与图表相同 | `SDK-MERGED.json`、`VERIFICATION.json` |
| 重复查询 | 重复 App 图表和 SDK 结果一致，零新增实际源调用 | `REPEAT-CHART.json`、`run-002/RESULT.json` |
| 来源谱系 | SourceSelection 两段 provenance 各五根 | `SDK-MERGED.json` |
| 关闭 | 两个 App 子 owner 均 closed，forced=false，pending=false；HTTP/转发线程结束、读线程为零、管道 EOF、监控与读线程归还、Job 资源关闭 | `run-002/RESULT.json` |
| 外层受管运行 | control006 exit=0，forced=false，tree_zero=true，读线程及资源关闭 | `qmt-full-app-real-history-control-006/build-qmt-full-app-real-history-control-006/result.json` |

本轮 Journal 仅有 **一次 `market.history_1m`**；没有 `market.history_prepare`，账户、下单、撤单、UI 操作或策略启动。准备阶段与首次准入失败均零源调用。实际输入采用 `dividend_type=none`、`fill_data=false`、`subscribe=false`。

## 来源语义及失败原件

来源仍保持 `coverage=unknown`；合成观察明确为 `Partial`，`preparation_state=NotNeeded`，源尾窗为 202610281451 至 202610281455。两段均为 source 原值，价格、量、额单位和分钟区间边界保持原声明的 unknown。十根图表可用与完整市场覆盖分别判断，不能据此确认标准股/元或闭合分钟资格。

首轮只在子 owner 配置准入阶段失败：QA 用仓库 Python 生成 pair，配对清单绑定该解释器，而部署选择的是 MRC 正式 HPR pythonw；另一个来源 owner 的本次控制目录尚未创建。已改为正式 HPR 解释器生成第二份私有材料并创建自己的控制目录。原件 `material`、根 `RESULT.json` 与 control003 保留，零来源调用；成功原件为 `material-002`、`run-002` 与 control006。该修正属于 QA 准备，不修改产品配置校验或放宽身份要求。

## 最终源码、验证与后继

自有入口位于 `tests/integration/qmt_full_app_real_history/`，仅新增 QA 和本文档。`verify.py` 对本次原始回包、SDK、图表、基准与资源记录离线复算通过，新增来源调用为零。最终 `setup.py` 将配对准备委派给正式 HPR 的 `prepare_material.py`；本轮已执行的对应材料原件为 `build/qmt-full-app-real-history-001/prepare_material002.py`，保留其输入与摘要。后继不得将准备入口整理当作额外一次真实源验收。

本轮完成 FHR 正常缓存主链。尚未执行可选九 ETF 日线的同环境端到端、真实异步下载到达、完整策略/交易路径或生产升级切换；这些范围由对应交付与授权继续推进。根负责把本规格与证据登记到共享索引，避免多个会话同时修改同一索引。
