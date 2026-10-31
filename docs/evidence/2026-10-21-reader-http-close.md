# 历史 Reader HTTP 退出与运行器验证

类型：候选验证记录。日期：2026-10-21。状态：Reader切片 DevelopmentVerified；完整运行器退出待解决。依据[NHR最终规格](../specs/native-history-reader.md)及[原运行器边界](../migration/native-runner-boundary.md)。保持框架冻结；本轮不部署、不重启终端、不执行账户或交易请求。

## 已重现的根因

StrategyReader原stop只等待active读取/事件归零，没有等待provider内部仍在执行的系统回调。回归 `guanheng_reader.stop_waits_for_provider_callback_drain_before_reporting_success` 在未修复实现两次失败：未放行provider回调时stop(20)返回Ok，drain调用数0，预期Timeout及调用一次。原始 `build/native/reader-drain-red.json` 记录退出1、二进制摘要及原StrategyReader源码摘要。接口已增加同步provider默认drain，原stop实现尚未接入时取得此红例。

修正范围为自有ReaderHttpClient与StrategyReader：使用系统session最后回调完成通知，active归零后在原stop截止内排空；关闭失败保留依赖，批回调期间保守Pending，slice和DLL所有权保持原约束。旧析构入口仍需等待安全释放，可能无界；受管调用方应先有界stop并在失败时保留依赖。

## Reader 最终回归与独立审查

完整 CTest 的 90 项启用测试通过，另 1 项既有全天会话测试 Disabled。Reader 包含 13 项原生测试及一个执行 7 个独立进程的真实 WinHTTP 测试：会话容量64/65边界及释放后复用、普通关闭、超时后的迟到回调、401早退、畸形响应早退、工厂销毁、持有slice跨reader销毁。容量用例直接运行共用session管理器，未声称建立64条网络请求。同步关闭与实际迟到回调分别记录，未把同步等待冒充异步路径。

最终 `build/native/ctest.xml` 与完整 `build/native/cmake/Testing/Temporary/LastTest.log` 保存结果；XML截断的子场景输出以完整日志为准。独立full位于 `build/native/reviews/nhr-exit-full-cad5abb8-f699-4640-9300-3ecb1af0acc8/`，包含review.md、validation、22项输入摘要及提取的reader-drain-ctest.txt。审查无阻断，NHR-R3/R4/R5本轮隔离资格通过；root在最终构建后复核22项摘要全部匹配。

完整 `native.py all --offline --qmt-source D:/workspace/qmt --calendar-owner-source E:/workspace/qmt-worktrees/wondertrader-service-adapters` 退出0，22阶段passed，90启用CTest、32流水线测试及包内reader/策略/独立日历链通过。日志 `build/native/reader-close-final-all.log`，回执 `build/native/receipt.json`。开发包 `dev-20261021T112246Z-b13b5153.zip`，6,223,566字节，SHA-256 `5524d66cdca1b4fcd3f17621f4fa639081066b3ca4650f4b3a7d223aab2546ab`。12个既有框架差异摘要与观察文件相同；本轮新增生产实现均在自有适配层。开发包仍包含既有冻结差异，生产资格和发布保持未完成。

## 真实行情延迟分段

作为18010只读接入的后续定位，独立诊断客户端按同样的prepare/read顺序读取两次单证券full_tick。所有响应身份仅内存比较，存证只含HTTP码与白名单计时；无账户、行情明细或凭证。

| 阶段（毫秒） | 样本1 | 样本2 |
|---|---:|---:|
| read前health | 966 | 1004 |
| operation HTTP往返 | 2039 | 2028 |
| 其中queue_wait | 984 | 1000 |
| 其中execution | 30 | 0 |
| result_persistence | 0 | 15 |
| response_wakeup / response_handler | 0 / 0 | 15 / 0 |
| read后health | 966 | 962 |

原始 `build/native/live-source-probe/http-stages-eb7a4cffdbeb40a39cb42cd5d8e9ef99.json`，脚本 `measure_http_stages.py`。两次响应均200、来源前后相同、结果ok。执行字段包括原生取数后的序列化范围，0表示服务端整数毫秒计时精度。分段表明本样本原生执行非主要耗时；单次read前后health+operation合计3971/3994ms，解释3秒预算失败。剩余未计入服务端指标的HTTP接收/交付时间继续由QMT运行线程调度观测定位，不能仅凭此表断言某个GIL持有点。

安装版一秒策略节拍、单轮operation限制和响应交付轮规则已核对，详见ignored `latency-audit.md`；本轮保持原QMT代码、调度和配置。10秒探针预算是已记录配置，未将增大预算作为根因修复。

## 未覆盖范围

完整原WtRunner的pool=0/2隔离实验已运行：初始化保护生效，Pending时策略计算0，补齐后同实例计算1次并读到2根历史；正常SIGINT处理返回后，两组均退出0xC0000409，driver未强杀。记录见[原运行器实际结果](../migration/native-runner-boundary.md)。该宿主退出故障与本轮自有Reader修复分别验收，后续独立MAP/反汇编及审查已定位CTA销毁未join的ticker线程；[13文件退出链提案](../migration/native-cta-stop-proposal.md)待批准。生产盘中持续行情、独立服务发布、页面入口和真实交易恢复继续按[总验收地图](../migration/acceptance-map.md)验收。
