# ETF行情规则纯业务链

类型：功能规格。状态：accepted / in-progress。前缀：NER。依据[完整保留范围](../migration/business-feature-inventory.md)及[COP](guanheng-operator-platform.md)。

## NER-R1 职责与原生接缝

独立包`guanheng-strategy-rules`迁入固定旧QMT提交`6cf508a070392ff976b6b4d6b31b0e6219001e71`的ETF规则1.0.0及其20根特征计算，保留原registry参数范围和app的ready/有效期准入。WT-S01负责分钟调度/窗口来源、WT-S05负责理论持仓/用户状态、WT-S06负责目标与执行、WT-B01/B02负责回放/撮合；本包只拥有确定性业务特征/目标权重及纯值续接。旧worker、StrategyIntent、审批、账本和服务退出运行依赖。

公开`evaluate_etf_rule`接受单证券按时间严格递增的已闭合1m原值、明确实际可知时刻、固定规则配置、当前权重或上次纯状态和知识截止，返回特征/目标轨迹与完整纯状态。一个调用至多4096根，每个特征窗口固定20根；宿主按每证券分别调用，组合预算与交易资格由宿主拥有。原规则的预算是单次该证券上限，本包不增造跨证券分配算法。公开结果可沿现有NSQ `EconomicTarget`接口交纯数量核，实际原生桥由B接线。

## NER-R2 数学与准入

保留原20根窗口的first.open、latest.close、最高/最低、volume/amount总量、量额均值和逐根close/open收益总体标准差；trend=clamp(窗口收益×10)，volume=clamp(末量/均量−1)，liquidity=clamp(末额/均额−1)，均价为总额/总量，零量时取末close。普通数值按原算序，派生不可表示时固定领域错误，禁止把inf经clamp伪装有效分数。

仅20根ready后更新目标。signal=trend×trend_weight+volume×volume_weight，默认0.7/0.3，二者0..1且和与1相差不超过1e−9；signal_threshold默认0.35且0.05..1，volatility_guard默认0.04且0..1，max_weight_change默认0.03且0.001..0.05。budget_weight默认0.20且大于0/至多0.50。current先clamp至0..budget，步长min(max_change,budget)；volatility严格大于guard优先减仓，否则signal≥threshold增仓、≤−threshold减仓，其余保持；confidence=min(1,abs(signal))。即使目标未变也保留该次ready决定及原10分钟有效期，dated零目标为真实规则结果。

输入价格CNY/份、volume份、amount CNY，证券代码使用六位ASCII数字及SH/SZ，非复权、1m、对齐整分钟的闭合结束标签；实际来源资格独立标识，合成样本不授真实来源。配置/bar/state/cutoff/数量消费at的所有时刻由唯一时间准入规范UTC后比较，拒绝夏令时fold导致的未来事实；整分钟也在规范后核，带秒offset不能伪装上海整分钟。每根available_at≥occurred_at、均不晚于知识截止，输入及状态窗口的证券/来源合同一致，顺序/重复/缺少来源身份拒绝。日期在上海固定UTC+08下须为2000..9999年且目标10分钟截止可表示，超界统一领域错误；时段/连续性和交易日准入由A/宿主提供。20根指实际提供的闭合行情根数，不补造休市或缺失分钟。

配置有明确effective_at/valid_until，实际决定在其有效区间内产生；预热阶段不产生新目标。最后ready目标过10分钟、配置到期或尚无ready时，结果标明不可提交并保留可复算纯状态；NSQ转换拒绝不可提交结果。该转换只授纯数量消费，不代表账户/资金/交易/原生运行准入。

## NER-R3 状态、身份和预算

纯`RuleState`保存最后至多20根闭合值、当前模型权重、最后ready时刻/有效期、滚动事件摘要与config身份。完整输入与分段新根续接得到相同最终状态和逐根数学；重复完整调用确定性一致，旧根/配置错配拒绝。该状态仅为算法窗口/目标，可序列化续接；原生仓位、未决委托及账户状态由原owner保持。

公共输入采用不可变领域值，每次入口完整校验，输出规范JSON bytes及to_dict独立副本。RuleResult仅由唯一计算入口创建，公开构造器拒绝任意encoded/state；to_dict和NSQ消费核创建时的内容印记，防止外部替换序列化目标绕过配置。外部JSON续接只重建RuleState，再走evaluate完整准入；印记用于本进程结果完整性，不是外部来源认证。输入/输出各至多8MiB，合计文本至多1Mi字符，每引用至多256字符/每根32项，预算可收紧；perf_counter单调截止至多5秒贯穿校验、窗口循环、编码和哈希。每步窗口固定20，JSON有界增量编码；Python协作时限由宿主原Job总截止补充，不声明硬实时。无磁盘、网络、线程、当前墙钟或旧工程导入。

## NER-R4 验证与交付

先跑闭合分钟→20根特征→规则目标→公开JSON/状态续接→现有NSQ目标/数量消费，普通非editable独立安装执行。再覆盖等号/波动优先/预算clamp/零量、预热与到期、重复/错配/未来/量价单位、数值不可表示、联合文本/输入输出和时限、不可变及跨hash seed。固定原源SHA、输入/目标样本和完整调用结果，经独立规格/规范审查后交A/B。真实A分钟源的闭合/单位及原生桥、回测/执行/页面、全版本和统一安装升级继续按完整goal验收。
