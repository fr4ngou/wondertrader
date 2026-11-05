# 共振1.2.2同账换代与当前运行

时间：2026-11-05北京时间15:20。状态：in-progress。范围：用户授权选用相近可交易ETF，保留原100万元含持仓基准、financial-state-008及真实周期；仅已确认模拟账户。

## 标的与柜台事实

589680最初被自有Source旧委托规则提前拒绝，该配置已修正。随后真实进入QMT的委托被模拟柜台置57废单、成交0；原界面提示为`SIMULIC, STK_CODE:589680; product information does not exist`。行情目录可查询与柜台委托受理分别取证；现有证据不判断实盘账户受理能力，也未核明模拟产品资料匹配失败的更底层原因。

替代选择博时科创100ETF588030，当前唯一策略版本1.2.2。14:27:57原StandardExecutionHost、WtExecuterMgr及股票执行器真实买入100份，成交价1.403元，券商委托832863347、原命令9e785b00-85c5-46fd-badd-9d5c6afb3865；后续P=100、可卖0、未成交0，原Native与SourceHost正常关闭。新基金自有原价日线从上市日2023-09-15至11月4日共756条，因子及前复权参考回读成功。新八证券窗口经原Reader发布9260行；没有将旧基金价格改名复用。

## 根因与正确实现

1. 显式role_replacement接续同一原账。先验证旧NSQ身份，再退役冻结旧计划，保留七证券周期、退出记忆、资金基准和cash_anchor。新基金100份用完整券商成交与当前P恢复原开启时间06:27:57UTC，沿原现金锚点纳入资金。
2. 原WT保存589680理论目标188600份及关联订阅；它的实际券商持仓为0。沿原code_filters.ignore阻止退役标的继续进入执行，保留原合约、理论账和历史身份。自有Managed报价缓存和ContextAccess理论仓位读取统一投影声明reads，范围外条目不污染当前策略；声明内价格、时点、有限数、容量及setter边界保持。
3. 恢复初始化仅校验配置并取得规范身份。原周期快照时点保持，首次自然回调读取当前P/D并执行完整时钟、行情、历史及NSQ检查，避免拿过期seed与新行情混做决策。record_clean首次启动仍完整校验。
4. 自有Native读取完整RuntimeInput时，原小配置32768节点上限拒绝了3563160字节、151326节点的真实输入。仅此完整输入在原16MiB字节边界内显式按正文长度选择节点预算；其他配置、收据及重复键/UTF8/深度/有限数检查保持。

本轮修改均在自有Guanheng模块，WT框架没有新增差异。最终规则见[角色换代规格](../specs/etf-role-replacement.md)。

## 构建与实际采用

Runtime固定45模块，版本resonance122.fresh.1.cash.2；伴随V1 a10、QNA resonance122.1。永久[源码闭包](../../apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.9.resonance122.fresh.1.cash.2/README.md)普通三包重建与全部载荷、METADATA匹配，Runtime wheel SHA5c59df3c82c0ecb5d0d14d104ccd14ed6663526b8b702c85470faceb95aa9308，安装解释器016。未采用的cash.1闭包移入私有QA存档。

Native先由ef3全源码构建25项，再对已独审的节点预算和自有观察范围增量重编；增量复用ef3库的事实明确保留，未将该两次增量记为全新干净构建。稳定native-execution-007保留切换前备份，安装清单包含旧/新合约及原生过滤器。

初次容量拒绝发生在金融准入之前。第二次已初始化后因范围外旧tick锁存故障；随后以该失败代913c0395的实际新KV进行原fault_reconciled接续，没有回档或重置原账。

当前service008-role/activation004：WRI47180、Native74368、控制代c8fd1607；WT CURRENT控制代72d71919。15:18观衡Playwright实读三页面及刷新，控制台错误0；五角色ready，页面显示策略1.2.2、原100万元基准、总资产100.2102万元、可用现金45.2011万元、588030持仓100份及真实周期。Native已接收30条行情且没有故障；setter及自然schedule仍为0。日常快捷方式已更新operator006/group015及解释器016，观衡继续独立运行18143。

私有证据根：wondertrader-qa/unified-wt-operator-20261105-001/candidate588030-001，包含ACTUAL-CANDIDATE-RESULT、history001/RESULT、NEW-WINDOW、两次源码重建、Native增量、ACTIVATED004、LATEST-LIVE、OPERATOR-ADOPTED及OBSERVER122-UI。独立delta分别核角色换代、恢复seed、节点预算及声明reads投影，均static complete；真实运行范围按本节分别登记。

## 剩余与风险

- 当前策略运行中等待新行情，尚未取得1.2.2首次自然计算及后继目标结果；既有自动交易和本轮100份真实模拟成交证据均保留。
- 八证券AWP此前waiting_source/analysis_source_terminal_failure，15:21:30已沿原重试自动发布11月5日共同基准，9268行，capture7770229f；先前失败原slot及自恢复原因继续只读归档，没有改旧窗口时间或扩大TTL。
- 全市场日线用户入口当前也只读到11月4日；盘中日K、全部来源余缺及确认无引用的最终清理仍未完成。
- 实际凭据诊断输出事件与未轮换状态沿[故障记录](../incidents/2026-11-05-source-body-tool-output.md)保留。
