# 唯一1.1.2原生日线回放

类型：模块C开发整链证据。状态：本回放切片完成原链、普通纯包安装、双轴修正审查和精确交付。范围为[RR112-R5/R6](../specs/retained-resonance.md)；完整模块及真实M1保持in-progress。

## 根因和实现

原App回测owner接configured/V2，唯一1.1.2尚无正式接缝；当前可见纯核要求实际接收不晚于决策，直接倒放本批历史会产生错误时间声明。本轮增加显式RetainedHistoricalModel，保留实际known_at/received_at及未知历史首次可知/修订，声明日末可用和最终基准前复权假设。历史与当前入口共用原唯一特征、信号、分配和实际周期逻辑，历史结果使用独立schema并始终保留未取得来源/执行资格。

retained_evaluation将完整八目标、原分配日期和配置摘要映射到原NSQ。retained_replay的正式同步run组合原BacktestPorter、原日线回放、原理论持仓/资金、NSQ及绝对目标setter。已有strategy_session的原生事实采集、精确资金编码和基础资料准入抽至strategy_replay_facts，两类会话共用同一实现，原编码口径保持。Python仅绑定已有cta_save_userdata/cta_load_userdata；原DLL及WT框架源码未修改。

周期仅保存身份和开仓时间，数量取当次原持仓；部分减仓导致first_entry成为较晚的剩余明细时保留原周期。退出状态同存原用户变量，写后核原接口读回，正常结束后核原ud_策略名.json与最后状态一致。该首回放从flat开始、独占setter；实时接管与恢复继续由B拥有。

## 原生主调用链

独占原件根为`build/retained-resonance-replay-001`。main-006通过原scripts/native.run的预绑定Job/总截止/隐藏控制台执行，公开固定JSON解码→新普通安装corea8/V1a5/nativea1/tzdata→当前源码App接缝→原WtBtPorter→完整报告。App本体当前仍为源码消费，未宣称新完整App安装。

125个合成交易日/1000行形成124次原计算，沪深300和上证50均实际产生原模拟持仓；上证50移动止损触发、卖出并延续退出状态，最终converged。原费用为非零，报告绑定7个原生输出文件的SHA。逐日实际接收时间保持原完整批次的实际模型接收时点；历史假设随每日摘要传递。原userdata实测32768字节接受、32769字节/非ASCII/NUL键拒绝；init写入及非owner线程读拒绝。原生正常结束、release及外层Job/tree/EOF/join完成。真实QMT请求、账户查询、下撤单和生产变更均为0。

package-001普通安装4发行673个哈希RECORD，3个私包wheel成员与安装payload相同，pip check通过。core沿旧a8原wheel复用；V1a5增加显式历史模型。当前root App旧依赖/runner/报告消费者仍待整体收敛，不把本安装当作完整应用发行。

## 回归与保留尝试

源码回归128项通过，包含原session回归与新增历史时间/批次绑定、同核结果、共享资金/事实、固定输入解码、稳定经济代际、部分减仓周期、未知费用、外来原生状态、错前缀和提交前容量拒绝。普通安装回归及独立双轴审查结果在后继段登记。

main-001的原生主链完成后，QA把上海时区字符串直接比对规范UTC字符串而失败，main-002改为UTC核对通过。tests-001发现新增历史模型局部名与旧信号局部名相撞，结果历史声明被覆盖；修正为独立historical变量，并增加每日模型声明断言，tests-002通过。tests-003误用EconomicTarget.config_sha256字段，按原合同config_id纠正，tests-004通过。原失败日志、脚本及关闭收据保持；每个失败九项回收标记true、cleanup_errors为空、无保留owner。

## 当前限制和下一主线

行情、辅助输入、前复权因子和理论本金在本轮为明确合成；六参数的实际私有材料沿[已核纯核证据](2026-10-29-retained-resonance-kernel.md)，本轮未打印或改动原值。A真实同基准前复权窗口、B实际周期/存量接管及实时目标、隔离委托/撤单仍需消费最终候选。原runner/受管宿主、工作区HTTP、报告/比较与浏览器尚未接新回放schema；root App发行依赖、普通完整安装、升级回退仍待验收。完整goal保持active，A唯一集成，当前未部署。

## 独审修正候选002

001 full检查发现退出延续每日更新source_allocation_date，同权重被NSQ视作新代际；另报告/用户状态编码可能越过原截止后才调用setter/store。原报告及独立复核保留。唯一核改为引用原退出日，解除退出形成当日判断；App使用原NSQ上一目标，完整权重及稳定身份相同则沿用经济日期，恢复A→B→A使用新判断日。两个原生副作用之前复核同一check，编码超期立即停止。

最终候选为corea8/V1a6/nativea1/tzdata的runtime-002/wheels-002。4发行673条哈希RECORD、3wheel payload和pip check通过，tests-008为132项普通安装回归。main-008再次125日/124原计算、上证50建仓/移动退出和原费用/7输出/原userdata保存通过；九个延续日保持单一经济代际，加入沪深300价格从100上涨至140的变化后仍保留原冻结200份。原Job/tree/EOF/join全部关闭。main-007主链完成后误把StageState.generation_id属性当作wire字段，QA失败；008使用原NSQ公开模型重建并核generation_id，原失败及九项关闭收据保留。

原examples中的三个旧版本已按字节复制封存到archived-v1-examples，当前公开样本改为唯一1.1.2的当前/历史两例。sample-replay-002用普通安装a6公开接口输出，与TARGET逐字节一致，SHA为8763ed5132d82fdb30b8b6097182fd220bdc34dfaf3e3d361f03cc84e658a3fc。project.py check通过。修正delta及精确交付在后继登记，完整App和真实M1仍沿上节限制继续。

## 最终审查与交付

REVIEW-INPUTS-002的SHA为66c9dbe88b3ab28e37707c11fd73119e6b2d1379c80d69ccd1eff4f0f1a8d8bf，固定21源及98原件，原001的43 raw全部保留。规格delta报告SHA为67e045bc3b66e64ca52eb884c49b06021a8bfd94b7f094c9d64af471a7be0e65；规范delta报告SHA为2d569303d9529070041ee6ae865726667e67244430a6535b22f690849830e6f6。两轴均complete、原P2关闭、无新增P级问题；两轴独立复验119项、普通安装673 RECORD/3wheel、两个截止触发、原生原件和样本，未执行新服务/真实来源。原full gap报告保持。

交付清单位于`build/retained-resonance-replay-001/DELIVERY-002.json`，开发候选ZIP为同根guanheng-retained-replay-candidate-002.zip，SHA及成员逐项见清单。交付复核当前产品与冻结源、98 raw、普通安装/全部wheel payload、7原输出及失败运行的九项回收事实；最终状态文档按审查结论单独冻结。候选只供A集成新回放接缝和纯包，不是完整App发行，也不授真实A/B/RT/HTTP/UI或生产资格。下一项必要工作是新报告族的受管runner、HTTP/归档/绩效和中文页面整链；root App唯一依赖和B实时接管随后按同候选核对。
