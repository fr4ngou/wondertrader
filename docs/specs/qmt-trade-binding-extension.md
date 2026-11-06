# 原交易Journal受控绑定扩展

类型：接口规格。状态：accepted / implementation candidate。原职责沿[QST](qmt-shm-trading.md)与原HostTradingJournal。

## TBE-1 唯一owner和版本

旧构造默认保持完整身份严格相等。新增可选Host配置`trade_binding_extension="qmt.trade-binding-extension.v1"`只选择版本化能力，不直接扩大证券。原HostTradingJournal沿同一SQLite、文件owner租约、事务和截止，维护`trade_binding_versions`（完整规范配置、前代SHA、授权及差异）与`trade_binding_current`（唯一当前版本）。原`trade_identity`创世字节、read_operations、56条原command UUID/body/admitted/dispatch/result及事件/读ticket均保留。

扩展后的原库必须以显式能力和当前完整绑定/profile重新打开；旧配置、无显式能力、链/当前指针/原件损坏均拒绝。旧UUID查询沿原body和来源返回，不借新scope重派。私有wire schema仍沿已有`qmt.trade-binding.v1`；版本链单独表达规则的版本，不重标历史命令。

## TBE-2 prepare/adopt

维护者只复用原Journal维护owner，先取得原独占租约。未停止的原owner使租约失败；构造会恢复queued/dispatching或补schema时，维护只读验证在提交前拒绝，不混入本次变更。维护不构造Runtime/运输/SDK。

`prepare_binding_extension(new_binding,authorization_sha256,rule_changes,deadline)`纯核所有身份和原表摘要，返回`qmt.trade-binding-extension-plan.v1`。账户、环境、币种语义、binding_id、strategy_name、全部读/交易/事件预算及存储路径保持。只允许严格新增证券，已有规则除明确授权差异外逐字段保持。新profile唯一变化是其trade_profile.binding_sha256。

`rule_changes`逐证券显式记录before/after和ETF合同证据SHA，只允许原BUY100格/price_tick保持、SELL100格到正整数1格。该静态规则赋予指定ETF整数SELL能力；原Source Kernel不读取P，因此不宣称其单独强制“全部余股退出”。实际可卖/剩余量由原WT股票执行器及ASA核同；未授权的既有588120规则保持。Kernel原能力已支持配置sell_min/sell_step=1，不改SDK调用、WT核心或单元算法。

queued/dispatching在原构造会发生恢复写入，因此维护构造在提交前拒绝。unknown/SDKReturned原状态、UUID、原文和原proof全部保留，允许追加绑定版本；版本追加本身不派发命令，不要求全部历史insert先有券商终态。原unknown准入围栏、Native恢复和同证券pending约束继续原义；原TradeOrderLinks/terminal_insert_observed证明按原版本核验，缺证明保持缺失，不以空查询/SDKReturned推断券商终态。

`adopt_binding_extension(plan,deadline)`在同一原事务核plan SHA、原current版本CAS和完整受保护表摘要，追加版本及唯一current；再次提交同plan只核已采用身份。采用后该维护owner拒绝新交易准入，关闭并用新配置重开。提交晚回按原截止保留未知，后继沿同plan/current核查，不重造命令。

## TBE-3 历史来源和恢复

新命令/新事件只接受当前profile；历史B、事件和原ORDER查询proof仅按显式版本链及已有read_retention前代关系读取。原trade_event_identity与read_retention_identity保持创世原件，新构造核对版本链允许的同一原件，不能拿authentication-only continuity授权scope变化。同一个旧Source session/profile不能伪装新profile；新运行按原认证生命周期建新session。

版本元数据计入原交易逻辑字节预算，无另一个数据库、淘汰或交易额度。prepare/adopt均使用首次固定的绝对monotonic截止；关闭沿原owner，关闭未确认保留原槽。

## TBE-4 验证资格

先证明合成已停止原owner→prepare→adopt→新配置恢复→旧UUID/事件/ticket原字节读取→新增159352准入及整数SELL，再核错误授权/缩scope/改账户预算/旧配置/坏链/CAS变化/未知责任跨版本保持/截止。实际生产Journal和配对材料保持仅读；普通安装、原56命令完整副本演练、权限采用与自然时段委托分别留证。
