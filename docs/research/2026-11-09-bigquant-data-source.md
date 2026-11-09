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
