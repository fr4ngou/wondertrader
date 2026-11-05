# 现金5线上结果与事件消费修复

时间：2026-11-05北京时间12:10。状态：in-progress。范围：自有QMT接入与运行装配；没有新增WT框架修改。

## 实际运行结果

09:35，共振ETF1.2.1由自然行情计算8个目标，经WT标准执行入口产生模拟买入和成交。已保存券商订单832806091、832806115、832806612等实际查询与成交；原100万元含持仓基准及financial-state008持续保留。

cash5在10:15沿原process_lost_reconciled流程接续，WRI21352/Native4484实际启动。跨11月4/5日成交查询known=true/error=0，159780开仓周期恢复为今天09:36:13，随后继续买入执行。这证明跨日与开仓来源修正已实际消费。

提交8b18e3d、标签guanheng-wt-runtime/cash5-20261105、cash5轮子及固定原生构建身份沿[候选记录](2026-11-05-cross-date-trade-candidate.md)。008为准备目录，实际部署采用稳定native-execution-007路径；旧五二进制和清单已保存在私有QA回退目录。解释器为runtime-service-20261105-014，操作员为operator006/group011，观衡仍独立运行18143。

## 当前阻断与根因

首次连接的完整P/O/D/A查询之后，StandardQmtTrader仍从事件cursor=0读取并逐条重放Host保留历史。原回报又触发O/P/A查询，形成串行积压；当前P比已交付成交新，导致实际开仓一致性核验等待。Source与Host自己的增量采集使用持久前沿，消费端首次读取位置是本次修复责任层。

修正方向：仅query_first首次Prepare在四查询之前获取经验证的durable_through，完整查询后从此前沿继续增量。查询期间新增事件必须继续交付，既有未知命令仍按原ID核查，运行中重连保留原cursor。无需修改QMT正文、Host协议或WT框架。

11:37的OS核实确认Native4484和WRI21352已退出，原failure记录为10:50 runtime/plugin_error=1、host_fault=3、session_fault=4。该退出的具体首因尚未查明，不能把事件积压推定为全部退出根因。正式故障、原委托、金融文件和close-prepared(ok=false)保留；恢复前核查原委托，禁止重复提交。

前次10:09带活动单正常停止另有recovery_drain超时，保留真实失败及process-loss交接，没有生成正常关闭证明。该项和持续运行仍需真实验证。

## 数据与页面现状

11:41直接读取18143：300308、588170、000001日线均到11月4日，分钟均到今天11:30。市场数据采集继续运行。系统状态实际显示账户WT faulted，其他四个WT角色ready；策略页保留上次buying结果，runtime_state=faulted，不能把该旧结果视作当前执行中。

原图缺日线及上证叠加已修复；当日完整日线仍随收盘发布。当前全市场余缺、部分指标预热和最终清理保持未完成。证据保存在unified-wt-operator-20261105-001的CASH5-ACTIVATION002、CASH5-LIVE-MAINLINE002、CASH5-LIVE-CURRENT003及原故障文件。

## 下一项验收

首次连接跳过已由初始查询覆盖的旧事件，查询期间新增事件交付一次；原未知委托继续原身份核查。新插件经同批构建后，沿原金融状态恢复，实际核对实时成交、P、开仓周期与连续自动执行，最后核对独立观衡展示。当前无需用户新增决策。

## 事件前沿部署与午休恢复结果

修正已合入b524d14，Standard源码SHA6b4d2a8b0514da623657882ed8d90e5574645286a5a19d0b5c8c0477184bc9c8。独立delta静态审查complete，完整翻译单元MSVC语法检查及实际方法/DTO/银行的合成回归通过；该合成证据分别覆盖默认路径、durable=37而next=1、404后真实零前沿，并以去掉成功Status重置得到实际失败。完整插件/SDK业务结果继续单列。

build/ef1正式同批构建通过，25安装文件、旧项目二进制输入0；此前长目录构建在Boost解压时触发Windows路径长度错误，未采用。稳定native-execution007的五个组件来自ef1同次构建，旧五组件及清单已另存私有回退目录。没有重打Python轮子，也没有修改QMT正文。

12:02启动金融WRI39580/Native55152，交易插件连接通过。恢复按原身份向券商订单832817087（515080）发撤单，原通信Journal序号281明确sdk_returned、sdk_entered=true、signal_sent=true、无error。12:03:10券商完整查询仍为原状态50、剩余1000；Native在reconcile_orders等待至原启动截止后退出，plugin/host/session错误均为0。此结果尚未证明撤单终态；午休时间与等待并存，下午必须先查原订单，不能猜测成交/撤成。

该次初始化没有取得ready、没有进入CTA；按前次已绑定交接逐字核验三份金融JSON均未变化。service003下午接续材料引用最后真正拥有该金融状态的Native4484；原失败初始化及已发撤单的Journal保持。准备只证明材料完整，未启动service003，也没有生成正常退出或恢复成功证明。当前金融仍faulted，另外四个数据服务继续运行。

证据：EVENT-FRONTIER-ACTIVATION001、EVENT-FRONTIER-NOON-BROKER001、EVENT-FRONTIER-POST-NOON-PLAN001，以及standard-frontier-20261105-001/RESULT.json。下午沿已准备入口只启动一次并观察同一实际实例，未核清时保留原身份和故障。
