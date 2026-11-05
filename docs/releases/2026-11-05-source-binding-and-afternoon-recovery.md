# 下午来源修正与原账本接续

时间：2026-11-05北京时间14:00。状态：in-progress。接续[午间记录](2026-11-05-cash5-live-and-event-frontier.md)，原记录保留当时故障事实。

## 已定位与采用

原策略已经采用589680，实际QMT正文的委托规则仍含589000。旧通信Journal中的589680委托明确返回symbol_not_allowed、DefinitelyNotCalled。10:50原首错摘要与该原因一致；最终退出的全部触发条件仍未取得完整证据。

修正后的完整正文继续使用原“新建策略文件”载体；仅停止、更新并运行这一行，另外两条行情策略保持。来源规则取当前八标的配置，并以新绑定及独立通信Journal接续；原Journal完整保留。12:52新通道真实认证通过。此次更新没有轮换凭据；凭据进入工具记录的实际事件及剩余处理沿[故障记录](../incidents/2026-11-05-source-body-tool-output.md)。

自有StandardQmtTrader的query_first确定未进入SDK的Insert拒绝，统一沿原逐单失败通知结算，不再污染全实例首错；默认路径、撤单、结果未知和真实硬错保持。源码提交13b40a2、SHA a463b299ead61b3ecb0bee48a4626b1508fa5056272a1164d06b16b7de3f6233；STQ-P34独立delta静态审查complete，实际方法定向正反验证与完整MSVC翻译单元检查通过。build/ef2同批构建25文件、旧项目二进制输入0，部署到稳定native-execution-007；清单SHA404c3766762b5d6d09555523a1a2035208b00d132256e4ca14b981646b010bb0。没有新增WT框架修改。

## 实际接续结果

13:00原515080委托832817087在完整查询中为券商状态54、剩余0，活动订单为空。原撤单终态已确认，没有重发买单。

新绑定先以真实writes_enabled=false实例核账户并正常关闭，再以原权限来源链恢复true；两阶段均沿原financial-state008、100万元含持仓基准和全部金融原件。只读阶段Native49136正常关闭并确认resources_closed/recovery_ready；随后金融WRI1512/Native36016真实ready。该实例行情连接已经关闭，未产生新策略目标。

13:19查明HPR的50885端口无监听。旧Host71140于12:52:12记录ProtocolError并退出，详细报文原因未保留；分析捕获只有PLAN，尚未进入SDK。按原hpr-service001恢复同配对、同Journal，WRI74368/Host56556启动。金融service005按原入口正常停止和接续，原Native36016及八组件全部正常关闭；新WRI64172/Native70992在原账本上启动。

13:24原capture 517f3725取得八标的HPR回执并成功发布第175个窗口；parser_connects=1、parser_closes=0、parser_quotes=16、schedules=1。实际成交查询known=true/error=0，共139条。当前策略waiting_actual_cycle/actual_opening_source_required：行情恢复，持仓开仓来源匹配仍阻断后继目标，正在责任层定位，尚未报告持续自动运行完成。

## 用户入口与余项

18143独立观衡实读300308、588170、上证：分钟均到今天13:24，日线均到11月4日。日线API的UTC日期标签转换到上海为11月4日；当前完整日线发布不包含今天盘中日K。盘中展示与已闭合策略数据的职责需明确，不能把分钟在线视作盘中日K已经接入。

日常快捷方式当前指向operator006/group014，分别管理HPR、采集、报价、日线和交易五服务。观衡继续独立发布。当前没有需要用户新增决策的事项。

私有证据：unified-wt-operator-20261105-001中的SOURCE-BINDING-REAL-VERIFICATION001、SOURCE-PERMISSION-BRIDGE-REAL001/STOP001、SOURCE-TRADING-ACTIVATION001、EVENT-FRONTIER-LIVE-132416，及analysis-source-pending-20261105-001/FACTS.json。进程身份随原入口正常换代，实际运行沿CURRENT核实。

## 开仓与账户修正后的真实自动执行

159780的完整券商成交查询保留原空user_tag；原13笔净买入12000与P相等，开仓为09:36:13的委托832806612。自有helper原先要求非空附属标签，现仅移除此条件，数量链、真实时间和歧义等待保持；新周期ID与已恢复KV相同，三个初始库存周期不变。6项定向回归及原数据实际方法红绿回放通过，独立delta静态审查complete。提交ceee5a7，源码SHA a729e5022d2163b8258d7272f6ff8b7b584d7bb8a5d83eb79c80607a04e76866。

[cash.6闭包](../../apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.9.resonance121.fresh.1.cash.6/README.md)沿原44模块仅采用该helper，V1/QNA及Native保持。固定源码正式重建与seed整包SHA一致，Runtime wheel SHA fb39a6861b85c95787651426a99c352e8241dec48a6da43fe1fe72e6e5105542，装入独立解释器015。旧014环境及旧闭包保留。

13:36 Native17192自然产生8个目标；首笔命令a7afc0c4-b5ac-4b94-8045-efe676e5af88于13:36:59.605准入，510500买100份，券商单832849971，原命令、委托和本代live成交关联一致。13:45已记录34条命令、19笔本代成交，证明目标到实际券商执行。60秒行情轮询的下一次tick可晚于setter，不能用紧邻setter的一次零计数推断执行失败。

账户扫描随后在ORDER批失败，实际Native诊断为“HTTP合约缺失或市场冲突”：旧账户资料含589000、缺589680。在新资料文件仅补入已在Native使用的589680合约，更新原Scan与capital_account配置摘要；账户、环境、原现金锚点及财务状态保持。实际新Scan的P/O/D/A全部通过，返回6项持仓、188项委托、165项成交和唯一资金行。

切换前只读观察存在活动委托832851197、状态50、剩1000。原service006正常停止15.594秒，Native17192确认ok/recovery_ready/resources_closed，再沿原金融文件启动service007。当前WRI40204/Native2428；14:00策略buying/frozen_buy_ready，72次setter，完整成交查询加增量177条、本代新增7笔，账户发布ready且持续成功。页面读取可用资金458031.8元、策略NAV997277.7839元，原100万元基准保持。短暂报价等待已自然推进，未扩大TTL或修改报价逻辑。

## 尚未完备的具体范围

589680的Source规则与账户资料已修正，但模拟柜台仍将其订单置57废单、成交0；QMT错误提示包含SIMULIC、STK_CODE:589680及产品信息不存在。它取得委托号不等于成交；本轮实际成交来自另外四只ETF。该标的兼容和无效重复报单仍需收敛，替代方案沿用户此前自行寻找可用替代的授权继续核查。不能把此状态报告为八证券全部正常运行。

其他余项为全市场来源余缺、盘中日K展示、确认无引用及无未合入成果的最终清理。工作树审计发现多个候选仍含独有修改，本轮未强制删除。14:00 Playwright在18143完成行情、策略、状态页面刷新，控制台错误0、五角色ready、策略资金可读；该结果证明页面接线，不代表柜台已支持589680。证据为ACTUAL-TARGET-ORDER-TRIGGER-001、ACCOUNT-SOURCE-DIAG001、ACCOUNT-REFERENCE-REAL001/ACTIVATION001、CASH6-AFTER-ACCOUNTREF-LIVE001、OBSERVER111-ACCOUNT-REF-UI及QMT-SIMULATOR-589680-REJECTION001。
