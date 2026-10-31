# 2026-10-21 QMT 本地分钟源语义验证

类型：验证记录。适用范围：国信 QMT 当前来源在 2026-10-20 的 `688076.SH`、`300308.SZ` 历史分钟样本。状态：`DevelopmentVerified`；生产精度、全市场完整性及再分发许可仍待资格核验。关联[分钟导入证据](2026-10-21-qmt-minute-import.md)与[统一策略行情规格](../specs/strategy-market-access.md)。

## 输入与边界

用户自行重启国信 QMT AI ETF 策略后，主任务观察到 18010 恢复，并经既有 Bridge → Gateway → `market.market_data_ex` 读取已下载历史。本次分析仅离线读取这些保存结果及原 QMT 源码；恢复动作归属用户，分析过程没有额外 QMT 请求、账户操作或原 QMT/WT 框架修改。

请求使用 `subscribe=False`、`fill_data=False`、`dividend_type=none`，交易日 2026-10-20。正式 1m 输入在 `build/native/live-source-probe/history-f0c812373e6a4484957a181447982650/`；其 `raw-result.json` SHA256 为 `7b9ee0110d36e18e5b57473f57ca19e0ff9cb069cb46ffb6eb0bc7472aff17a1`。同目录 `source-identity.json` 的前后身份完全一致，原始身份字段保留在 ignored 私有目录。先前 `history-e78956ec42db4e5295b6b7a4bec2271a/` 的数据与本次逐值一致。5m 对照来自 `history-30cd08377f9f486db8266e64014000d5/`，由主任务记录采集前后身份一致。

原始行情、身份和完整逐桶结果保留本地，不纳入 Git。复现脚本及结果位于 `build/native/live-source-probe/semantics/`：`analyze.py`、`compare_five.py`、`profile_evidence.py` 分别产生 `analysis.json`、`five-minute-comparison.json`、`profile-evidence.json`。证据文件包含输入、相关原 QMT 源码及分析结果 SHA256。执行方式为从 WT 仓库根目录使用 `D:/workspace/qmt/.venv/Scripts/python.exe -B` 顺序运行这三个脚本。

## 时间标签与跨周期正负对照

1m 为 189 / 239 条，均按时间严格递增、无重复、对齐整分钟，首末为北京时间 09:31 / 15:00。5m 两代码各 48 条，首末为 09:35 / 15:00。将每个 5m 标签 T 的 1m 集合选为 `(T−5m, T]`，按首开、最高、最低、末收及量额求和，与原始 5m 比较：

| 代码 | OHLC 完全相等 | amount 完全相等 | volume 完全相等 | 每桶原始 1m 行数 |
|---|---:|---:|---:|---|
| 300308.SZ | 48 / 48 | 48 / 48 | 48 / 48 | 47 桶 5 行，1 桶 4 行 |
| 688076.SH | 48 / 48 | 48 / 48 | 48 / 48 | 14 桶 5 行，18 桶 4 行，15 桶 3 行，1 桶 2 行 |

量额由 JSON 数值的十进制表示转换为 Decimal 后求和、比较；96 桶量额差均为 0，无需金额容差。脚本同时记录一元及假设 binary32 舍入界的诊断结果；这些宽限没有参与本次通过结论，也不构成源精度契约。跨周期未观察到成交量截断差值。

负对照将 1m 标签视为左端、选 `[T−5m,T)`：300308 的 OHLC、amount 均为 0 / 48 匹配，688076 为 15 / 48、7 / 48（稀疏窗口可能偶合）；最大金额差分别为 222726844、2040132。将两周期都视为左端、选 `[T,T+5m)`，两个代码 OHLC、amount 均为 0 / 48 匹配。

因此 `minute_boundary=right` 获得本来源、本日期样本的真实聚合实证。此次检索的官方字段表仅将 time 描述为时间，尚未找到适用于该国信版本的明确区间契约；样本证据仍有来源和日期边界。两周期可能共用底层文件或生成逻辑，完全一致不能独立证明交易所逐笔成交完整性。

## 量额单位与源精度

