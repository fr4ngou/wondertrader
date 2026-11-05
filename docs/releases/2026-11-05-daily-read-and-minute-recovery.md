# 中断日线恢复、指数分钟补齐与观察参考恢复

类型：实际采用与验证记录。核实时间：2026-11-05北京时间09:25。范围：自有日线读取、准备编排、分钟维护调度和独立观察刷新。未新增WT框架修改；金融服务、QMT策略正文及原Journal保持。

## 根因与正确实现

1. 已consumed的纯缓存查询保存了operation_interrupted终态，原SDK持续沿原槽返回未知。SDK提供默认仍选原槽的protected hook；日线owner仅在完整验证原请求/票据/结果、确认为market.market_data及qmt.daily-batch-read.v1后选择.rN后继观察。原请求及成功/未知责任保持，metadata与额度完整核验，绝对截止保持。原22股票实际查询已重现旧阻断并在新owner完成。
2. 旧HPR原件已consumed、明确preparation_not_executed，且无dispatch/result binding，旧规划仍将其当未知而阻止后继。现在仅此完整可证明未派发条件记为not_executed；真正未知继续保护原区间。该次530050旧原件保留，597个新缺口任务全部返回、190批价格回读完成。
3. 分钟维护始终先选到期重试，多个30秒慢请求使重试持续到期，新窗口长期等待。现在两类队列都有任务时轮流选择，只有一类时继续推进；原producer/Reader/Importer和请求身份保持。8ETF及50常用指数中当前采集来源支持的49项优先；SSE.932000缺映射已明确保留缺项。
4. 独立观察快照原生成时尚无11月4日上证数据，普通行情补好不会重算旧快照。沿原source wondertrader.indices及原refresh/collection lease实际刷新，未新增调度或把WT生命周期放回观衡。

规格：[UDI-R53/R54](../specs/qmt-source-daily-history.md)、[分钟维护](../specs/continuous-minute-collection.md)、[ADR0028](../architecture/adr/0028-interrupted-cache-read-observations.md)。

## 实际部署与业务结果

- 日线固定源程序minute-adoption-20261104-001/program016，安装SHA9bc8991aab10b3273d02718a0a9445c72319332700446a012c4003427f7d12e7；daily-service007，WRI28736/history62204，服务SHA6236386575b73355ea7eb320c4a5203ab8eb54f6b70a4571bb60f6a2a2fae3ac。SDK读取hook随独立daily-runtime001固定，原依赖.pth根继续保留。
- r001在04:52完成published，continuation_required=false；CURRENT generation2ca1a1e6ead944fcb179db420cc66497。941910行股票Native结果保持，597项价格准备/190批回读完成，588170、300308及000001.SH在18143实读均到11月4日。
- 当前登记范围目标日可读股票5572、ETF1717、指数642。全量资格仍未成立：价格范围还含历史登记与非价格项；沪/深/BSE指数分别17/55/10项目标不在缓存，ETF尚5项目标不在缓存。股票6项来源停牌数量未知，与不存在补齐程序分别说明。指标预热27项不足、6项stale，不生成伪行情。
- 分钟固定源程序program017，安装SHAaa224c9c1cdc0e62a0cea7985c7fcf1881614b4741e807bee276865808d77be7；data-service003，WRI10380/collector15000/history18760，服务SHA4c562611416e216d96f07d96629b1c9db131e5a84931c31b226339aef84fb38a。上证、深证成指11月3/4日均已各240根reconciled；18143实际读取两指数11月4日15:00分钟。
- 原Reader观察base仍缺240根时，恢复结果由原recovery store提供；maintenance中的native_count=0与recovered_count=240分别保留语义，实际统一查询已读到恢复数据。
- spread_sw的11月4日sse_reference现为3686.172，原spread4.553729451632778保持；真实页面图表、API和截图已核，无运行错误。
- 操作快捷方式采用operator006/group010.json，组SHA7e10b38e57a0ca56aedd27bcd29898324214c608a301243ad5d16deb80c73edf。独立观衡仍0.1.0a111+wtgroup.2、SDK0.17，18143。HPR、报价、金融原运行代保持。

源码声明unified.17覆盖最终分钟调度源码摘要；实际日线program016和分钟program017分别冻结，不将声明版本视为已安装wheel。

## 验证及证据

私有证据根：E:/workspace/wondertrader-qa/unified-wt-operator-20261105-001。

- READ-REOBSERVE-REAL002：原真实22股票、原失败/成功字节保持、2批实际SHM查询完成，无金融命令。
- READ-SLOT-RECOVERY002：原metadata缺失/不一致拒绝，未知/未消费结果保持原槽，后继成功沿原后继恢复。
- test_protected_completion：12项通过，含可证未派发及dispatch证据冲突分支。
- MINUTE-QUEUE-FAIRNESS：原step重现持续重试饥饿；修正后新399001窗口在第二步推进。
- DAILY-MINUTE-PUBLICATION003：正式CURRENT、Native结果、证券计数、真实页面API及两项指数240根恢复。
- INDEX-CONTEXT-REFRESH001、OBSERVATION-SPREAD-RESTORED、observation-spread-restored.png：独立观察真实刷新和渲染。
- 中断读取、未派发识别及队列调度分别经独立delta静态审查complete；真实运行由主会话验真。源码/静态审查/页面读取各自授予对应范围。

## 剩余与回退

最新策略1.2.1、含持仓100万元起点、现金721311.1及3持仓保持，金融Native47840实际存活。既有模拟提交/查询/成交/撤单已通过。09:25仍waiting_market_input，首次自然计算及后继调仓尚待开盘输入，继续沿原实例观察。

剩余包括全范围日线缺口、北交所分钟366项及来源映射、确认无引用的清理。早前HPR02:03退出最早原因未知，当前运行已隔离HPR与采集且保留诊断。清理两处旧构建node_modules曾被自动审批拒绝，只返回blocked by policy，未删除或绕过。

回退采用前一固定service/config与部署索引，正常停止受影响角色后切换；保留原任务、读取槽、Journal、Native数据、旧CURRENT及依赖根。初次分钟候选因932000缺映射启动失败时已正常关闭并恢复旧服务，最终data-service003仅配置实际来源支持的57项优先证券。金融及其他QMT策略保持。
