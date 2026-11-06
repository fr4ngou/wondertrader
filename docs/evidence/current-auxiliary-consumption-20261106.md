# 当前辅助事实实际消费模块

实现SDO-R3-current。原历史逐bar入口只允许在收盘前已知的辅助事实，11月6日才收到的11月5日统计因此无法进入11月5日收盘行。独立当前视图复用唯一派生与真实decision_cutoff；完整历史仍保留原输入和因果。AWP发布、V1纯核与Runtime消费共用一份事实，不生成新行情bar。

## 已安装主链

固定证据根 `E:/workspace/wondertrader-qa/current-auxiliary-module-20261106-001`。`build004/BUILD.json`核源码冻结前后、四wheel RECORD、普通离线哈希安装、23包依赖及实际安装成员；`main003/RESULT.json`为冻结真实原件→AWP enrich_window→原原子发布→MarketWindowFile.read→evaluate_retained→原V1数学→原NSQ目标的完整模型消费。6743事实、16当前值、角色实际读取7项；6056行真实行情和分析价逐值保持，历史enriched_rows仍0。

真实decision_cutoff为2026-11-06T03:53:03.966654Z（北京时间11:53:03），最近真实行情基准为2026-11-05。沪深300份额概率34.163872804355954、热度47.5、融资分位2.5；科创50份额变化12.99亿份使原kc50_low_accumulation触发BUY，588000目标由0变为0.1667553677690326，其他目标沿原分配公式调整。`ACTUAL-MATH-CONSUMPTION.json`记录原信号函数实际读取，`CORE-RESULT.json`保留历史重放和当前结果，`PUBLIC-DIAGNOSTIC.json`为同一公开core_result消费证据。

信号/分配日期保持算法真实行情基准日，实际当前求值时刻独立报告。相同basis的已有CycleExit继续压制同一模型日重入，下一真实模型日才沿原fresh条件解除；本模块保持原周期规则。同一事实的后继轮询保持原经济目标及代际。历史模型拒绝当前视图；更早历史已生效的值不forward-fill。旧缺字段发布清除请求残留值；真实旧Runtime19/V1a12已安装结果与新包旧路径逐值相同，见`OLD-INSTALLED-BASELINE.json`。

## 精确发行组合

- AWP `0.1.0a13+auxiliary.4.current.1`
- V1 `0.1.0a13`，Core `0.1.0a8`、tzdata `2026.3`
- Runtime `0.1.0a15+currentaux.1`，NativeStrategy `0.1.0a1`
- NativeAnalysisCore `0.1.0a3+currentaux.1`，MarketClient `0.15.0`

四wheel摘要及精确依赖统一见`build004/BUILD.json`与`build004/INSTALL.lock`。AWP精确依赖新Runtime/V1/Core，普通依赖解析不能保留旧严格窗口消费者。NativeAnalysisCore12个业务源码与旧安装a2相同，四项基础源码沿永久compat来源；Runtime沿原46模块闭包，只更新版本和市场窗口接缝两模块。旧正式安装与金融状态保持。

## 采用与回退

Root独占集成与部署。先核本模块源码CAS及四wheel；新独立安装根按INSTALL.lock普通哈希安装，与既有锁定服务依赖组合后pip check。依原配置身份/源码身份交接创建新角色，沿原prepare_transition/resume_reconciled恢复；保留100万元含持仓基准、原周期、金融状态及未知委托责任。采用后核新AWP发布包含current_auxiliary，真实自然计算core_result记录当前知晓截止/基准/7项消费，复核目标/原NSQ、实际执行及公开读取。

回退需Root沿同一正常关闭与恢复入口整体切回原四包及匹配发布配置，保留当前金融状态和未知委托核查，避免把新顶层字段交旧严格消费者。禁止清除slot/ID、改接收时间、重建金融账或重放未知。

本模块安装与重放使用明确隔离flat-cycle及100万元资金模型，未读取账户、未启动服务、未调用Source/交易。现场新自然计算、含实际持仓的执行、AppHTTP/页面展示和上线收据由Root采用后验收；离线模型证据不授这些资格。
