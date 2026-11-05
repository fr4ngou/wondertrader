# 当前事实

核实日期：2026-11-05北京时间09:25。当前身份沿稳定CURRENT/部署索引定位，正常重启会换代。整体目标active。

## 唯一策略与交易

金融角色仍为cash.4（service.9.resonance121.fresh.1.cash.4），共振ETF1.2.1唯一活动，科创综指角色589680；仅使用用户确认的无真实资金模拟账户尾号1314。当前waiting_market_input，首次自然计算及后继调仓未观察到。既有模拟提交/查询/成交/撤单已验收，不再笼统列为未测。

用户停止旧金额追溯，initial-inventory008/financial-state008保持；现金721311.1元、3实际持仓市值278688.9元、净值1000000元。历史账/交易不迁移，原49命令保持。八ETF分析到11月4日、共同406交易日。

统一入口恢复后，金融控制cbac5320-5b28-4fa8-b776-df884bec522d，WRI32360/Native47840，逻辑实例不变；八组件实际就绪，账户查询继续更新。资金/持仓接续通过与后继策略自动交易分别登记。

## WT入口与独立观衡

日常快捷方式采用wt-control-20261105-001/operator006/group_control.py及group010.json；沿原ServiceController组合HPR、采集、报价、日线与金融五服务。前次完整正常停止/恢复、资金持仓接续证据复用；本次仅替换受影响日线和采集角色。HPR WRI37208/Host71140、采集WRI10380/collector15000/history18760、报价WRI22688/history71892、日线WRI28736/history62204、金融WRI32360/Native47840实际存活。

观衡0.1.0a111+wtgroup.2、SDK0.17独立运行http://127.0.0.1:18143，按各角色CURRENT跟随。spread_sw 11月4日原独立来源已刷新，sse_reference=3686.172；真实图表及API恢复。WT生命周期仍由WT管理。

## 日线与分钟

r001于04:52正式published、continuation_required=false，CURRENT generation2ca1a1e6ead944fcb179db420cc66497。597项价格准备及190批回读完成；941910股票行Native结果保持。300308、588170及上证日线在18143实读均到11月4日。

实际日线program016/daily-service007与分钟program017/data-service003分别固定，源码声明unified.17。只读中断后继、可证HPR未派发识别及重试/新窗口轮流调度已采用，原slot/Journal/请求保持。

登记价格范围目标日股票5572、ETF1717、指数642项可读；全市场完整资格仍未成立，来源历史登记、非价格项、6项股票停牌数量未知及指数/ETF余缺分别记录。指标27项预热不足、6项stale。两常用指数11月3/4日均恢复各240根，实际统一查询可读11月4日15:00；8ETF及当前来源支持的49常用指数优先补齐。北交所366项分钟、SSE.932000映射继续。

早前HPR02:03退出最早原因未知；当前已分离HPR与采集并保留首故障诊断。当前Source/Writer保持，不能以旧成功状态替代实际进程证据。

## 剩余与决策

剩余：1.2.1自然计算及后继调仓；日线全范围余缺；北交所分钟及来源映射；确认无引用的最终清理。此前已清一干净worktree、约461MiB重复依赖及六旧Web，当前引用的配对、故障、金融状态、回退和HPR依赖根保持。

无需用户新增决策。开发者目标保持清除，普通进度留本会话；新增WT框架修改继续先获批准，不研究假设并发缺陷。实际源码、制品、审查和运行结果见[本轮恢复](../releases/2026-11-05-daily-read-and-minute-recovery.md)及[原统一启停](../releases/2026-11-05-independent-wt-control-and-observer111.md)。[原事实](CURRENT-history-20261104-before-cash3.md)及[更早原件](CURRENT-history-20261104.md)保留历史定位。
