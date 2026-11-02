# 指数长日线实际接入

类型：本机上线验收记录。状态：上证指数2015年起日线已接入独立WT18146，并由原a86观衡18143读取。范围：本次003行情历史接收时点；账户与资金的后继接线另行登记。

## 已上线范围

源码已合入`49bd4298264f0a505fe9f0b9b03d9cf575ddbd26`、`6457158101f3d8c2bb18e67713fc1978bc6cbc6c`。离线导入按明确交易日期范围读取原DAT，记录全文件摘要、扫描/选中/排除数量；日线日期标签与分钟真实时刻分别处理。原Helper、Importer、Reader及MarketClient继续承担转换和读取。

| 数据或运行入口 | 本次实际归属 |
|---|---|
| `SSE.000001`日线 | 已下载QMT原件`D:/software/guoxin/datadir/SH/86400/000001.DAT`；显式选择2015-01-01至2026-10-30，实际2015-01-05至2026-10-30共2870条；转入独立schema3原生日仓，替换原短分钟聚合日线路由。 |
| `SSE.000300`、`SSE.000016`日线 | 保留18142配置的原日线owner；003另行转换的5294、5532条长原件独立可读，本次上线沿用原owner。 |
| 其余指数、股票、ETF和分钟 | 沿原routing及数据归属，50项指数清单保持；本次只改变`SSE.000001`日线路由。 |
| WT18146 | `E:/workspace/wondertrader-data/index-long-daily-wt-20261102-001/DEPLOYMENT.json`；仅托管原history组件。旧18142及其配置、服务保留。 |
| 观衡18143 | 同一`0.1.0a86+capital.1`安装，采用`E:/workspace/wondertrader-data/observer-controlled-web-20261102-a86-history-001/web-profile.json`，历史地址为18146。观衡只读取WT；WT与独立市场更新各自运行。 |

量字段保留原数值及`unknown`单位。日线OHLC只读资格和量指标资格分别判断，记录未提升为已知股/手，也未补造行情或交易日完整性。

## 实际结果与固定原件

Root接收证据目录：`E:/workspace/wondertrader-qa/root-index-daily-intake-20261102-003`。

- `HTTP-VERIFIED-001.json`：真实HTTP经原MarketClient查询50项指数通过；上证2870条的日期、开高低收、量、额逐值等于CSV。2016年返回244条，旧18142同年返回0条。
- 同一证据核对旧沪深300/上证50响应各58条、股票300308响应17条、ETF588170响应12条及分钟响应，均与原响应相同；旧18142保持运行。比较只授这些实际查询窗口及字段的资格。
- `OBSERVER-CONNECTED-001.json`：新历史实例`13bcaaa3-4365-445f-b346-a1548483d58f`、WT控制`2abe8887-4e84-4764-9919-dc4f83162162`，观衡控制`076cffcf-cee2-4233-ae9d-bb7ee4dd78a4`。观衡profile原字节SHA256为`822bb03addd51ba0bc813320fa135e9b0ddaaddb30c5de75195267b0f3a410e4`。
- `OBSERVER-PREVIOUS-CLOSED-001.json`：旧Web及启动器退出码均0，`shutdown_complete=true`，两类Reader线程均0；随后沿同一安装启动新profile。自选SHA256保持`1c0fefa69843b23447e3a1c05f88858eaa725d3dbea448871a04b487f35f7a7e`，原账户绑定保持。该接收时点实际策略资金仍未发布，后继账户/资金工作单独验收。

上述接收记录的QMT/SHM调用、下单和撤单均为0。本次文档收口只读固定原件和源码，未新增测试、启停或切换。启停与回退步骤见[本次发布记录](../releases/2026-11-02-index-long-daily.md)。

## 尚未取得的资格

完整上证原件有8751条，1990-12-19起。8条旧计数按既有分钟布局投影出现负值，日线原始计数语义仍待同源对照；全量默认导出继续拒绝该不确定输入。全8751条、三份原件合计19577条的全量导入仍未完成。1990/1991诊断读取及日期修正的离线证据不授当前18146早期日期支持资格，线上证据明确`early_1990_support_deployed=false`。

004的`399001.SZ`完整8691条已完成离线数据准备与逐字段回读，尾日为2026-10-23；旧日线路由包含10月29日，因此004尚未替换现行路由。交付原件分别为`E:/workspace/wondertrader-qa/index-daily-full-cache-20261102-003/DELIVERY-003.json`、`E:/workspace/wondertrader-qa/index-daily-full-cache-20261102-004/DELIVERY-004.json`。

本次接收保留观察8表整体替换的完整覆盖要求；SSE参考数据采用、账户资金和交易链分别验收。回退命令已按原源码核对，本轮未执行回退。
