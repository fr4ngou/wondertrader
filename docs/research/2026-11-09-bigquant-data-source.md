# BigQuant 数据来源与读取验证

类型：来源研究与使用记录。验证日期：2026-11-09。当前资格：研究与历史补采候选。

本次使用原受控凭据完成 SDK 认证，并取得股票未复权日行情、基金静态信息、融资融券交易明细及市场统计的实际数据。此次读取继承[市场广度备用来源补采](../evidence/2026-11-08-observation-breadth-alternative-sources.md#t2108-与-bigquant)的核查范围。该记录反映 11 月 8 日的权限状态。

## 账号权限与读取方式

- 2026-11-09 供应商试用清单列有 258 张只读表，每周额度为 60,000,000 cell，供应商说明每周一凌晨刷新，清单截止日期为 2026-11-16。后续使用前以当时有效的授权清单和额度为准。
- 隔离环境实测版本为 Python 3.11.15、`bigquant==0.1.11`、`bigquant-core==0.1.14`。使用 `bigquant.init(ak=..., sk=...)` 完成 AK/SK 认证，经 `bigquant.dai.query(...).df()` 读取。凭据由当前 Windows 用户从受控加密位置读取，脚本、命令行参数、日志和 Git 只保存无凭据的使用说明。[BigQuant SDK 使用文档](https://bigquant.com/wiki/doc/vac4qwmQr4)
- 先查授权表清单，再查 `https://bigquant.com/data/datasources/<表名>` 的字段、单位、粒度和时间语义。查询显式列出所需字段，同时用 `filters` 限定交易日分区，按需限制证券与返回行数。宽表如 `cn_stock_prefactors` 应逐字段选择。
- 先核对已有本地缓存。新读取保存 SQL、分区过滤条件、UTC 请求时刻及返回数据。首次回包核验分别确认鉴权、可读表、有效业务行、键唯一性和日期范围。保存的请求时刻表示本次读取时间，历史首次可知时点需要单独取证。

认证后可运行以下最小查询。示例按两只 ETF、两个交易日、三个字段读取，结果在本地排序。

```python
from bigquant import dai

shares = dai.query(
    """
    SELECT date, instrument, public_float_share
    FROM cn_fund_static_data
    WHERE instrument IN ('159352.SZ', '159780.SZ')
      AND date BETWEEN '2026-11-05' AND '2026-11-06'
    LIMIT 4
    """,
    filters={"date": ["2026-11-05", "2026-11-06"]},
).df().sort_values(["date", "instrument"])
```

## 已验字段与适用范围

| 数据 | 已验字段及结果 | 使用边界 |
|---|---|---|
| 深市 ETF 份额 | `cn_fund_static_data` 的 `date, instrument, public_float_share`。159352 自 2024-10-15 至 2026-11-06 返回 499 条，159780 自 2024-09-24 至 2026-11-06 返回 509 条。两只的键唯一，所取份额均为正数，单位为份。 | 表中日期是盘前快照日。两只基金的 2026-06-30 公告期末总份额分别为 21,591,101,746 份和 2,978,048,583 份，均与 07-01 盘前值一致，同日盘前值分别为 21,216,101,746 份和 2,968,048,583 份。归属到前一交易日及回测可用时点仍须跨日期验证。沪市对照 510300 的两天样本为 0，供应商文档将沪市流通份额列为全 0。[静态表](https://bigquant.com/data/datasources/cn_fund_static_data) · [159352 基金资料](https://www.nffund.com/new/personal-financing/detail.html?fundCode=159352&tab=redemption-list) · [159780 二季度报告](https://static.cninfo.com.cn/finalpage/2026-07-21/1225434371.PDF) |
| 股票成交额 | `cn_stock_real_bar1d` 的 `amount` 为未复权逐股成交金额，单位为元。11 月 6 日沪深逐股合计 16,576.01 亿元，交易所股票汇总合计 16,589.97 亿元。 | 逐股成交额用于研究、逐股对照与候选重建。交易所统计范围由原表定义，正式成交额沿原合同。日表包含沪深北，深市该日 2,906 行中有 4 行 `amount` 为空。供应商文档将停牌或无成交日的成交额列为空。[未复权日行情](https://bigquant.com/data/datasources/cn_stock_real_bar1d) |
| 融资余额 | `cn_stock_margin_trading_detail` 的 `financing_balance` 单位为元。11 月 5 日、6 日按沪深北分组后的合计均与 `cn_stock_margin_trading_market` 的 `method='sum'` 行一致。11 月 6 日沪深明细合计 21,215.51 亿元，交易所汇总合计 22,474.68 亿元。 | 汇总表覆盖明细表中的沪深北证券。即使剔除北交所，明细覆盖仍与交易所汇总有差异。交易所沪深汇总用于本次对照。现行补充事实中的融资余额仍沿原供应商报表范围。[融资明细](https://bigquant.com/data/datasources/cn_stock_margin_trading_detail) · [融资市场统计](https://bigquant.com/data/datasources/cn_stock_margin_trading_market) |
| T2108 历史价格 | `cn_stock_real_bar1d` 的 `close, adjust_factor` 分别是未复权收盘价与累计后复权因子。600000.SH、000001.SZ、920001.BJ 在 2026-06-10 至 08-24 各有 53 个有效价格与因子。 | 现行方法使用 QMT `front_ratio` 等比前复权序列。后续对照需要覆盖除权、停牌、上市区间和全股票池，核验最近 40 个有效点及大于、等于、小于均线的分类。[观衡观察规格](../specs/independent-market-observation.md) · [复权因子口径](https://bigquant.com/data/datasources/cn_stock_real_bar1d) |
| TRIN 争议点复核 | 同一未复权表返回 2026-11-03 的 300223.SZ 收盘价 99.50 元及 11-05 的 300750.SZ 收盘价 264.06 元，均与既有独立参考值一致。 | 两个样本可作收盘价交叉证据。正式历史修订仍需按观察合同验收当日股票池、价格、成交量及重算结果。[原争议记录](../evidence/2026-11-08-observation-breadth-alternative-sources.md#沪深北历史) |

## 本地缓存与后续采用

已验样本存放在受控数据目录 `E:/workspace/wondertrader-data/bigquant-sdk-validation-20261109-002/`。同范围优先从以下 JSON 复核，缓存按当次查询范围使用。

| 文件 | 范围 |
|---|---|
| `etf_float_history.json`、`etf_float_shares.json` | 两只深市 ETF 的选定历史区间，以及与 510300.SH 的两日对照。 |
| `stock_turnover.json`、`turnover_by_exchange.json` | 三所样本证券的两日金额及 11 月 6 日分市场聚合。 |
| `margin_detail.json`、`financing_by_exchange.json`、`margin_market.json` | 三所融资明细样本、分市场汇总和供应商全市场汇总。 |
| `t2108_price.json`、`trin_close.json` | 三只股票的价格与因子历史，及两笔 TRIN 原价争议样本。 |
| `exchange-reference/verification.json` 及同目录原件 | 2026-11-06 交易所融资余额、股票成交额的原始响应、单位、统计日和核验结果。 |

正式接入属于后续采用任务。沿[市场补充事实规格](../specs/market-supplement-facts.md)和[市场观察规格](../specs/independent-market-observation.md)，沿 QMT 优先的来源规则，按目标字段验证统计范围、单位、覆盖、首次可知时点及消费结果，保留来源身份并独立验收发布。

## 2026-11-14 WT 备用链路隔离验收

沿已存在的本机受保护凭据和 Python 3.11 隔离环境，调用 WT 的 SDK 工作进程实际读取 `cn_stock_index_bar1d` 与 `cn_stock_real_bar1d`。中证2000的 2026-11-12 和 2026-11-13 成交额分别为 407142700000、342201380000 元，WT 补充目录两行均保留 `BigQuant` 来源和查询原件。观衡从同一隔离 WT 快照读回 4071.427 和 3422.0138 亿元。日期覆盖限于本次两日请求。[指数日行情表](https://bigquant.com/data/datasources/cn_stock_index_bar1d)

11 月 13 日股票查询返回 5579 行，与 WT 已归档同日股票池、收盘和前收盘核对后取得 5570 个有效交易样本。成交前 5% 占 45.4604%，涨跌幅中位数为 −2.00%。聚合通过 WT 定日事实接口读回，观衡按该快照得到相同结果。隔离证据位于 `build/observation-bigquant-live-qa/results.json`。生产启用及自然交易日连续性另验。[股票未复权行情表](https://bigquant.com/data/datasources/cn_stock_real_bar1d)

扩展中证2000验收到 2024-11-01 至 2026-11-13，共 494 个交易日。WT 成交额归档 493 个有效值，2026-04-24 缺合格成交额。观衡同版计算出 83 个完整合力分和 19 次事件，最新事件为 2026-11-11。当日中证2000领先沪深300 5.7796 个百分点，成交接力倍数 0.9965。11 月 13 日合力分仍受 4 月 24 日成交额缺口影响。历史批次统一保存进度，每行保持原件证明。隔离结果见 `build/observation-smallcap-history-qa/results.json`。

随后通过中证指数 `index-perf` 原件补齐 2026-04-24 的 5560.77 亿元，493 条 BigQuant 事实继续沿用。隔离 WT 目录达到 494 日完整覆盖。观衡同版复算出 219 个合力分、19 次事件，11 月 13 日合力分为 0.2603。隔离结果见 `build/observation-smallcap-history-qa/completed-results.json`。[中证指数中证2000资料](https://www.csindex.com.cn/#/indices/family/detail?indexCode=932000)

对科创看板的 252 个交易日窗口 2025-10-31 至 2026-11-13，生产 WT 原定日事实目录只有 68 日，缺 184 日。最近五个交易日已有股票池的四日均通过 BigQuant 对照，11 月 10 日缺原定日事实。历史接入需先补独立可核的股票池和同日行情参考，才能计算合力分和事件。隔离覆盖审计见 `build/observation-structure-history-qa/audit.json`。

回放既有市场广度历史归档，184 个缺失日中有 183 日具备可重建的股票池及同日价格参考。沪深沿归档的 BaoStock 或已校验 Tushare 日线，北交所沿原行情、上市区间和停复牌证据。股票池采用事后核实的上市区间。另用 BigQuant 对照区间首尾各两日，2025-10-31、2025-11-03、2026-07-30、2026-07-31 分别得到 5431、5433、5527、5527 个有效交易样本，四日均通过 WT 股票身份、收盘价和前收盘价校验。回放和抽查见 `build/observation-historical-stock-facts-qa/coverage.json` 与 `bigquant-samples.json`。逐日原件链绑定、其余日期的对照和 WT 目录发布仍待完成。

11 月 10 日 QMT 当日股票池有 5579 只。QMT 原价回读、Tushare 当日未复权日线与 BigQuant 对其中 5572 只有成交股票的当日收盘完全一致。Tushare 当日除权前收与 BigQuant 全部一致，包括先前和 QMT 上一交易日收盘存在差值的 13 只，以及上一交易日缺日线的 5 只。其余 7 只在 BaoStock 当日原件均为停牌，且在 BigQuant 均无正成交额。一只 BigQuant 池外证券按 QMT 定日股票池排除。四份来源的身份和采集时刻随隔离目录保存。[Tushare A 股日线](https://tushare.pro/document/2?doc_id=27) · [BaoStock 行情字段](https://github.com/zxygithub/baostock/blob/master/docs/pythonAPI.md)

用上述原件生成隔离 WT 快照。观衡经 WT 接口读回 11 月 10 日的成交前 5% 占比 42.7417%、涨跌幅中位数 +1.3117%，样本数为 5572。隔离事实只验证该看板所需的股票池、价格和成交状态，换手率留空。证据位于 `build/observation-historical-stock-facts-qa/nov10-isolated-wt/results.json`、`nov10-independent-source.json` 和 `nov10-baostock.json`。正式 WT 历史目录仍待接收带来源绑定的事实。

随后对 2025-10-31 至 2026-07-31 的 183 个缺失日执行了完整 BigQuant 核对，183 日均通过 WT 的股票池、交易状态资格、收盘价和前收盘价校验。独立价格参考包含 148 日 BaoStock 和 35 日 Tushare 沪深日线，北交所沿原官方日 K。逐日绑定保留历史配方摘要、定日证券清单、参考原件和 BigQuant 回包。17 日 Tushare 原件只留存归档录入时刻，逐日绑定明确标记该时刻为采集时间上界，历史首次可知时间均未知。供应商查询结果和全量比对分别见隔离目录 `bigquant-history/` 和 `bigquant-full-comparison.json`。

在隔离目录中通过 WT 定日事实扩展入口合并 183 个历史缺失日、11 月 10 日及现有 68 日，后者同样通过 BigQuant 核对。观衡经正常 WT 接口逐日读回 252/252 个同源股票横截面，窗口从 2025-10-31 至 2026-11-13。逐日结果见 `history-isolated-wt/results.json`。

将同一历史配方向前补 33 日，隔离 WT 接口覆盖 2025-09-08 至 2026-11-13 的 285/285 个交易日。观衡同时通过 WT 读取科创50和沪深300日线，算出从 2026-09-21 起的 34 个完整合力分，9 月 22 日触发一次事件。11 月 13 日合力分为 −0.5040，与独立复算一致。11 月 9 日至 13 日的五个已收盘交易日均有可判定状态，观衡最近事件目录返回完整且无触发。读回与计算记录见 `history-with-warmup/results.json`、`history-with-warmup/star-model-results.json`，预热横截面对照见 `bigquant-warmup-comparison.json`。此次使用隔离 WT 快照，生产接入另验。

以候选源码 `c2f953f6` 构建并安装 WT 与观衡离线制品。用隔离 WT HTTP 重读科创价格，以已经核实的横截面和中证2000最近五日结果生成观衡隔离快照 `f16686d14585bb9eb8e3fd571c4da93c3b46ecbc6850bff1aadff84878f09e19`。保留原沪深300 ETF 市值占比的两日分区。安装后的观衡以同一快照提供三组 API 结果，Edge 在 1660×1330 验证多看板和 11 月 11 日中证2000标记，940×1050 验证三图纵排。11 月 13 日复核科创合力分 −0.5040、中证2000成交额 3422.0138 亿元、沪深300 ETF 市值占比 1.8039%。受控证据目录为 `E:/workspace/wondertrader-build/observation-workspace-real-browser-02/`，其中 `BROWSER-RESULT.json` 的 SHA256 为 `22a7fd45cee6f6bd5089542c30a499178162fffeee4731c57ee613aad1e22d0d`。本次组合使用已核历史窗口，逐日生产调度及完整 IPO 数据窗口仍待验收。
