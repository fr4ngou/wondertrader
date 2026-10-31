# 真实报价、活动分钟与正式CTA组合

类型：最终规格。状态：accepted。范围：NRT-R14后继限定组合验收；生产源码和已有QA保持只读。

QRC1：复用B BUILD005固定普通Appa10安装、ManagedPythonExecutionProcess、CtaExecutionSession、原Factory/ticker及configured唯一业务/数量核。模块A固定Parser2d42/Readerf5f7经现有GH090认证WinSHM只读取full_tick，分钟只读137活动Writer；不启动报价流消费者。日线125天、预算和券商SDK明确为替身。

QRC2：真实价格进入原数量basis及原净额执行；SDK替身按实际原入口价格/数量独立累计账务与模拟成交/查询，允许原执行器拆单，核对实际目标、总数量和后继收敛；不使用固定700/1400或10.01报价假设。报价终态原件SHA与策略实际价格basis逐证券匹配，原证券/时间/单位保留来源声明。

QRC3：至少两个自然分钟的原ticker调度；真实bar与同次原Helper副本逐date/time/OHLC/量额及SHA核实。行情源只允许full_tick，模拟账户/写入使用独立WinSHM与SYNTHETIC身份。独占终端外HPR e Host/新pair/journal容量事前声明≤32并沿原公式计算（首轮11次、最终重跑13条，模块累计最多24次）；3证券批、8000ms轮询、单pump≤8000ms，最终运行预算100秒、真实full_tick最多24次，保持原请求时限和Unknown原ID核查，不POST重派。

QRC4：实际控制停止后确认Parser/Reader/CTA/Host/SDK/线程/Job/管道全关闭，源正文SHA保持，137/140保持运行且唯一Writer。无UI、策略编辑/重启、真实账户/交易/下载、生产切换或WT并发调查。原15:05归档、15:18关闭边界保持，时段不足时不推进时钟或重启采集。

先完成主链，随后按已变QA接缝覆盖异常/独立审查和搬迁安装。真实日线、现金/费用/T+1、全真实策略及生产资格继续由根集成，不从本混合组合推定。
