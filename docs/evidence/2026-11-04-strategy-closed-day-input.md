# 唯一策略上一闭合日日线恢复

类型：实际运行证据。日期：2026-11-04。状态：八只ETF真实补齐及原WT分析窗口发布通过；自然策略计算和委托结果继续。

## 根因及处理

原分析发布者持续运行并成功查询，QMT八只ETF缓存尾日仍为11月2日。原只读配置未启用缓存准备，因此查询实收时间更新，行情日期保持旧值。沿既有HPR接口为八只ETF补11月3日，原请求身份及结果留存，回读全部返回该日。处理沿已有共享内存来源，QMT正文、账户、交易WRI及金融账本保持。

原Native Reader绑定producer004的状态与源目录。另一个显式启用准备的producer005候选曾成功发布11月3日，配置准入核实发现当前执行权限origin还冻结原发布引用。该候选已按原CLI正常关闭；沿完整原发布SHA恢复producer004，再由原配置恢复读取已更新QMT缓存。其后原Native已绑定入口成功发布11月3日。金融运行全程保持代100ca951及原进程；本次未修改原WT框架，也未改写配置核验规则。

后续每日缓存准备由统一WT数据owner承担，八只ETF纳入同一资料/日线责任。原分析发布者继续只读消费已准备数据；该持续接线交开发者2作为统一数据模块的一部分验收，当前这份证据只证明本次实际闭合日恢复。

## 可复核证据

证据根为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/strategy-tail-preparation-20261104-001`。

- `PREPARATION.json`及source目录：八个原HPR请求均call_returned，作用范围仅11月3日日线；调用返回与覆盖核验分开。
- `READBACK.json`：八只ETF逐项真实回读20261103，原request_id及received_at保存在证券slot。
- `BOUND-RESUME.json`：producer005正常退出，旧发布字节核原SHA，producer004按原恢复入口重新接续；原账运行未重启。
- `BOUND-COMPLETE.json`：原producer004实际PID3012、phase=published、basis_date=2026-11-03，完整窗口SHA为`2e7af9cfa9d7c97cca5bd614affd79822c3780934cf0f3a8a06cf54d2faf2b08`，八只证券完整。后继正常刷新会改变SHA，当前身份以原STATUS与窗口一致性为准。

证券为159780.SZ、510050.SH、510300.SH、510500.SH、512100.SH、515080.SH、588000.SH、589000.SH。源工作根保持`E:/workspace/wondertrader-data/analysis-window-live-20261102-012/producer004`，消费窗口保持同根`current-window.json`。

独立账户查询继续更新，策略现金633075.20元、资本基准100万元及五项非零持仓连续。开盘前策略仍为awaiting_first_strategy_calculation；实际分钟调度、策略输入采用及模拟券商结果由后继开盘观察记录证明。
