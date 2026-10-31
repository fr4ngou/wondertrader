# 2026-10-21 QMT分钟来源契约与当前缓存观察

类型：源码核准及现场只读记录。状态：公开读取已验证；盘中连续更新、分钟最终性及完整覆盖待验。

## 来源身份与调用范围

只读源码核准时QMT HEAD为 `a3c49d35706c0f3db30f03e2674c1fa2c30f7f9e`，15份关键文件摘要保存在 `build/native/capability-audit/qmt-minute-contract.md`。协议登记实际为 `docs/contracts/qmt-gateway-operations.json`；Broker与Gateway共享原Adapter分派。

现场观察开始于2026-10-21 15:15:02 UTC（北京时间23:15:02）。沿既有Bridge HTTP公开入口提交两个只读操作：market.market_data_ex和market.full_tick。分钟请求显式period=1m、dividend_type=none、fill_data=false、subscribe=false；证券为此前已使用的300308.SZ与688076.SH，范围为当天09:30–15:00，count=500。

未执行下载、订阅、账户查询、交易、终端启停或部署。完整原始结果、health和源身份仅保留ignored目录 `build/native/capability-audit/qmt-current-9f2254a68d`；两次health的来源身份一致。脚本与输入摘要见该目录summary.json。

## 现场结果

| 操作 | 结果 | 耗时 |
|---|---|---:|
| market.market_data_ex | 成功；300308.SZ为0条，688076.SH为120条 | 2.471秒 |
| market.full_tick | 成功；两只证券均有快照 | 2.581秒 |

120条分钟记录提供time/OHLC/volume/amount，时间为可精确表达的整值浮点epoch毫秒，首末对应当日09:31–11:30。此观察证明接口能读取当前已有分钟数据；它不证明当天完整240分钟、原始成交完整性或盘中更新。0条没有足够事实区分未下载、停牌或无成交，保持来源覆盖未知。

快照存在、HTTP成功、Host心跳新鲜与分钟数据齐全分别判断。full_tick不是完整tick流，轮询快照不能直接获得真实分钟高低价重建资格。

## 可复用入口与真实缺口

1. market.market_data_ex可按区间读取1m；market.local_data可独立核已有缓存。显式none/false/false避免跟随策略周期、自动填充或订阅副作用。自动补齐可先从QMT已有数据填入WT原生存储。
2. market.prepare_history_data虽登记为download_history_data，当前Adapter实际限制1d；新受限Host又拒下载/订阅。用户在QMT客户端能下载1m不代表现有公开operation已允许程序下载1m。本轮不扩大原源端权限。
3. 原始协议没有逐bar final/revision标志，也未固定所有版本的时间标签和量额单位。既有真实样本的右端与手→股profile可以作为有边界的开发依据；新来源版本、实时闭合与修订仍需验证。
4. 旧bar normalizer按time加周期筛闭合、成交量未做手→股转换。这是旧消费者设计，不能直接作为WT新接入的时间/单位契约；当前现场统计使用原始结果，未把旧归约结果当作最终分钟事实。
5. Bridge当前bounded-history协调入口仅特判1d；1m即使带history policy仍走普通market分支。新的后台适配需验证实际HTTP预算及同request_id结果领取，不把180秒policy当成每层等待都支持该期限。

## 对接入方案的影响

继续使用QMT主来源、WT原生存储/Reader/Factory及原CTA分钟调度。源获取放在回调外，区分已有缓存读取、主动下载、来源缺口、正常空段和传输错误。公共契约不足时保留明确未就绪状态，不伪造tick或分钟，不恢复旧PG行情链。

下一步按[原生行情方案](../migration/native-market-integration-plan.md)冻结来源、预算、闭合/修订与线程交接接口，再实施相应自有适配。本文没有提供实时分钟完整资格或原始分钟下载授权。
