# QMT账户原始委托字段投影验证

类型：开发验证。日期：2026-10-24。范围：标准TraderQMT规格STQ-P2/P3中显式版本、原始字段运输和完整内存策略准备。状态：本切片通过；WT身份覆盖、标准插件及重启恢复继续开发。

## 实现与职责

账户读取此前只投影金融字段，委托/成交查询无法带回原始备注和本地引用。本次在同一读取链新增显式账户policy_version=2.0，仅与v4/control2组合使用，版本事实取自可信operation descriptor。旧v3及v4/account1.0继续输出batch.v1；新版本输出batch.v2，order/deal增加m_strRemark、m_strOrderRef，其他两类账户查询保持原字段。

两个字段沿原getter、标量、容量及截止时间逻辑处理，保留缺失、null、空串和数值零；不从备注格式猜测WT归属。Host按原请求校验数据版本，C++在prepare冻结原profile和容量，并在同一receipt恢复时复核。旧两字段receipt的空/0兼容仅用于原policy1路径，不能据当前响应升级原请求。

WT的userTag仍由原生TraderAdapter自动生成；QMT实际撤单继续使用券商委托号。本次只运输后续关联所需原始信息，没有增加用户参数、实盘资格或审批条件，也没有实现完整身份覆盖。金融转换仍归唯一AccountMapping；本轮未修改WonderTrader框架。

终端外新增prepare_trade_runtime，与原只读prepare_runtime共用准备逻辑，分别以trading_agent和restricted为实际依赖闭包根。QMT运行期继续使用完整正文中的内存源码及builtin-shm，策略运行期无外部文件或网络加载。

## 运行证据

下列原件均位于build/guanheng-workspace，实际券商SDK调用为零。

| 验证 | 实际结果及目录 |
|---|---|
| C++重编 | qmt-native-trade-build-001/trade-projection-final-build-result.json通过；Common、codec探针、交易探针和故障DLL重编，编译输入无漂移。 |
| Python受影响回归 | qmt-account-projection-regression-002：529通过、25跳过，25.54秒。跳过的6个真实原生场景、11个故障方法和8个HTTP投影方法全部另经下列CTest执行。16个新投影测试含实际SDK源码元数据的完整内存生成，无环境跳过。 |
| 最终原生CTest | qmt-account-projection-native-002：四组全部通过，35.60秒，源码快照无漂移。 |
| 原生交易闭环 | integration.qmt_native_trade_client实际7个方法通过，含原6方法及新增account2.0往返；C++、认证loopback Host、通信SQLite、真实Win32 builtin-shm、原策略线程和SDK替身均参与。 |
| 新版本四查询 | roundtrip-projection-v2场景：position/order/deal/account各一次，原线程查询；order/deal各两行，覆盖完整原token、普通中文备注、整数0与空串。按request_id核C++原data字节SHA与Host原片段SHA，并独立核源行原值。原下撤单替身各一次、三条回报及源ACK、同receipt恢复和正常关闭断言保持。 |
| 原生故障与旧版本 | integration.qmt_native_trade_client_faults的11方法/27场景通过，原V3/V4空币种等场景保留；integration.qmt_trade_v4_codec的新旧版本准入通过。 |
| HTTP投影故障 | integration.qmt_account_trade_projection的8方法/47子场景通过，包含字段原值、版本、预算、receipt原profile/容量、响应篡改和原截止。 |
| 目标解释器 | account-runtime-install-001/build-qmt-account-projection-sdk-regression-001：实际国信独立Python3.6.8执行167项源端回归通过，0.227秒。 |
| 完整内存策略 | qmt-trading-memory-projection-002：公开prepare_trade_runtime生成91模块闭包和完整render_trade_strategy正文，目标3.6.8执行通过；新增order/deal查询各一次且batch.v2/原标量保持，既有策略初始化、下撤单替身及回调/ACK/关闭保持。文件和外部导入尝试均为0；运输start在该探针使用替身，实际运输由上述原生闭环证明。 |

最终交易探针SHA-256为2f8004f83b15fac93c1ed5426156207ca99f4f0f29aa2a03f1f36a9b1f42d0db，故障DLL为42dd1e24d742a975e664e8344b49aeac2e362289e11f2e51f682b1666cc1bd26。完整策略SHA为e103cccf16910f45086bc9be681ec4f2e3a1bbfb12377ca0754e7f091b510d68。

所有进程由隐藏、有期限的控制器管理，先加入Windows Job再恢复执行；最终控制器的进程树归零、管道EOF、读取线程join和资源关闭分别核实，无强制终止。最终汇总及控制器收据见qmt-account-projection-final-001/FINAL-SUMMARY.json与FINAL-CONTROLLERS.json。

## 失败原件与独立审查

首次Python回归发现两处测试假设错误：MemoryCompletion.poll实际返回dict，测试重复decode；旧负例仍将新增合法版本2.0当成非法。修正测试为直接读取完成值、用真正非法的3.0验证拒绝；生产源码保持。首次2失败/527通过/25跳过原日志留在account-runtime-install-001/build-qmt-account-projection-regression-001。首轮原生日志四组通过，其同目录result.json后被首轮Python驱动覆盖，最终原生验证已在独立qmt-account-projection-native-002重新执行和封存。

首轮新增内存探针遗漏请求的correlation_id并使用非UUID request_id，原协议正常拒绝；qmt-trading-memory-projection-001原件保留。按真实请求契约修正后在002重新生成并通过，产品源码保持。

独立审查位于qmt-account-trade-projection-review-001：full核生产者/Host/Core、版本/预算/receipt、内存闭包及测试接线；DELTA-001核真实SHM增强；DELTA-002核两处测试契约修正。最终静态complete，无剩余P1/P2；根按最终34项来源逐一复核，无漂移。审查者执行为零，动态结论由上述实际运行分别证明。

Core验证外层result原bytes/SHA；Host另复核内层native SHA。本次没有把外层篡改测试表述为Core独立复算内层摘要的证明。

## 剩余范围

当前ShmAccountMapping仍沿旧batch.v1路径；新增batch.v2的WT身份覆盖尚未接通。标准TraderQMT Factory/ITraderApi/SPI、旧自有ManagedTrader额外签名/资格等级/原子四查询前置退出、事件消费与重启交接、独立安装及真实终端委托仍需完成。目标SDK对新增字段的真实回显类型、长度和完整性需要后续只读证据，当前合成字段不能替代该结论。

WT原查询与事件没有已证实的共同原子水位，恢复方案仍需明确覆盖查询期间成交及回报晚到；本轮运输通过不能证明重启恢复完成。整体迁入目标保持active，下一步沿[标准TraderQMT](../specs/native-qmt-standard-trader.md)完成身份覆盖与标准插件接线，保留原生持仓/资金处理职责。
