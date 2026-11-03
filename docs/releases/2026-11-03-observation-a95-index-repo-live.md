# 指数背景与回购来源a95实际接收

类型：本机独立更新角色部署。2026-11-03 10:10复核。用户Web保持`0.1.0a93+status.1`和 http://127.0.0.1:18143/ ；独立市场更新已运行`0.1.0a95+sources.1`，WT/QMT生命周期保持各自所有者。本轮没有金融命令或框架修改。

## 根因与统一实现

指数来源按其配置声明的源表/指标归属读写，解决`market.sh000001`同名源表被只读投影误认后拒绝更新的问题。中证全指背景按实际消费的日期/收盘接纳，保留原官方close-only日期及谱系，七张OHLC/量表继续原完整覆盖要求。回购定盘沿官网公开POST表单替换原GET403，复用已有Fetcher和全部预算。细节沿[指数模块](../modules/observation-index-background.md)及[回购根因证据](../evidence/2026-11-03-repo-fixing-query.md)。

最终代码已合入干净主干`a6592d0`。App与SDK版本、数据配置分别固定，未将任何活动WT差异带入构建；既有1项参考夹具缺少CSI300定义的失败保留。干净主干文档检查通过，TypeScript/Vite及分包检查通过。

## 数据与实际安装主链

Root按固定最终交付`119d891315b95b4de6aa49f84e66d62f0a4a98a5df6b168c3802e7429d3633bc`完整核验Source/Data CAS及原验证记录，沿原adopt/CAS从d011接收`5a94e1ea15f7eabce05419e94f11d665d723cdd1431a4ed651413de8b116d79b`，仅复制6个新对象。72组、全部原历史日期、方法版本、股票PB分区及原窗口记录保持；允许的数值变化为回购真实值和债券中证全指参考。中证全指219条实际接口价格保留其三位小数，2018-06-18原官方4380.58收盘保持，无补造OHLC。

新安装原refresh实际选择本次两路来源，10:08:18至10:08:40耗时21.69秒，两路均success，发布`fe80362aa6bcd1e2a6f3eccf53f845837d6c7e4e61d1b3e1ddb02f6ef9051c9c`。指数来源20099条表观察、尾日11月2日，回执明确保留上述close-only日期；回购来源6条本次增量，当前完整28条、区间2026-09-18至11月2日，末FR007=1.38%、FDR007=1.36%。首次启动期间的一次手动刷新遇到采集租约占用，返回another_owner_running且无请求/发布，原结果保留；确认新调度已waiting后才重新执行。

普通wheel隔离验证18个背景消费页的series和导出逐值一致。当前a93真实浏览器1440×1000已核回购与独立日频PB：回购两曲线、PB与上证参考线及末日11月2日实际显示，控制台/框架错误0；报告页400条记录的实际验收沿[此前记录](2026-11-03-observation-a94-shared-update.md)。本轮未改前端样式或授新移动端资格。

## 制品与运行定位

- ZIP SHA256 `bd338b7dd143d345e1510f8d84dfc429d70142be85e253abc6bbff9e28aefb46`；制品清单`e5cf1796088a6fb66a9aa9cea66b995d0d7c63b633452e6821b5923e4ff55fb6`。
- 角色清单`bf0cc3e87ad68daa1daa048503635656f1c9a7e07e591d4f11f809dc86cd22d6`；安装收据`8ac321aed7f2a2be6cd2ef18fa193d07915eb6e5471f98fa484b0c57a1d5cb5f`。
- 来源配置保持原27路、SHA256 `dc79564526c226179e08ccdb10215a1b50c72d8843afc3fa80b6652751239fcc`及09:00/17:30/21:00计划。新部署SHA256 `31bdad56823569bd8c3e20b2f7dc4fbfd81e060a1361c9074904e35ab06b54b6`。
- 更新稳定定位`E:/workspace/wondertrader-data/observer-current/UPDATE-DEPLOYMENT.json`；控制`c224b589-7470-425d-8ab9-77716f6ef2e3`，监督PID63268，启动器51332。10:10按原创建时间核父子存活、心跳推进、调度waiting及fe80。
- 维护目录`C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observation-update/a95-indices-20261103-001`；解释器取稳定定位中的python，执行controller的status/stop/start，沿[市场观察维护手册](../runbooks/market-observation.md)。Web的DEPLOYMENT独立保留，个人观察未改。

旧a94正常关闭、退出0、父子实际退出且原停止截止满足后才启动a95。旧定位及全部回执保留。回退先正常关闭a95，再按同一控制入口启动原a94，实际新控制身份重新登记；数据根、窗口、历史和内容对象保持。a94会恢复本次旧GET及指数拒绝行为，页面读取仍兼容，回退范围应明确接受。

原件位于`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`：INDEX-REPO-ACTUAL-ADOPTED、A95-ACTUAL-CHANGED-REFRESH、A95-CHANGED-REFRESH-NOT-STARTED、两代stop/start/status、a95-actual-browser/RESULT及截图。来源交付及完整Source/Data CAS位于`E:/workspace/wondertrader-data/observation-indices-20261103-001`；Root首次读到仍在冻结中的旧handoff摘要时准入即停止，未写现场，改核最终交付后才接收。

## 剩余主路径

T2108仍待全池实际前复权回读与最新日资格，原MDP已完成缓存优先候选，旧349条准备责任保留。v7/v8端口恢复后仍握手未就绪；原采集父子存活、无溢出，但Source断开、最近接收停在09:30:05，不能用其ready或当前心跳宣称行情持续推进。执行侧已定位QMT图表“一目均衡表”全历史重算持有GIL，临时停用确认及源回调恢复由开发者2处理。账户旧实例故障、当前可用资金为空，新的恢复身份尚未接收。

持续原生日线/50指数的配置候选已合入，现场完整GH配对、维护切换及自然开市收盘尚待统一接收。年度/月度等资料仍显示实际报告期，原月频PB与独立日频PB保持口径区分。本次两路成功范围明确，完整27来源的自然后继窗口继续由原调度实际执行。