2026-10-21 查阅的[迅投云策略 get_market_data_ex 官方字段表](https://knowledge.thinktrader.net/docs/cloud/data_function.html)明确把 1m / 5m 等 K 线 volume 定义为手；[官方换手率示例](https://knowledge.thinktrader.net/docs/cloud/code_examples.html)明确使用乘 100 进行手到股的换算。这是一般接口文档及示例，尚缺国信安装版本的固定版本说明。[内置 Python 数据结构表](https://dict.thinktrader.net/innerApi/data_structure.html)的 Bar 栏仅写成交量、成交额；Tick 栏的单位说明不能单独用作 Bar 单位证据。

据此，当前股票源 profile 采用 `volume_to_shares=100`，表示源手数换算后的股数口径。样本全部 volume 为整数手值；该换算保留源精度，无法恢复源未表达的不足一手部分，不应标为精确成交股数。

对于 `amount_to_yuan=1`，此次检索的官方 Bar 表未明确标注币种单位，证据等级为本样本量价尺度推断。以官方手单位换算后，`amount / (volume × 100)` 与价格尺度吻合：

| 代码 | 正量行 | 隐含均价范围 | 隐含均价 / close 中位数 | 位于 OHLC 范围内 |
|---|---:|---:|---:|---:|
| 300308.SZ | 239 | 638.263957–672.176667 | 1.000129 | 229 |
| 688076.SH | 186 | 27.820381–39.370000 | 1.003772 | 66 |

源手值较小时量化误差占比明显，688076 有三条 volume=0、amount>0，标签为 10:57、13:48、14:09。保留这三条；原值与条件推算均留在本地 `analysis.json`。在量额系数 100 / 1 假设下，分别相当于约 47.021、81.024、65.973 股的价格金额尺度，这些分数并非真实成交股数。手值向下量化假设的区间检查在 300308 为 238 / 239 行相容、688076 为 188 / 189 行相容；另两行金额分别比 `源手数 × 100 × 单一成交价` 少 4 / 19。该结果提示量化或舍入，实际源转换顺序和金额精度尚未验证。

分析同时检查 volume 系数 1 / 100、amount 系数 1 / 1000 / 10000 的组合。100 / 1 是与官方手单位及样本价格尺度共同相容的配置。开发导入可采用该值；生产资格需补固定版本单位、金额精度与原始股数证据。不得为通过验收删除零量非零额记录，或把所有隐含均价都处于 OHLC 范围内设为本源的既定事实。

## 缺分钟与原 normalizer 职责

仅为诊断生成 09:31–11:30、13:01–15:00 的 240 标签参考网格。300308 缺 14:59；688076 缺 51 个标签、分布于 38 段，完整列表留在 `analysis.json`。688076 的上午末标签 11:30、下午末前 14:58–14:59 均缺失。上述网格来自分析假设，正式计划必须取自日历事实所有者的指定版本事件，并结合证券例外；本次未读取该交易日权威日历事件。

[官方内置接口说明](https://dict.thinktrader.net/innerApi/data_function.html)及[官方本地数据示例](https://dict.thinktrader.net/innerApi/code_examples.html)将关闭订阅后的读取关联本地数据。当前请求使用 `fill_data=False`。缺标签可能涉及本地文件覆盖、交易稀疏或源生成规则；现有保存结果无法分别确认原因。缺标签桶的 1m 量额与 5m 完全一致，支持当前来源的稀疏表示特征；全天完整声明仍需独立证据。导入保留 189 / 239 条，不补齐 240，不制造零量分钟。

只读核查原 `D:/workspace/qmt` 的 `qmt_agent/broker/adapters.py`、`encoding.py` 和 `src/qmt_platform/services/bridge/bar_ingestion.py`：market_data_ex 参数经适配器传给 QMT；DataFrame 编码保留记录；normalizer 转换时间和数字、检查 OHLC、排序去重。将实际原始结果送入原 `normalize_closed_bars`，428 条全部保留，时间及 OHLCV/amount 逐值不变。本样本根数差异发生在保存的原始返回中。

原 normalizer 的 `_closed` 对 1m 使用 `bar_at + 1 minute <= now`。离线边界实验在标签时刻及 +59 秒尚不输出，+60 秒才输出。结合本次右端标签实证，这会额外等待一分钟。昨日静态导入不受影响；实时闭合分钟接入需由其职责层结合时间 profile 处理。此研究没有修改原 QMT 行为。

## QMI 开发资格结论

当前来源样本采用 `Asia/Shanghai`、`minute_boundary=right`、`volume_to_shares=100`、`amount_to_yuan=1`、`adjustment=none`，资格保持 `DevelopmentVerified`。`source_license` 记录 `user-authorized-guosen-qmt-local-history; redistribution-unverified`。正式身份由采集目录的 `source-identity.json` 绑定；`profile-evidence.json` 给出字段证据等级和输入哈希，不替代实际导入 manifest。

真实源精度、金额单位固定版本契约、全天日历覆盖和再分发许可仍未完成验证。本记录支持当前开发数据导入及原生读取实验，生产资格由后续完整证据决定。
