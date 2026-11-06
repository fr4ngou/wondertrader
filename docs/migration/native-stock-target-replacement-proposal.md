# 已达持仓时替换旧执行目标

类型：框架修改审批方案。状态：accepted / implementation-in-progress。2026-11-06用户明确回复“批准”，按下述两框架文件及配置选择范围实施；正式部署与业务恢复分别登记。依据：2026-11-06真实模拟运行及当前公开工厂DLL回放。

## 大白话说明

策略今天要求159780保持22000份、512100保持76200份，只卖515080的100份。原股票执行器此前保存了更高的旧目标。它收到新目标后发现“目前可卖持仓已经等于新目标”，就直接返回，留下了旧目标；下一笔行情到来时，它继续朝旧目标买入。

当前实际DLL重放与真实成交相同：159780额外买入两次、合计2000份，512100额外买入200份，515080卖出100份。券商原始查询在09:38前确为22000/76200，之后为24000/76400；WT最后读取值与券商一致，数量没有在展示层重复相加。

修正目的：收到新绝对目标时，先接纳这个目标，再由原数量和委托算法判断是否需要交易。原目标和实际账户数量仍各自保存，已发生额外买入保持真实记录。

## 修改范围和配置

- 框架文件：`config/native-reader-overlays/runtime/src/WtExeFact/WtStockMinImpactExeUnit.h`和同目录`.cpp`。只新增缺省false的`replace_equal_position_target`，显式true时避免“持仓相等就丢弃新目标”的提前返回。
- 自有接线：`src/GuanhengExecution/StandardExecutionHost.cpp`校验这个可选值必须为布尔；Python恢复和Native恢复的深拷贝比较投影仅归一化本开关，原金融身份和实际执行配置保持。
- 配置入口：`executer.policy.*.replace_equal_position_target`。缺省/false保留原路径；正式候选显式true。既有Borrowed元数据引用、原订单和未知身份保持。
- 两个框架文件与既有CORE-011合成维护在同一覆盖，构建清单绑定最终SHA；审批时差异保留为[原建议差异](native-stock-target-replacement-proposal.diff)，当前实现及验收以本正文和源码为准。

## 已有证据与验收

当前实际WtExeFact.dll的SHA256为ba7872a6b0a7bc4b3845aa1ef7b33354f36c91333e6e4872a3056c7288dc18cb，与重放加载的DLL相同。七组公开工厂回放覆盖上述三证券、连续两次买入、全新单元、已有在途余量及总量/可卖分离；原行为均按实物复现。自有NSQ正确阻断额外数量，185条历史成交未计入当日变动。

隔离同批构建已通过：显式true的三证券为0额外买入、0额外买入、原SELL100；缺省/false逐项复现原路径。两工厂三模式42组公开工厂回放、Host坏型准入及Python同账比较见[实际证据](../evidence/2026-11-06-stock-target-replacement.md)。保留活动委托与未知恢复责任，独立审查、普通安装和真实接续分别核验。

现行日志缺少原执行器历史文本，无法逐项还原当时owner队列顺序；源码、实际DLL因果反例、已发目标、原始P和成交数量相互吻合。新日志接线后需核目标、持仓和实际委托。修正不会自动处置已发生额外买入，不自动卖回、改账或重置状态。

真实原件位于E:/workspace/wondertrader-qa/natural-execution-divergence-20261106-001：BROKER-POSITION-ORIGINALS、BEFORE-STRATEGIES及NATIVE-OUTPUTS。原DLL重放材料由`.tmp/EXECUTION-DIVERGENCE-SHAS.json`绑定；该材料在合入和清理前固定归档。需要用户批准的原因是既有约定：新增WT框架行为先解释并获批准，配置保留原路径。
