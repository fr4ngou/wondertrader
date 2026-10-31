# V3动态风险与迟滞纯业务链

类型：功能规格。状态：accepted / in-progress。前缀：NRH。依据[完整策略范围](native-strategy-kernel.md)及[模块C](../migration/parallel-system-delivery.md)。

## NRH-R1 职责与固定来源

`apps/guanheng/strategy_risk`独立发行`guanheng-strategy-risk`，只承担V3 0.1.0及V3 hysteresis 0.1.0的历史→共享特征/信号→风险分配。复用core a6和signals a3公开入口，保留现有App/V2依赖身份。旧QMT固定提交6cf508a070392ff976b6b4d6b31b0e6219001e71的两个allocation.py为数学来源；按原算序保留20日总体标准差、244交易日年化、波动率底限0.05、趋势预算、0.05预算台阶、单证券0.20、分组0.50/0.35/0.20和总量0.90。V3仅无直接信号且最大目标变动小于0.025时跳过。迟滞预算偏离至少0.10且连续三日同值才确认；预算上升保留既有目标，下降按比例缩减；直接信号按原先卖后买、角色和排序处理。

WT能力WT-S01/CTA上下文及WT-B01/B02原回测继续拥有理论持仓、数量、撮合、费用和输出。本包不复制旧backtest_engine、StrategyIntent、账户账本或worker，不产生委托。唯一公开`evaluate_risk_history`返回原始权重及风险快照，供B原生桥后续接线；本包纯数学通过不授予原生/真实来源/券商资格。

## NRH-R2 输入与起点

输入复用`SignalTraceInput`、`FrozenHistory`和`SignalTraceBudget`。先取得本轮独占typed快照，交SST唯一公开准入及信号计算；八证券必须完整，所有证券交易日严格对齐，评估首末日均有行情。市场/辅助来源、时间、单位解释和两类信号起点沿[SST](shared-signal-trace.md)，拒绝未来事实和缺失时间。此版本保持严格逐行收盘可知路径，真实历史首次可知未知的事后数据不能补造available_at准入。

风险计算需要完整逐日close与regime；SST只公开末特征，因此本包对同一独占历史再次调用core的唯一特征函数，算法实现保持唯一。特征从全前缀计算，信号按runtime-full-prefix或backtest-evaluation-range选择起点，分配器沿原流程读取全部特征。公开输出保留完整信号轨迹身份、评估区间内分配事件和风险快照。无分配日期时latest_raw_weights/date均为null；首次有日期的零向量保持真实事件语义。

## NRH-R3 身份、确定性与资源

strategy_id仅允许resonance-regime-v3或resonance-regime-v3-hysteresis，算法身份分别标明原策略版本、no-cycle和风险policy。结果规范ASCII JSON包含input/trace/source/factor和两个原allocation来源SHA、依赖版本、profile及日期/cutoff；pipeline_sha256由去掉自身字段的完整body生成。结果保存不可变规范bytes，to_dict生成独立值。

一个monotonic截止覆盖快照、SST、完整特征、风险循环、编码和哈希；预算沿SST硬限，仅可收紧。数学源码中的随历史增长的循环/推导式传同一check，派生值不可表示时返回固定中文领域错误，失败无可用部分结果。年化/标准差保持原算法与普通输入算序，集合生成评分时按证券排序保证跨进程确定性；同源浮点差额按1e-12核验。stdlib排序/哈希/单次数值操作有界但非硬实时，宿主仍须使用独占Job总截止。本包无IO、线程或持久状态。

## NRH-R4 验证与交付

先跑完整历史→两策略风险结果，再覆盖手算预算、上下边界、分组上限、先卖后买、无信号重平衡/迟滞确认、预算降额和上升保值、预热/空结果、来源/因果、乱序/缺证券/错日期、不可表示、联合预算/单一期限、不可变和跨hash seed。固定合成输入及目标JSON绑定来源；数学验证不导入或执行旧QMT代码。正式非editable独立安装验证公共入口、依赖闭包和无旧路径导入；精确SHA及独立规格/规范审查后交A/B。实际原生接线、真实日线和辅助、资金/T+1、报告页面、升级和全模块资格继续按原目标验收。
