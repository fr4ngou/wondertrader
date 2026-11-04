# 买入阶段账户资料与迟到回报故障

类型：现场故障与后继诊断。日期：2026-11-04。状态：账户真实恢复、迟到回报修正已采用；后继启动遇事件页处理超时，金融实例当前故障停止。

## 发生与业务结果

service.9控制代bf53ae7d完成510050卖出并自然进入buying；515080两笔各1000份买入由券商确认成交，价格分别1.592及1.591。512100、510500各1000份仍已报。589000四笔买入均被柜台拒绝，QMT界面原文“[证券产品]信息不存在”，原回报保留STKBD:10/STK_CODE:589000；SDK返回和券商成交分别核查。保持原策略标的与未完成目标。

13:37账户发布失败，13:38 Native55092报告plugin_error9（SubmissionUnknown）、host_fault3、session_fault4后退出；WRI关闭组件。失败收据与recovery_ready=false保持原件，金融状态未清空。

## 账户根因与真实恢复

账户扫描使用初始五合约资料，新增589000委托虽由Source完整返回，映射因BaseDataMgr缺合约而拒绝整批。同一真实结果按实际配置复现“HTTP合约缺失或市场冲突”；保留原定义并补齐当前策略资料后整批通过。

Root以原扫描器和原账户Host执行只读恢复，14:02:20取得5持仓、44委托、37成交、1资金，随后正常停止。实际515080持仓67200、可卖65200；510050与510300均0。47条原通信命令经此完整查询核对无未确认提交遗留，挂单保持原身份；9、16条仍明确未进入SDK。恢复金融请求0，交易CURRENT及原账未变。账户装配需与当前策略资料保持同版，避免依赖初始库存的静态清单。

## Native独立触发

实际红例为：Standard先应用Source3253的完整44行委托查询，再交付85至102的较早活动回报，remember在85产生相同code9及空reason。较新查询已知终态，较早活动观察被错误当作提交责任未知。候选保持终态责任不回退；原Adapter表、执行器和完整事件交付继续核实，未修改WT框架。账户恢复不授Native故障已关闭。

后继修正已合入9eef0a6，生产同批DLL摘要5671a3e2前缀。两组实际44行查询加原活动事件回放中，旧终态订单保持不在活动表，原活动表3→3、余量1000→1000；新增下撤单、资金通知及执行器重算均0，原事件序列推进至102。独立源码审查无发现。

14:33第一次恢复在trade_host原15秒启动校验预算耗尽，Native未启动，金融文件逐字节保持；仅扩大进程启动预算后，8709fe25运行代的账户Host和真实扫描恢复。其后Native d1a4f241在14:36:36的reconcile_orders阶段报告plugin_error5，原因定位为qmt_standard_event_chain_deadline，原8秒事件页链的实际触发继续诊断。该Native未发布ready，WRI随后关闭组件，当前自动交易仍未恢复。

这次实际恢复已沿原身份撤销832770246、832770247：通信48/49均SDK进入且signal_sent=true，14:36:32完整券商查询分别为状态54、成交0。原49命令核查无未确认提交遗留；9/16仍未进入SDK。失败收据、原基准和原金融账保留，委托不重复提交。新增证据为BUY-OBSERVATION-NATIVE、BUY-OBSERVATION-RECOVERY-PREPARED/START及002、ORIGINAL-ORDER-AUDIT；正常关闭资格保持按原收据判定。

## 数据与剩余

资料Host原先随金融WRI关闭，现由既有WT只读组件独立托管，wt-reference-service-20261104-002：WRI54936/Host20720/18155，认证metadata已恢复。金融CURRENT保持故障代。数据owner已取得8013证券完整名册及详情：32页、126详情批，缺详情0；北交所ETF和Source业务时点未知保持。名册不授行情覆盖。

统一日线.4独立运行18136，旧名单7870发布及八证券两口径实际回读已核；动态名册采用继续。观衡三个类别日线样本到11月3日，公开分钟仍停昨日DSB，今日标准Reader已有数据，该接线由分钟模块修正。

证据根为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`：ACCOUNT-INSTRUMENT-RECOVERY-LIVE/OBSERVATION、ORIGINAL-ORDER-AUDIT、mapping-source-failure-candidate001、query-event-observation-candidate001、REFERENCE-OWNER-START002/METADATA002及MARKET-LIVE-ACCEPTANCE。Source Journal和失败收据保持；私有原件不入库。

继续交易适配修复、原账恢复、全市场行情与最终清理。589000当前模拟柜台拒绝为独立执行限制，证券存在、行情可读与该柜台可成交分别表达。整体目标active。
