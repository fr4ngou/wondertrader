# 标准TraderQMT候选查询、生命周期与共享内存正向交易

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-24。范围：[STQ-P9](../specs/native-qmt-standard-trader.md#stq-p9-标准插件接线与实施状态)候选的标准接口、查询/回调生命周期和正向写整链。状态：上述隔离切片通过；完整P9故障矩阵、实时事件、交接/恢复、生产Factory及发行未完成。整体目标active。

## 实现

[StandardQmtTrader](../../src/TraderQMT/StandardQmtTrader.h)提供标准ITraderApi、单I/O worker、创建线程owner pump和P8账户三阶段；[StandardFactory](../../src/TraderQMT/StandardFactory.cpp)提供真实候选create/delete与五个生命周期导出。实际测试将该DLL作为TraderQMT加载，不静态链接另一份插件registry。

业务入口只复制有限值，网络客户端留worker，WT对象和SPI留owner。首次pump在原TraderAdapter.run返回之后；回调前释放完成任务名额和必要状态，自有锁外通知SPI，有效载荷在回调结束前继续计费。首次close D冻结，真实drain/join后才删除。

原WT EntrustID/UserTag沿样运输，worker自动生成内部UUID并在一次POST前保存原receipt。撤单用真实券商OrderID及原关联恢复，不给WT撤单对象增加UserTag，也不新增逐单签名/资格等级/原子四查询前置。当前生产[Factory.cpp](../../src/TraderQMT/Factory.cpp)仍创建旧ManagedTrader，未切换。

## 固定构建与运行

固定上游为08b230dd05facf6d650d949bfe51054115a2ecb1。新构建入口（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/build.py`）的--standard模式从原Git blob创建独立上游快照，复用现MSVC/Ninja/锁定依赖与原WTSTools/WTSUtils/TraderAdapter对象；自有候选另冻结。没有编译当前工作树的未批准框架差异，没有新增WT核心修改。

最终fixed005构建（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fixed-005/result.json`）通过。最终运行（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-003/result.json`）11方法、12场景通过；标准接口日志（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-003/standard-tests.log`）10方法2.766秒，真实SHM日志（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-003/standard-shm-tests.log`）1方法2.291秒。两个输入分别见本次owned/input.json与测试FIXTURE-SOURCES.json，后者无漂移。

| 实际覆盖 | 结果 |
|---|---|
| 真实原TraderAdapter.init/module加载→run返回→pump | 原登录和position/order/deal/account四查询推进，持仓100、资金137.25/19.5及原状态断言通过 |
| 直接标准Factory/SPI与业务线程入队 | HTTP在worker，SPI/金融对象在owner，独立四查询回调各1次 |
| detach、回调内stop/release、迟到HTTP | 已ready结果被撤销注册后抑制；回调内不自join；原D后不发布查询数组 |
| max_response_bytes容量边界 | 16MiB在init准入；16MiB+1和32MiB在init当场拒绝，worker/HTTP均0 |
| 净仓卖单确定未调用 | 原net/buy/direction/offset/type/price/volume/代码及原ID/tag完整回传，拒单回调恰1，SDK0 |
| max_queue=1真实原Adapter | 原登录及整段四查询均通过；没有为回调额外占新名额 |
| prepare第三次trade-status真实503 | 第一次未POST委托拒单SPI中看到writes_blocked已真，新委托同步负返，trade POST始终0 |
| 真共享内存正向写 | 见下节，真实运输到原源线程替身insert/query/cancel及完整关闭 |

## 正向交易整链的准确范围

Standard候选DLL→真实TCP/HMAC Host→Win32 builtin共享内存→RestrictedTradingAgent原线程SDK替身。原SDK调用替身insert/cancel各1次，HTTP写POST恰2条不同原UUID；各自结果仅GET原ID。一次真实Account2订单查询经过Core/P8 lookup，恢复原EntrustID/UserTag与broker.1，随后标准orderAction使用该券商号撤单。

源端产生3条原事件，Host持久/R21关联及源ACK连续到3；SDK替身线程与source原线程相同。source handoff、I/O、worker、Host、HTTP server及原生API均实际关闭/退出；SDK真实调用0。十二场景的根逐项断言（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-final-001/CASES.json`）确认无强制退出，tree/管道/线程/资源证据见控制器（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-final-001/CONTROLLERS.json`）。

这里的3条ACK表示源事件已交Host保存。当前插件event_consumption_complete仍为0，测试没有将它们交给onPushOrder/onPushTrade；不能据此宣称WT已应用实时成交。正向写使用直接标准SPI；真实Adapter加载用例验证查询链，尚未将全部策略/执行单元的实盘写链合并授予资格。

## 根因修正与独审

四项P2在自有适配层修复：配置上限沿唯一HTTP owner统一为16MiB；保留净仓委托属性；终结任务在SPI前归还名额而有效载荷仍计费；需要阻断的新写状态在SPI前生效。Query→Resolve继续转移同一任务名额，普通明确业务拒绝仍保留原继续交易语义。

单槽问题取得旧候选原红灯（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-queue-red-001/result.json`）：仅从16改成1，原Adapter在prepare之后四查询0直至原D，清理正常；最终同场景已绿。首次编译的导出属性不一致及测试const容器访问也在自有声明/测试边界修正，失败原件保留。

独立full静态报告（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-review-001/NOTES.md`）当前P1/P2为0，Reviewer执行0；根对52当前来源及5固定原版来源（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-final-001/REVIEW-ROOT-CHECK.json`）核同，无漂移。构建、实际运行和独立静态审查分别证明各自范围。

## 剩余范围

标准插件层丢提交回复、SDKentered未知、全部关闭/父死亡/容量异常矩阵仍待补，不能只用原底层TradeClient故障通过替代。实时事件到SPI、SDK重复抑制、查询/迟到成交交接、同实例重连及跨进程恢复继续开发；[后继事件提案](../specs/native-qmt-standard-events.md)为proposed，未实施。

生产Factory切换、同版独立安装/搬迁、真实SDK非空委托成交字段与授权实盘、全部保留策略和观衡入口/发行分别待验。终端旧HTTP未使用；旧QMT工程只静态参考，未运行或修改。本轮没有新增需要用户先解决的外部阻塞。
