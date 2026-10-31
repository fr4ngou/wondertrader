# 当天分钟来源与ETF原生读取

日期：2026-10-28。类型：隔离开发实机证据。范围：三个来源样本、一个ETF的239根分钟；实际账户/订单动作0，生产切换false。

## 触发与结论

真实全推持续处理旧源时间，当前完整实时性未通过。改查另一既有厂商分钟入口，首次仅close查询返回Panel公共索引，不能用三证券共同的15:00索引证明三证券都有有效分钟。后续完整六字段查询明确范围：510300.SH有239有效原行，600000.SH/000001.SZ为公共索引对齐的239行全NaN。单独查询600000返回空DataFrame。此前根据公共索引扩大范围的判断已更正。

## 输入与执行

终端外厂商Python3.6.8运行一次qmt_api.api.get_market_data，显式20261028000000..20261028235959、period=1m、dividend_type=none、count=-1、open/high/low/close/volume/amount。此程序在QMT外，由创建期Job和原总截止管理；QMT策略未新增网络/文件访问、未改动。该独立诊断入口不自动成为产品依赖或替代既有SHM。

三样本完整查询原值SHA65d246658fbfa95f54d522a795492a48b65b4e0f8724e9875ddbe5e23dccdf1a，SDK调用1、0.672秒，原始数据及摘要见build/qmt-live-afternoon-diagnosis-001/DAY-MINUTE-RAW.json、DAY-MINUTE-SUMMARY.json。两个股票空值如实保留；ETF零量原行保留，部分NaN报无资格，不前向填充。ETF标签09:31..15:00，14:59标签未出现，原因待核，coverage=unknown。

单股票对照STOCK-DAY-SUMMARY.json为DataFrame0行，外层exit2表示观察失败并正常回收，0.75秒，非SDK异常或真实数据成功。源本地DAT尾部另只读核实：600000/000001到10月27日15:00；510300到10月26日11:30。此抽样不代表全库存，也说明ETF当前接口数据不同于该磁盘文件尾部。

## 复用现成数据链的实际结果

239条ETF原值→七列CSV/QMI v2 source→现有qmt_minute_import.import_dataset→固定原Helper store_bars及逐字段read_dsb_bars，成功。新隔离根build/qmt-day-etf-import-001，原文件/旧历史store保持。Helper SHA f8ec5eb6d7780bc77999226582488b836d2e3652c93c5e3a62a8dd5bb965319f；QMI SHA8a9442e04d683c50dd1056864cc6315f8a663c11a61200f75316a4b0478e3537；成功收据SHAa18a0bfe002ef17e311b58e634a71bdc08ab2f296abd61362a26cf8b68a25d79。外层0.281秒exit0/非强制/树0/EOF/join/资源关闭。

同根通过既有NativeHistory.read_source_store，固定GuanhengNativeBarFile.dll SHA4f5e2696559011d755edfac1d58296626fdedb6ba46c6d6a0fafc0203eebe62c；239根的来源时间及六字段逐行与CSV完全相同。STRATEGY-READER.json记录起止09:31..15:00、source数值、量额单位/分钟边界unknown、coverage unknown，外层0.125秒exit0且资源回收。首次脚本把coverage小写unknown误写为Unknown导致断言失败，已修正验收脚本；产品合同/数据未变。

## 资格及下一步

已验证一个ETF当天数据的原生存储与现成策略历史读取；两股票当天仍缺有效来源，全市场当天补齐、与旧长期历史合并、自动归档和持续源延迟根因继续开发。该DSB尚未注册到活动服务，未覆盖旧历史或发布环境；策略公共HTTP/浏览器本次未验。来源单位、未出现分钟和交易日完整性保留待核，不能把239根记作全天完整覆盖。
