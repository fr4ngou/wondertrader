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


## auxiliary.4.current.2 原价格输入身份修正

Root实际Reader主路径发现：此前AWP同时把历史富集及当前辅助摘要写入publication.input_sha256，而PublishedDaily严格将该字段与NATIVE-READ.inputs.sha256比较。该字段属于原Native价格/因子输入；辅助属于独立current_auxiliary/history reference及完整规范输入身份。AWP本次删除两处覆盖，Reader、V1、Runtime、NativeAnalysisCore与原资金/周期保持。

固定实际证据根为`E:/workspace/wondertrader-qa/awp-price-identity-20261106-001`。FROZEN.json绑定实际旧窗口：publication输入为141a529a0f89cf38dc86a30eaab516687f68d37b196f2a2f56bcfeee422046cd，原Native输入为38b6d4fce5998dcef99d28fc38f9be987c1f63cabdf0910be73d48c1ec9b6bc0。74份完整Native原件另存NATIVE-FROZEN.json。真实原GuanhengRealtimeReader DLL对冻结旧窗口报daily publication native identity；新AWP原原子发布后保留Native输入，原DLL读8证券9268条实际日线、尾日20261105，见READER.json。Reader试验使用固定parser-startup正式安装DLL，路径与二进制SHA完整记录；全部投影缓存写入本QA根。

新普通安装AWP→原发布→Runtime→唯一V1数学→原NSQ目标完成6743事实/16值/7字段消费，见main/RESULT.json。当前辅助修订模型和显式历史知晓时间测试模型（5292行富集）各保持原价格输入；current_auxiliary.sha256及references.history_sha256表达其各自修订，完整RetainedInput纯核摘要三种输入逐一不同，见REGRESSION.json。历史回归所用提前知晓时间为显式测试模型，不授真实历史可知资格。

新版本仅AWP `0.1.0a13+auxiliary.4.current.2`；轮子SHA为573110f35950b4d145e5e2f3bf82c2465dca30ddf9e6ad3ec5b51f54e9674ca9。BUILD.json及build/INSTALL.lock声明精确依赖；POSTFLIGHT.json核轮子RECORD、安装成员和其他三包全部成员未变。Root新独立Runtime21普通安装此AWP并保留Runtime20其余精确依赖，按原同账交接与一致AWP/Reader路径采用；保留100万元含持仓基准及未知委托责任。回退保留已冻结旧轮子及失败原件，通过原正常关闭/恢复入口处理；旧AWP current.1仍有本节已证实Reader阻断，采用时须同步考虑最后兼容发布。现场消费、实际执行及公开页面验收由Root独占。
