# 当前事实

核实日期：2026-11-05北京时间11:41。当前身份沿稳定CURRENT/部署索引定位，正常重启会换代。整体目标active。

## 唯一策略与交易

金融角色cash.5（service.9.resonance121.fresh.1.cash.5），共振ETF1.2.1唯一活动，科创综指角色589680；仅使用用户确认的无真实资金模拟账户尾号1314。09:35自然行情驱动8个目标，已有自动模拟买入及成交。既有模拟提交/查询/成交/撤单验收保留。

100万元含持仓基准、initial-inventory008与financial-state008保持；原721311.1现金/278688.9市值为启动基准，自动成交后数量及估值已经变化，不再作为当前余额。历史账/交易不迁移，原命令与金融文件保留。

cash5于10:15经原process_lost_reconciled启动，跨日成交及159780今天09:36:13开仓周期已实际恢复。随后事件历史重放导致成交观察落后于持仓；11:37实际OS检查确认Native4484/WRI21352均已退出，正式故障记录为10:50 runtime/plugin1/host3/session4。具体退出首因仍待核实，当前金融为faulted，不能以旧buying帧宣称正在执行。

当前优先修正自有StandardQmtTrader首次连接事件前沿，初始完整查询后只交付后继增量，原未知委托继续原ID核查。原source/Host增量采集保持，新增WT框架修改为0。

## WT入口与独立观衡

日常快捷方式采用wt-control-20261105-001/operator006/group_control.py及group011.json；沿原ServiceController组合HPR、采集、报价、日线与金融五服务。11:41实际页面API显示四个数据角色ready、金融faulted；采集collector15000的OS身份仍存在。cash5解释器014与稳定native-execution007路径承载同批新原生组件，旧制品保留回退。

观衡0.1.0a111+wtgroup.2、SDK0.17独立运行http://127.0.0.1:18143，按各角色CURRENT跟随。spread_sw 11月4日原独立来源已刷新，sse_reference=3686.172；真实图表及API恢复。WT生命周期仍由WT管理。

## 日线与分钟

r001于04:52正式published、continuation_required=false，CURRENT generation2ca1a1e6ead944fcb179db420cc66497。597项价格准备及190批回读完成；941910股票行Native结果保持。300308、588170及上证日线在18143实读均到11月4日。

实际日线program016/daily-service007与分钟program017/data-service003分别固定，源码声明unified.17。只读中断后继、可证HPR未派发识别及重试/新窗口轮流调度已采用，原slot/Journal/请求保持。

登记价格范围目标日股票5572、ETF1717、指数642项可读；全市场完整资格仍未成立，来源历史登记、非价格项、6项股票停牌数量未知及指数/ETF余缺分别记录。指标27项预热不足、6项stale。两常用指数11月3/4日均恢复各240根，11:41实际统一查询中300308、588170及上证分钟均可读今天11:30；8ETF及当前来源支持的49常用指数优先补齐。北交所366项分钟、SSE.932000映射继续。

早前HPR02:03退出最早原因未知；当前已分离HPR与采集并保留首故障诊断。当前Source/Writer保持，不能以旧成功状态替代实际进程证据。

## 剩余与决策

剩余：交易运行故障与事件积压修复、1.2.1持续后继调仓、带活动单正常停止；日线全范围余缺；北交所分钟及来源映射；确认无引用的最终清理。此前已清一干净worktree、约461MiB重复依赖及六旧Web，当前引用的配对、故障、金融状态、回退和HPR依赖根保持。

无需用户新增决策。开发者目标保持清除，普通进度留本会话；新增WT框架修改继续先获批准，不研究假设并发缺陷。cash5实际切换和当前故障边界见[本轮交易结果](../releases/2026-11-05-cash5-live-and-event-frontier.md)。实际源码、制品、审查和运行结果见[本轮恢复](../releases/2026-11-05-daily-read-and-minute-recovery.md)及[原统一启停](../releases/2026-11-05-independent-wt-control-and-observer111.md)。[原事实](CURRENT-history-20261104-before-cash3.md)及[更早原件](CURRENT-history-20261104.md)保留历史定位。
