# 观衡当前市场数据与账户恢复接收

类型：实际开发环境接收。北京时间2026-11-03 00:32复核，观衡仍为a93、入口 http://127.0.0.1:18143/ 。本轮既有总览精简保持，原个人观察未变。

## 市场数据

原市场根已按完整adopt/CAS从9c4a接收全A候选002，当前快照`4c2927b5f4c15f1ec5b5c8090d53bd9d81498780738633379dfe758c05aeea45`，仅新增10个对象。实际5576只沪深北普通A股原件覆盖，六组广度、Breadth Thrust、MSI、RANA、TRIN与高换手占比推进到最新已收盘交易日2026-11-02；另外66个dataset完整记录、所有旧行和原窗口完成记录保持。最初001候选误清了上证背景freshness，Root在接收前发现并停止，改由002保留原记录后接收，未发布001。

已安装App实际目录和六个series API均消费新4c29快照，72组中49组最新行到11月2日。高管六组也已到该日，属于披露回溯、非盘中实时；原独立计划09:00/17:30/21:00保持。年度/季度/月度资料保留实际报告期，T2108等剩余输入继续补齐。全A来源源码的后续归档回归另行登记，本次仅接已核数据，不宣称未发布的来源代码已经上线。

数据HANDOFF-002摘要`91c49f275c0a6208dace35c1645f4d6d51340b7bb5ea4c09a08223010329fdbf`，DATA-CAS-002摘要`c334e47aced2a7ed81dd39652a4cb81068eb7be2ac2b483ee39d50668277db84`；原件位于`E:/workspace/wondertrader-data/ashare-public-20261102-001`。最新全A股票池也已交付v8/T2108接续，未以旧池重标日期。

## 当前账户与策略

开发者2将合法的source_binding_changed未派发终态与读取等待衔接修正后，Root接收实际新控制`49279c21-195d-4933-84e4-6e6422ebe2d0`，实例`a309716d-1288-4328-ac57-abd6ef0bb2e9`，配置SHA256`5713aa4e5dd10260d41d76c2e6157ab2d96fa856a17560c42713b14d7b01939a`。原5周期、100万元基准和5持仓/2委托/1成交保持。

当前实际API策略ready，资产1,000,000.00元、持仓市值366,924.80元，现金余额与可用资金均633,075.20元。账户观察继续更新；五个已登记WT实例均完整读取且ready。此前12i故障事实保留，新实例持续接续的专项复核继续，不以一次恢复替代长期运行资格。

观衡稳定维护定位仍为`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`；当前profile位于`observer-wt-bind-49279c21-195d-4933-84e4-6e6422ebe2d0/web-profile.json`，SHA256`f7a2555b849bead63b991be6406fd86dc041dfa75e775d3ca8ead94f4f892b03`，Web PID5728，控制`64f2aece-90bf-4db8-94c8-03cbe56c40a4`。原a93 Web按原工具正常关闭exit0，新绑定ready后登记当前物理身份，再做业务验真。初次接收脚本普通文件读碰到状态共享冲突，尚未改变Web；改用同一已修复App SDK读取接缝后完成接收。

证据：`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001/ASHARE-ACTUAL-ADOPTED.json`、LATEST-MARKET-ACCOUNT-ACTUAL.json，以及binding-49279c21-195d-4933-84e4-6e6422ebe2d0目录的接收、关闭、ready和业务记录。原RR报价/采集、统一历史18148和独立盘后更新保持；Root本轮没有金融命令或WT框架修改。
