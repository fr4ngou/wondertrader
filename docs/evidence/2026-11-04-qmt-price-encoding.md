# QMT标准委托价格尾差修正

类型：根因回放与候选构建证据。日期：2026-11-04。状态：自有适配候选已编译，原条件及未改Source核验器主链通过；线上采用另行记录。

## 根因与范围

WT原股票执行器按整数档位乘合约double tick生成限价。`2885 * 0.001`的最短往返字符串为`2.8850000000000002`，原Source精确十进制规则判定离档。真实本轮第9和第16条通信命令均返回`definitely_not_called / sdk_entered=false / price_off_grid`，其余14条命令分别对应券商完整查询中的14笔已成交订单。没有通过改写原命令、清除通信记录或重新发送旧身份取得通过结果。

修正唯一位于自有[StandardQmtTrader](../../src/TraderQMT/StandardQmtTrader.cpp)的WT价格到通信十进制转换。沿用WT合约tick，仅消除有界浮点尾差，保留真正离档输入。Source、WT框架、金融账本、持仓及现有命令原文保持。要求见[标准Trader规格](../specs/native-qmt-standard-trader.md#当前实施边界)。

## 固定输入与结果

QA目录：`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`。

- `ORIGINAL-ORDER-AUDIT.json`：四查询的原请求身份、时刻、结果摘要，按持久事件的完整原token与券商委托号逐笔核对，14条已调用命令均有订单和成交；第9、16条明确未调用。
- `price-encoding001/BUILD.json`：原源码`38fbbaca4852edc8370eac64c41be2bac894bcac3e224950a3d89a115684d223`与候选源码/对象/DLL摘要；沿当前限定链接清单只替换自有Standard对象，原mapper修正继续保留，框架差异没有新增。
- `PRICE-ENCODING-REPLAY.json`：原WT算式、上下相邻表示、分价格单位、0.005单位、科学计数tick及整十单位共10种输入，实际送入未改的已安装Source `TradingKernel`；使用内存SDK替身，真实下单0次。

原失败输入在修正前没有进入SDK；修正后运输`2.885`并且恰好调用一次替身SDK，实际限价为2.885。`2.8851`与`2.8855`仍以`price_off_grid`拒绝；tick资料缺失时保持原值和原拒绝结果。未把未知价格规则当成允许。

## 限制

本记录证明构建与Source主链回放，独立审查和线上加载、原生标准入口后续自然委托结果分别保存。全量调仓、买入阶段和正常停止验收继续沿总目标完成，局部修正不代表整体交易交付完成。
