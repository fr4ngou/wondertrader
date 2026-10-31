# 标准 TraderQMT 完整字段事件消费者

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证证据。日期：2026-10-24。状态：SEV-R4a/R11隔离稳定流切片已验证；整体迁入目标active。

## 实现与职责

自有C++ StandardQmtTrader沿真实读取上下文、唯一worker取页、owner逐项金融begin、同worker身份resolve、owner finish与原WT SPI交付完整order/deal。有限EventDeliveryIndex只保存运输/金融交付身份和处置，不建立第二份持仓或资金账本。长寿命索引、上下文、临时页链及普通任务均从同一max_queue_bytes划分；SPI在自有锁外执行。普通配置缺少两项事件资源时继续原查询路径。规格见[SEV-R4a/R11](../specs/native-qmt-standard-events.md)，模块行为见[TraderQMT](../../src/TraderQMT/README.md)。

正常整页和空页在本次完成转换中释放临时额度并启动轮询间隔。错误通知只包含类别、序号及派生摘要，原payload留在原通信事实。正常解绑后的成功Query/Resolve明确抑制并按owner退役候选，完成值先析构再归额度；真实HTTP失败、缺结果与原D失败保留原事实。

## 实际验证与精确输入

固定原版WT为08b230dd05facf6d650d949bfe51054115a2ecb1；Adapter取原Git blob，当前工作树框架差异没有进入本次验证。最终产品Standard.cpp为abaed6c0090faa228128e3475d33f4017083d2ce8b4ab8bfa9fcfe8517468ac3。实际使用同一个fixed015候选DLL，SHA为942210e0f93934d150c3a96319f891ac9e884cf03a268f70968735de69da4713。

| 范围 | 已取得的证据 |
| --- | --- |
| 原查询、标准接口、写替身与关闭链 | 最终DLL的15方法/16场景通过；含3个真实Win32 SHM/Host正向及未知场景，SDK为替身 |
| 完整事件到真实WT Adapter | 19个不同场景已取得通过证据；已知非空持仓100后新增20最终120，可用量仍100；重复成交、重复取消及旧订单抑制 |
| 调度及异常 | 非空分页、空页间隔、单槽账户查询重入、gap先阻写且保持读、来源变代、缺/非法字段、原D、stop/detach、页末跨D及错误日志摘要 |
| 解绑 | Query及Resolve两阶段实际完成；候选/名额/预算回收和单槽再用；成功查询保持正常状态，真实GET503保留IoError/qmt_http_remote_failure并正常进入Closing |
| 纯交付索引 | 9组、499断言、4条逐分配故障路径、30次真实bad_alloc注入通过；不能替代全Standard链分配失败矩阵 |
| 独立静态审查 | full及各delta所有已发现P2关闭；最新38份规则/规格/源码及依赖逐SHA根核一致，无剩余确认P1/P2 |

19场景的实际输入分别固定：runtime016的17个成功模式使用Probe016；其整批因两个夹具调度问题失败，整批状态保留failed。修正仅影响解绑方法的trade前页内continuation推进，targeted017以Probe017重新执行stop/detach/detach-read-error三模式全部通过。相同最终DLL保持，成功未变模式按原Probe016范围复用；Probe017未执行模式没有新增动态结论。合并去重后19个模式逐原件核验，见逐场景清单（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-events-final-002/QUALIFIED-EVENT-CASES.json`）。旧15方法及索引分别使用其实际执行制品，不把全部数字合称一次CTest。

页末延迟/空页延迟及错误正文问题用修前6a251插件真实复现，对应修后已通过。解绑反证用修前d264插件取得真实原UUID GET200/native_ok成功，但owner误报qmt_standard_base_data_missing并转Closing；修后同窗口正常抑制，真实503仍保留故障。反证后检明确记录原验证驱动预期了较晚的断言标签，而旧pump实际先负返回；原诊断及成功GET足以核同根因，原失败驱动和字节保留。

本轮18个创建期Job受控执行树均已实际回收：非强停、tree_zero、读线程join、资源关闭及双EOF均核实。中间失败构建和夹具运行保持实际失败状态。最终封存入口：源码/日志/回收清单（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-events-final-002/REVIEW-ROOT-CHECK.json`）、独立报告（外部历史/待归仓路径：`../../build/qmt-standard-event-independent-review-001/FINAL-REVISION007-INDEPENDENT-REVIEW.md`）。

## 限制与后继目标

新事件消费者使用正式HMAC/账户协议及合成完整事件源，真实原版Adapter归约；本次没有真实券商委托、撤单或终端重启，也没有生产切换。先前真实SHM事件→金融/P8证据与本次Standard SPI证据分别成立，完整SHM事件→Standard SPI组合链继续验收。新WT框架修改、旧QMT项目修改均为0，生产Factory仍旧，event_consumption_complete保持0。

同seq成功重取由纯Index测试覆盖；Standard把已前移cursor下的旧seq页作为Common契约负例拒绝，未新增历史页自动重试资格。最大页N+1必需复验的CPU/容量/分配/原D边界、完整Standard故障和父死亡矩阵仍待测。

生产首次/重连query-live交接仍按[来源边界调查](2026-10-24-qmt-query-live-source.md)和SEV-R8闭合；不能从四查询返回推定持仓覆盖。继续R5缺字段补查、unknown定向撤单、真实来源字段/生命周期、QMT历史覆盖/原生消费、全部保留策略与观衡入口、独立安装搬迁及发行。当前没有新增需要用户即时决策的事项。
