# WT统一操作入口、观衡独立跟随与11月4日日线发布

类型：实际采用与验证记录。时间：2026-11-05北京时间凌晨。范围：自有运行工具、日线编排及只读实例发现；WT框架无新增修改。

## 实际行为

WT启动、停止入口组合历史补齐、行情采集、报价查询、日线与资料、交易与策略五个独立服务。每个服务继续由原ServiceController持有运行身份、环境和恢复。观衡独立运行，只沿各服务稳定CURRENT读取最近发布状态；服务正常重启后无需手改控制UUID。原生采集算法、DMB/DSB格式、策略算法及通用SDK保持。

操作入口为`E:/workspace/wondertrader-data/wt-service/启动WT.lnk`和`停止WT.lnk`，已从金融服务单独启停改为统一组入口。解释器为runtime-service-20261104-013；工具在wt-control-20261105-001/operator003，组配置为同根group005.json。工具SHA为c0fcc268881b2ea7fe0d5fb66a21dd5ef15c2043b979c27d1fbaf460cdcf4356，组配置SHA为d6d2c5e1a945649eacd5b91ad6da4f20325dde8168892a2583f26565bf3e4391。原两个快捷方式及部署记录已在私有验收根备份。

观衡单独采用0.1.0a111+wtgroup.2，SDK仍为0.17，地址http://127.0.0.1:18143。独立构建收据在unified-wt-operator-20261105-001/observer111-build003；ZIP SHA为513e426b533b1eb202a70923a19c786efb3de5954bf981b64676e9cb29c44712。观衡部署指针仍为observer-current/DEPLOYMENT.json，关闭观衡不会停止WT。

## 根因与修正

1. HPR Host在02:03实际退出，旧采集组合随其停止。原故障仅给出runtime_failed，最早退出原因仍未确认。本次将HPR与实时采集拆成独立运行服务，并采用现有首故障类型/阶段诊断；正常HPR启停实证中，采集和金融进程保持。原QMT正文、配对业务参数、Journal及权限保持，QMT内未采用新正文。
2. 长轮次HPR任务持有旧通信身份；修正仅允许尚无slot的任务在原截止内重新认证。已有slot/未知责任沿原ID。原SDK实际plan处保存并核完整业务metadata，取消后停止重新认证。
3. 股票508批已实读和落盘，但快照仍拒绝跨Host代批次。现在按原capture anchor及read-generations核同一完整业务身份，保留每批实际binding和原件；快照合同不变。
4. 同日修订目录叠加UUID和摘要临时文件，在本机产生277/283字符路径并触发FileNotFoundError。新修订改用同一市场日下原递增revision对应的rNNN目录。旧已登记路径保持；仅本次未提交REQUEST、没有新读取槽的准备根重新登记至r001，旧原件保留。原事实内容摘要和SDK临时文件算法保持。

对应规格：[UDI-R48至R52](../specs/qmt-source-daily-history.md)、[统一服务控制](../specs/wt-service-control.md)。

## 固定安装与运行身份

日线实际程序为minute-adoption-20261104-001/program013，安装清单SHA为1ede98de961995c7048c747f0b4d76155c616d177384e521987f676991faad28。服务为wt-control-20261105-001/daily-service004，service SHA为143ad0dd732a114f7ae43cc478cbe73c90beb7420e950217ea2a47e9976dfa9c。同一原daily配置、INDEX、REQUEST、Native结果及发布目录保持；后继源码声明unified.14与实际固定源程序分别记录，不称为已安装wheel。

统一启停后的核实身份：HPR WRI37208/Host71140；采集WRI53260/collector75932/history35356；报价WRI22688/history71892；日线WRI14724/history49188；金融WRI32360/Native47840。金融控制cbac5320-5b28-4fa8-b776-df884bec522d，逻辑实例不变。实际定位须沿稳定CURRENT，正常启动会换代。

## 真实结果与验证边界

- 原股票HPR5612项、508批回读和941910行原生转换完成，原278批及全部已知结果保持。
- 11月4日正式数据CURRENT已发布：generation 0103ea9e116943b3a19ce54764682943，配置SHA37f8ff29e1d7dc2a408d8f3ad1c26df58e542bb1b827f41ac4917e56fd84a9fd。
- 18143实读300308.SZ和000001.SH，最后日线为2026-11-04；接口UTC零时标签为前日16:00Z，页面按北京时间正确显示。588170.SH样本仍停11月3日，属于继续补齐范围。当前发布价格范围中，11月4日可读股票5571项、ETF1276项、指数618项；范围含历史登记项，不能直接作为全市场完整分母。
- Playwright实际刷新行情、策略、系统状态三页，五服务卡片均可读，无页面运行错误。观衡测试的passed只授页面/投影资格，不代表所有证券当日完整或自动调仓完成。
- 统一组正常停止13.05秒、启动43.03秒；五角色均停止并恢复，观衡进程在该次操作中保持。现金721311.1元、持仓市值278688.9元、净值1000000元连续，3个实际持仓保留。后续观衡仅为切换日线稳定定位独立重启。
- 实际508批/两代metadata回归通过；损坏profile、四项limits缺字段或变更额度明确拒绝；HPR取消后无重新认证/新槽。最终独立delta静态审查complete，运行证据由Root执行。

私有证据根：`E:/workspace/wondertrader-qa/unified-wt-operator-20261105-001`，包括GROUP-NORMAL-RESTART001、DAILY-RECOVERY-REGRESSION002、SHORT-REVISION-ADOPTED001、OBSERVER111-LIVE-UI及原件对照。新日线在同一r001修订继续；短暂RetainedReadPending保持原读取责任，按原间隔接续，不表示已完成剩余覆盖。

## 剩余与回退

1.2.1仍为waiting_market_input，首次自然行情驱动的计算和后继调仓未观察到。既有真实模拟提交、查询、成交、撤单已通过，沿[既有交易证据](2026-11-04-source-reference-and-clean-stop-live.md)复用。全市场ETF/指数余缺、两项分钟指数及北交所分钟范围继续；完整清理尚未结束。

市场观察spread_sw的11月4日原发布行仍为sse_reference=None；普通上证日线已到11月4日，已发布的独立观察快照尚未由原更新owner重新生成。因此第二张图的叠加缺点仍待修复，不能把普通行情接口恢复当成该观察图已恢复。本次两处已结束构建的node_modules清理被自动审批拒绝，工具仅返回blocked by policy，文件保留。

回退时保留原服务组、程序、关闭收据、数据CURRENT和Journal。恢复旧快捷方式只改变操作入口；数据/金融状态沿原恢复协议，不用旧状态覆盖当前事实。不得并行启动已退出的旧owner；先沿原服务正常停止并核实际关闭。原HPR依赖根仍被新环境引用，继续保留。最早HPR异常退出根因尚不具备结论，诊断旁证和职责隔离分别记录。
