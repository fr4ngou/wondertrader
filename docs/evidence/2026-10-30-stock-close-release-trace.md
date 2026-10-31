# 股票执行单元关闭异常的同次释放链

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B实际故障证据。状态：触发位置及原工厂最小红例已确认，修复未实施。范围为固定唯一1.1.2实时安装的rt-main002关闭c0005，WT潜在线程研究保持停止；本轮没有真实下撤单或生产切换。

## 实际故障与证据层次

原`build/ms-retained-backtest-001/rt-main-002`在四笔SDK替身买入、四周期及converged之后关闭失败，原生运行根exit2、外层wrapper exit1。原debugger附加/退出/join和外层Job/管道回收分别成立。异常为执行访问0xc0000005，指令地址位于已加载模块之外。旧业务成功、关闭失败和实际回收分别保留。

本轮只读取该次已保存的转储：TID75412的原CONTEXT及MemoryList、原模块PE函数表。StackWalk64通过只读回调展开42帧，missing_reads=0。最顶层无函数表，进入下一帧依赖无表leaf返回地址处理；直接返回地址位于原`WtExeFact.dll+0x1baff`，前一条指令是商品成员的`call [rax+8]`。其余帧的PC落在各自提供的RUNTIME_FUNCTION范围内。最近导出符号仅作邻近标签，未当成真实函数名。

原COFF函数节与同次PE函数范围匹配，逐字节比较仅屏蔽声明的重定位槽；关键链为：

`gh_cta_run → run_process → CtaExecutionSession::close → StandardExecutionHost::close → BrokerQueryLocalExecuter/原WtLocalExecuter析构 → 原ExeUnitWrapper/工厂deleteExeUnit → 原WtStockMinImpactExeUnit析构 → 商品对象release虚调用失效`。

其中股票析构354字节比较306个非重定位字节；自有close、原Local析构等关键函数也有完整函数节匹配。frame4保持未命名，frame5保留ICF等价容器模板的歧义，重定位目标没有被该匹配器独立证明。

同次原执行单元的`rdi+0xd0`成员等于异常rcx，商品首指针等于异常rax且不在任何模块中；调用目标指针所在页未被转储收集。此证据定位失效商品虚调用。正式进程中的首次释放者及完整引用计数历史仍缺失，不能把所有历史退出失败归到同一原因。

## 原工厂最小红例

`stock_commodity_close.cpp`复用既有诊断Context，加载同一原工厂；只有两个股票单元和一个借用商品对象，没有行情、业务策略、SDK或观察retain。实际运行得到：

| 步骤 | 实际引用数或结果 | 正确配对要求 |
|---|---|---|
| 创建商品 | 1 | 基础资料owner持有1 |
| 初始化单元A | 1 | A长期持有后为2 |
| 初始化单元B | 1 | B长期持有后为3 |
| 删除A | 原工厂调用返回 | 仍应保留owner+B |
| 删除B | c0005，返回地址同为`WtExeFact+0x1baff` | 正常释放B长期引用 |

原初始化已有缓存retain；get_minOrderQty的第二次临时getter结束时又release，抵消缓存的长期持有。旧单单元带观察引用的2→2→1实验及本轮无观察引用的1→1→1/第二次析构异常共同证明这个固定工厂的引用配对缺陷。正式现场的失效虚调用与该最小红例位于同一原释放指令；正式同次首次释放过程仍按上述范围保留未知。

最小进程实际exit3221225477，第一单元删除完成、第二单元未返回；debugger正常detach/join，原native Job树清零、EOF、读线程join及句柄关闭。两次异常事件分别为第一机会与第二机会，同一进程，没有按两次运行统计。

## 身份与独立审查

- 固定Factory SHA `8e0721f3c2d54621468a02fa6cf3a63640f7ec9218e7a2116bcfe8af5860a131`；正式Runtime SHA `68d7c415837556ff7c3e2d180250dfb1e98c4d3051a0fd4133a9e4f5a3f1d86f`，从dump实际ModuleList路径核完整SHA并与R23 BUILD比对。
- 正式dump SHA `f1733253d6e8eb1b84dd89d5fc64ab8220d7d9905a1f8200db9413d3ef6bd938`；转储保持原受控目录，公共包不包含原始内存或完整RT配置/POSTFLIGHT。
- 原件根`build/ms-retained-close-trace-002`包含STACK、OBJECT-MATCH-002、SAME-SITE-001、MINIMAL-STACK-001及OUTER-CLOSE；最小运行在`build/ms-stock-close-minimal-001`。所有新增源码/工具/日志/符号目录在E盘。
- 独立REVIEW-001（外部历史/待归仓路径：`../../build/ms-retained-close-trace-002/REVIEW-001.json`） SHA `072c98dc63c4cfde5a12a31be09966e3c721f1053a03cac943b35989763bcd3c`，44项身份绑定、0漂移，无新增阻断P1/P2；限定支持上述释放链和独立机制复现，保持正式首次释放历史缺口。

首版walker使用DbgHelp默认函数表仅得到3帧，保持未充分展开；后继提供原PE函数表后取得42帧。首次COFF匹配器反复计算整个对象摘要/扫描符号表，已明确终止该自有离线进程并按对象缓存摘要/按节索引重跑；没有重启业务实例或替换故障输入。两项工具前件分别保留在trace001和OBJECT-ATTEMPT-001。

## 修复边界与下一步

[最小引用方案](../migration/native-stock-metadata-ownership-proposal.md)继续proposal-only：三WT文件提供显式工厂别名，在原类中保持临时借用引用；两份自有装配验证能力及名称。最新可审阅差异在`build/ms-stock-reference-proposal-003`，按当前R23原生23文件及NBC六wheel/15模块重新绑定；旧name继续原路径。生产源码、工厂和候选编译均为0修改/0次，等待所需的明确框架实施批准。

003提案独审REVIEW-001 SHA `6cfb8f7e9c85845bdd910bbbc0c0b81d1ee1513fed4a77282599a15b3c811d72`，构建基线P2已关闭，开放P1/P2为0。开发诊断包、源码及全部回执SHA由trace002的DELIVERY-001.json、PACKAGE-MANIFEST-001.json和FINAL-POSTFLIGHT-001.json登记；原始内存、真实账户材料与凭证保持受控，不进入公共包。

实施后须以新别名通过引用配对、最小关闭、正式唯一策略关闭及同根两代恢复，继续资金/T+1/费用和完整BT/RT主链。当前实时关闭与完整模块资格仍未通过；核心默认行为及原账本、持仓、成本和绩效继续复用。
