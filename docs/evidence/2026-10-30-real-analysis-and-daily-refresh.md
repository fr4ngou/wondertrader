# 实际 QMT 日线补齐与原生分析窗口

类型：验证记录。状态：实际只读来源、八证券当日日线补齐及原生窗口读取通过；持续自动补齐接线进行中。范围：唯一共振市场状态 ETF 策略的八只证券，不授予真实交易或完整实时策略资格。

## 根因与职责

新安装包的实际 QMT 读取最初得到 2026-10-29 的共同日。510300 日线缓存修改时间为 10 月 29 日，候选末条日期也是 10 月 29 日。按照[迅投内置行情接口](https://dict.thinktrader.net/innerApi/data_function.html)及[官方问答](https://dict.thinktrader.net/innerApi/question_answer.html)（2026-10-30 核对），`get_market_data_ex(subscribe=False)`读取已有本地历史；更新来源缓存由历史准备模块承担。v7 保持只读，原 Native 分钟采集、复权和策略算法保持原实现。

本轮复用正在运行的 v6 HPR `market.history_prepare`，其原 profile 支持 1d/1m。外部客户端经原认证接口向 QMT 共享内存发送请求，由 QMT 原策略线程调用下载 API。QMT 正文没有新增文件读取、网络连接或 SDK 工作线程。补齐只针对 20261030 当日日线；原缓存逐只备份，其他采集与策略保持原状。

## 实际主链与前后结果

固定制品为 `build/root-analysis-system-001/installed001`：WT a11、Host a12、Agent a9、AWP a4 与同包原 Native 分析组件。WT 持有本次只读 Host，原 SHM_READ_PROBE 临时加载配对正文；结束后在 QMT 停止该探针并逐字恢复原正文。观衡和旧 QMT 项目没有参与来源运行。

| 事实 | 补齐前 real-read-002 | 补齐后 real-read-003 |
| --- | --- | --- |
| 实际 SDK 原值读取 | 32 次 | 32 次 |
| 八 ETF 最新共同日 | 2026-10-29 | 2026-10-30 |
| 原 Import 日线行数 | 8878 | 8886 |
| 原 Reader/QNA 后 R24 消费条数 | 3216 | 3224 |
| 整轮耗时、退出 | 70.641 秒、0 | 51.125 秒、0 |
| WT/Host/Native 子树、管道、线程、资源 | 正常回收 | 正常回收 |

八只证券为 159780、510050、510300、510500、512100、515080、588000、589000。每只实际返回均增加一天。前七只起点为 2021-11-01；589000 的实际返回起点为 2025-03-05，保留其真实范围。因子仍沿 SDK 原映射和原 QNA 处理，未改写价格或填造行情。

原 HPR 八个请求均取得 `terminal/ok`，`effect=call_returned`，准备主轮 54.125 秒退出 0。该回包保持 `coverage=unknown`；覆盖结论由随后实际 v7 回读得到。补齐后的源实际实收区间为 2026-10-30T09:38:29.362574Z 至 09:38:52.144832Z，窗口日期和实收时间分别保留。

结果原件：

- `build/root-analysis-real-read-002/{RESULT,MAIN-CONTROL,R24-RESULT,PROBE-RESTORED}.json`。
- `build/root-analysis-daily-cache-003/{RESULT,CONTROL,CACHE-BEFORE,CACHE-AFTER,COMPLETED}.json`。
- `build/root-analysis-real-read-003/{RESULT,MAIN-CONTROL,R24-RESULT,PROBE-RESTORED,ROOT-AUDIT-001}.json`。

根核对了八证券逐只日期和行数差异、32 份成功读取、同包 helper/Reader/probe SHA256、原探针恢复及退出收据。补齐后 Native 输出 SHA256 为 `24d517dcacf4f7e0920e5996df066f4422fb4690b150b3dbb8e8d0f24ac721ab`，窗口发布 SHA256 为 `4abc066745f6d9cc6cad62e7909639cdf0e82efbb922e400bb06415764e02fdb`。

## 保留的失败与修正

`daily-cache-001` 的请求已规划但 `attempted=false`。QA 客户端向原 `rpc_budget` 传入 40 秒，原接口合同上限为 30 秒；离线回归复现旧调用失败并确认 30 秒合法。002 沿原合同修正调用预算，产品运输与截止规则保持。

002 首只请求已发送，旧观察包装在固定轮数后返回 Pending。后继沿同一 request_id GET，确认原调用成功；003 第一只继续核原身份，其余七只分别提交。没有重发未知请求。一次辅助核查曾通过 JavaScript JSON 转存 profile，使浮点数词法由 40.0 变为 40，导致能力摘要变化；该辅助失败单列，后继使用原 Python canonical 请求字节，原已发送身份保持。调试原件位于 001/002/003 独占 build 根。

## 剩余范围

本轮证明实际来源、缓存准备及原生分析窗口的完整读取主链。运行中的 CTA 是否采用新日线并产生目标、完整九组件同实例、模拟券商下撤单及生产发布分别待验；本轮真实下单与撤单均为零。

持续发布者正在接入显式可选的原 HPR 连接，使后继刷新自动准备来源缓存，再由原 v7 读取证明日期；不增加定时任务，也不把下载返回当成行情覆盖。原 a4 包和本轮原件保持，已修正恢复配置身份的 a5 角色另有固定接口，后继组合显式选择版本。
