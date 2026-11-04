# 日线unified.9入口修正与自然新日实际运行

类型：实际采用记录。日期：2026-11-04。状态：入口修正已部署，维护owner已自动进入11月4日真实QMT批读；当天新快照发布、覆盖与重启验收继续。

## 采用及根因验证

固定主干41a08380e862382b01053b3d21842f0b8b152478，注释标签guanheng-daily-data/0.2.0a1+unified.9。程序位于`E:/workspace/wondertrader-data/unified-daily-20261104-001/program-natural-day-20261104-015`，164源码成员、183固定输入，SDK0.17.0及原Native文件保持。制品清单SHA为cf2953aa6c17b8493c7e9a21bcabb3b60d46b5268de072acbe742965e02c0b84；完整源码采用与许可文件行尾规范化依据由BUILD-TAG-PARITY022记录。

修正quote_collection_service的bootstrap：独立脚本需要的路径仅在无package入口装配，SMP按包导入helper保留宿主SDK解析。两项入口定向验证通过，Root又使用新安装解释器按实际SMP脚本首次加载顺序核完整SDK、日历及真实时钟目标11月4日，Source调用0。新增验证子进程显式隐藏，新增WT框架修改0。[原失败记录](../incidents/2026-11-04-daily-sdk-shadowing.md)及失败unified.8文件保留。

## 实际运行与业务范围

服务配置为`private-natural-day-20261104-014/service.json`，SHA为8a5db984acd292bd64efaeacd3f6dc78aca32b7c518aa980f4c691b6bdb35893。控制代5ea00e12-2693-4074-a7da-77f919ed7775，WT PID38472、历史及数据owner PID4652；现场已核进程存活及自动登记11月4日任务。原daily.json、任务根、金融WT、QMT Source及独立观衡保持。

辅助公开事实采集曾在Baostock全A日表阶段发生source_request_timeout。原部件及失败回执保留；原重试于13:38:28 UTC取得沪深日表，13:38:30 UTC取得11月4日事实包，北交所收盘与证券身份成功部件沿原件复用。随后原任务进入QMT批读，Root采样已见476个原v8槽且持续updating。该槽数只证明任务进展，不表示476只证券或完整覆盖。

当前正式行情CURRENT仍保留11月3日成功版本；独立观衡18143实际查询300308、588170、上证及399379的5根日线均成功，最后一根为北京时间11月3日。维护新日、旧版本持续可读和新快照完成分别记录。金融WT八组件及当前100万元策略状态保持，本次未新增交易命令。

## 证据、恢复与剩余

完整构建、安装及入口记录位于`E:/workspace/wondertrader-qa/goal-acceptance-20261103-001/unified-wt-entry`的role-build021和natural-day-20261104-001；Root独立记录为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/entry-bootstrap-integration001/INSTALLED-P15-ACCEPTANCE.json`及P15-OBSERVED-CHARTS.json。任务及Source原件归当前owner持有，观察超时不据此重启或重发。

剩余为当天实际发布、各类别真实覆盖及缺项核对、原责任与历史保持、正常重启；分钟Source维护在在途请求交接后统一进行。程序回退沿原服务正常停止与保留程序恢复，原任务、事实包和请求身份继续保留。数据维护对辅助事实源的耦合及旧error_type字段在updating阶段保留的行为记录为维护边界，本轮先完成已恢复的实际主链。
