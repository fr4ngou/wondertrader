# 证券资料接入、真实撤单与正常关闭接续

类型：模拟账户现场采用记录。日期：2026-11-04。状态：通信升级、正常停止、实际撤单及原账接续已发生；完整自然卖买调仓与全市场数据覆盖继续验收。

## 当前运行

WT采用`0.1.0a12+integrated.2.market.35.3.service.9`，逻辑实例仍为`a309716d-1288-4328-ac57-abd6ef0bb2e9`，控制代`bf53ae7d-d30e-4fe7-ae2b-b64cc9df8bcb`。WRI PID51624，Native PID55092、控制代`9c976d47-1751-477e-871c-c44abb57b290`。账户Host、账户观察、证券资料Host、交易Host、历史与执行器六组件均已就绪，账户查询与真实策略计算继续。

原100万元含持仓基准、金融账根、策略1.1.2和原委托身份保持。Standard DLL仍为`e9a049ed256cc5eea7ebe645a616d0ef266b1ea734c1f6f2f8f917d50169519c`，未增加WT框架修改。启动及停止快捷方式已更新到service.9和本代服务配置。唯一账户/交易通信策略沿原QMT行替换，完整正文SHA为`2446d861a63e2f5f2a7c884ef7d4990535f8ee35b19a8b008bfc987de5e11dfc`；其余行情采集与指标策略保持运行，QMT整机未重启。

账户Host采用已修回复等待及已完成持久化异常核清的专属角色。实际pythonw安装起源不符曾在离线核验中被发现；新配对按真实pythonw重建并经独立实际verify通过，原严格验证器及失败材料保持。

## 正常停止及原挂单

前代713edbdb正常停止，五个原组件PID均已退出。WRI收据`components_closed=true/status=stopped/error_code=null`；Native收据`closed=true/ok=true/recovery_ready=true/exit_code=0/resources_closed=true`。本次实际证据关闭了[前一现场记录](2026-11-04-wt-main-path-repairs-live.md)中正常停止待验项，旧故障原件继续保留。

停止前，券商订单832758806为510050的1000份未成交卖单。WT标准入口沿原单产生第18条撤单命令，Source实际SDK返回且`signal_sent=true`；后继完整券商查询确认原订单状态54（已撤）、成交量0。该结果证明实际撤单，不能用关闭收据替代它。

新代接续同一金融账后再次自然计算，继续发出卖单；已核第19、20、21条分别由券商确认1000份成交。13:24观察中第22条仍为已申报未成交，原查询身份和冻结数量保持。策略处于selling；买入及完整目标到位尚未证明，后续委托状态继续由完整查询更新。

## 资料与页面

证券资料Host由WT原只读组件管理，端口18155。实际QMT通过共享内存返回首个64条证券页及冻结分类：沪股2318、沪ETF995、沪指数270，深股2906、深ETF770、深指数388，北股354、北指数12。北交所ETF组为unsupported，应收数量保持未知；Source原业务时点未知亦保持。组数属于本次SDK名册，证券上市资格、全页成员和日线/分钟覆盖均另验。

开发者2负责唯一完整名册及详情捕获，日线和分钟模块共同消费该固定结果，避免重复目录与Source额度竞争。全类别日线候选已合入正式主干，最终制品与正式数据角色切换由数据模块推进；本记录不声明全市场行情全部到齐。

独立观衡18143通过实际Playwright/Edge刷新策略、持仓和系统状态页面，无前端错误；页面读取当前WT与策略资金，策略selling。WT启停和资料Host均由WT拥有，观衡仅消费发布结果。

## 证据与剩余

固定现场目录为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`。`SOURCE9-UPGRADE-PLAN/PREPARED/START`、`SOURCE9-SOURCE-SWITCH`、`SOURCE9-SHORTCUTS`、`SOURCE9-LIVE-ACCEPTANCE`和`source9-live-acceptance001`保存采用与真实结果；`security-reference-live001/FIRST-PAGE.json`保存原资料页；两项`*-REVIEW002`保存实际pythonw核验。私有配置和账户原件留在现场，不入库。

完整自然调仓、全类别每日数据维护、分钟缺口自动恢复及最终无引用产物清理继续。旧GHWT正文中无消费者的停写交易连接仍会接收回报并产生event_capture_failed日志，已交分钟Source整合候选移除；保持当前采集，实际替换由Root协调。金额浮点尾差保留原值，临界资金判断的完整精度核查仍待完成。整体目标active。
