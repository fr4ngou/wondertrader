# QMT未报委托回报兼容与实际恢复

类型：根因回归及部署证据。状态：映射已修并部署；完整自动交易目标继续。日期：2026-11-04。

## 原触发及依据

控制代fa72c6a0的自有Standard在第八笔模拟委托初始回报退出，plugin_error=InvalidInput。冻结30条原始回报后逐条经原金融mapper离线回放，唯一失败为sequence29；与后继sequence30逐字段比较，仅m_nOrderStatus从48变为50，身份、数量、余量、时间和价格均相同。

[迅投内置枚举](https://dict.thinktrader.net/innerApi/enum_constants.html)及本机xtquant/xtconstant.py均声明48为未报。原mapper只准49至57，遗漏正常初始状态。修正共用解码范围为48至57，并将48保留为非终态、保留原剩量；WT粗粒度ABI沿未成交排队承载，原规范事实仍保留状态48。原数量关系、订单/成交身份、时间解析和其他状态保持。

## 验证与固定安装

材料根`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`。MIDDAY-EVENT-REPLAY.json记录原29/30条通过；MIDDAY-UNREPORTED-AFTER.json记录修正后30/30条通过，原回报字节保留，SDK/新订单调用均0。独立MAPPER-UNREPORTED-REVIEW.json无未解决发现。

AccountMapping.cpp SHA为`4a7919ea3da90b850038e1fd3baa989e5f2f6818ac9ca08807e8852e3f5eb3c1`。仅在原固定链接输入中替换该对象，Standard DLL为`dd0632c2464e37240d7c339a49df2d8f8ace53d6b24959cfe31ceaca57c581cd`，Readonly DLL为`503189bc33b8a80dfdcaee14f9207011bea3f17bf01402b0d23ae332fa8a6a76`；其他Native输入及WT框架保持。

原失败进程实际退出后才安装，保留DLL/manifest前件。Readonly新Scan身份沿已审账户发布接线规则接入；原账、基准、命令和Source正文保持。MIDDAY-RECOVERY-INSTALLED/PREPARED/START三份收据记录采用。新代d0618d71，WRI6100、Native50112，service.7；自然策略已重新提交完整目标，原已成交委托未重复提交，后继委托沿原标准执行器推进。

## 页面与未完成

Playwright使用已安装Edge在独立18143验策略、持仓和系统状态三个页面，1440×1000；各页面刷新成功，无控制台错误。CAPITAL-LIVE-UI.json同时核实际业务API，当前runtime_state=ready、status=selling、可用策略预算有值，避免把HTML可打开当作业务恢复。截图及原文位于上述材料根，程序未操作QMT。

Host等待预算候选首版独立审查发现普通/Bulk关闭原claim形状及UTC回拨扩大截止，首版未部署，后继修正继续。实际带挂单停止的StaleSession、最终调仓及买入费用来源仍须核验；全类别每日行情及源码闭包/最终清理另列，未将本轮修正授为完整上线。
