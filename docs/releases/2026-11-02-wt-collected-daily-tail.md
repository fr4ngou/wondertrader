# WT收盘日线先行上线

类型：独立WT及观衡连接部署记录。日期：2026-11-02。状态：当天尾部已上线；原生日线持续落盘和多年指数接收继续。

## 用户入口与实际结果

打开 <http://127.0.0.1:18143/market>。观衡仍为`0.1.0a89+runtime.2`，只读行情地址改为独立WT18147，原18146、18142、全市场采集和账户/策略生命周期保持。

300308与588170的日、周、月线实际读取已包含11月2日，默认60根日线、自选名称及五日小图正确。收盘价分别为550和0.617，与各自当天15:00分钟末价一致。旧历史行逐值保持，当前价量额单位沿原unknown声明。桌面与390px页面已核对，移动端无横向溢出，浏览器无脚本或控制台错误。

根因是WT已经输出收盘快照，日线读取分支仍只返回静态导入。修正在WT数据侧消费原Writer输出，通过原Helper/Reader读回，并提供明确的QMT派生批次身份；观衡SDK、UI和App制品均保持。配置包含6982个原采集证券标识，先行实际页面与全字段验收覆盖上述两个证券。模块与资格沿[WT闭合日线读取](../modules/collected-daily-history.md)。

## 当前部署与维护

WT元数据：`E:/workspace/wondertrader-data/wt-daily-tail-20261102-001/DEPLOYMENT.json`。运行PID37284，监督者39636，control=`3fd94539-edc3-44f0-94b6-92288fc91f0c`，instance=`ed572437-308f-4dbe-b82c-26004af94428`，配置SHA256=`bfababb5eec3d7745d9c091b4df590ca104cdd7be2080b38d05b692ff536296a`。本实例只有history组件。运行记录同时保留实际pythonw路径及摘要，监督者PID与运行PID分别表达。

原SourceMarketProcess及WRI停止/启动协议沿[历史服务手册](../runbooks/source-market-app.md)和[独立WT手册](../runbooks/wt-independent-runtime.md)。正常停止须核本代control、instance、配置摘要，写原stop消息，等待closed及原owner退出；重启使用新控制目录和UUID，并登记新状态定位。私有环境只在专用启动进程载入，不输出正文。本轮已启动并实际读取，未再次停止此现场WT；相同组件的隔离HTTP及原Reader关闭已通过。

观衡稳定维护入口仍为`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`，沿[a89维护命令](2026-11-02-observer-a89-runtime.md)。新实体profile是`E:/workspace/wondertrader-data/observer-controlled-web-20261102-a89-daily-001/web-profile.json`，SHA256=`5daab82131a1774cda5ad34decaaf9078fc5b17f204811e6549d869e87030775`，Web PID74576。旧Web及启动器均正常退出0。原个人观察目录及两只自选保持，账户原5持仓/2委托/1成交及资金基准保持；账户/策略恢复继续由其owner处理。

回退历史连接时，用当前观衡工具及profile正常停止Web，确认关闭后，沿同版a89工具启动前代实体profile`E:/workspace/wondertrader-data/observer-controlled-web-20261102-a89-runtime-001/web-profile.json`，即可恢复原18146连接。验真后再更新稳定维护入口。原WT18146保持运行，回退不要求重启采集或QMT；本轮未执行回退。

## 源码与证据

- 源码`369d070`，限定7文件；旧文件与CAS002基线逐项匹配后复制，候选与运行组件逐字节相同。WT核心及Native ABI改动为0。
- 组件：`E:/workspace/wondertrader-data/wt-daily-tail-20261102-001/market-component`；安装清单SHA256=`74e30c0065f07f799214f37b9121eae52a994b314b4dcb78312257619f49b978`；源码CAS摘要=`97021e5f060441970397e3020f434896e6a50c6ad69c5cdf81c4f67a69090af6`。
- 组件交接：同根`HANDOFF-001.json`与`PREPARED.json`；审查及字段对照在`E:/workspace/wondertrader-qa/index-history-continuation-20261102-001`的CAS002、HTTP002、两份delta审查及原快照原生回读材料。
- 实际部署：`E:/workspace/wondertrader-qa/root-daily-tail-deploy-20261102-001`中的`READY.json`、`A89-CONSUMED.json`、`DEPLOYED.json`、`DEPLOYMENT-CURRENT.json`、`PAGE-VERIFIED.json`及`DAILY-MINUTE-CLOSE.json`。

收尾脚本首次使用无tzdata的工具解释器，启动成功后的日期核验中断；改用已安装App解释器在同一运行实例完成核验及稳定入口更新，未重新启动服务。原启动记录的PID为监督者，后继当前部署记录已分别登记运行PID和监督者PID。

本次先行不代表完整50指数商店已上线，也不代表长期日线保留链已完成。最近64份快照读取与静态base之间的持续归档问题继续收口，优先复用WT原生日线输出；不新增定时下载服务。未操作QMT、下单或撤单。
