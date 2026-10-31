# QMT 首次事件取页的真实读取配置

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-24。结果：accepted切片限定开发验证通过，完整Standard消费者仍待实施。要求：[SEV-R2c](../specs/native-qmt-standard-events.md#sev-r2c-首次取页前的真实读取上下文accepted切片)。

## 根因与实现

标准消费者首次取页需要真实 profile 和 Host 已准入的事件页容量。旧 prepare 仅返回 Status，成功 events 才带出上下文；调用者无法在首请求之前合法选择 limit/max_bytes。HTTP接收上限、账户结果上限及profile最大页容量分别拥有不同含义，不能相互替代。

自有 Common 新增 QmtTradeEventReadContext 与 prepare_event_read_context(originalD,out)，先沿Core原check核线程与原D，再复用同一次原 prepare 的 read-binding→refresh 两次 GET。仅本次 Status 成功后复制原 B/session、原 profile、descriptor、read_result_capacity 和实际 Host 页上限；完成全部可抛复制后末核原 D，以编译期保证无异常的移动赋值发布 out。失败及异常保持 out 原值，旧 prepare 的内部状态副作用不作回滚承诺。

旧 prepare 存在早退保留旧 ready 的路径，新接口直接依据本次 Status，不凭旧 ready 发布陈旧配置。接口不新增取页、lookup、SDK、线程或网络客户端；公开 DTO 可改写，其本身不认证来源，也不授写权限。WT框架、Host协议及原 prepare/events 调用面保持。

## 输入与实际运行

根保留 修改前四输入（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-context-001/BEFORE.json`）、四产品/测试输入摘要（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-context-001/CONTEXT-SOURCES.sha256`）；实际 CMake 与完整运行输入见 运行快照（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-context-native-001/identity-build-inputs.json`）。Windows/MSVC，真实认证回环服务，合成来源，真实券商 SDK 为 0。

十组受影响 CTest（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-context-native-001/ctest-identity.log`）全部通过，81.95 秒；实际分组日志（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-context-native-001/LastTest.log`）确认新增4方法、15上下文场景、无跳过，同时保留46事件身份场景、31事件金融样本、128旧金融/115规范样本和4真实append所有权场景。已有codec、原生客户端/故障、订单查询、账户投影与身份链同时通过。

新增场景实际核验每次准备只有两次GET且没有事件页/命令/账户请求；Host实际3072字节小于profile4096上限；全部descriptor、原profile/B/session一致且在client退出后独立存活；公开值变动不改Core；错owner/已过期无新HTTP；两阶段503/真实晚回复以及先成功后来源/profile变化均失败且保留out全部字段。只读请求不增加写许可。

## 证明边界与后继

分配异常以及复制完成后精确耗尽 D 的窗口尚未动态注入；out强保证对应源码局部临时值与末次无异常发布结构，不将15场景扩张为逐分配故障矩阵。独立 full 与最终固定原版WT候选组合结果另补后继。

本次没有装配 Standard 持续调度、首cursor、长期交付索引、SPI、缺字段补查或query/live交接，event_consumption_complete保持0。原SHM三回调的独立[事件映射证据](2026-10-24-qmt-event-identity.md)仍按各自源码身份使用。本次没有新增WT框架/旧QMT工程修改，没有终端重启、真实委托、生产Factory切换或发布。

## 后继：线程预检与最终验收

原prepare在拒绝错线程之前先写accepting=false。新接口原初规格只承诺out强保证及客户端独占；初次full审查（外部历史/待归仓路径：`../../build/qmt-event-context-review-001/NOTES.md`）保留该边界，没有据此泛化为WT框架问题或客户端并发安全。后继接受将预检前置于自有新接口，原prepare保持。

修前真实反例（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-context-owner-repro-001/RESULT.json`）先经真实两GET取得accepting=true，再在错误线程调用新入口；确认Conflict路径改写原准入标记。旧探针及精确源码已保留。修正只在新方法入口增加core.check(originalD)，失败在进入原prepare前返回；客户端整体仍由创建线程独占，不新增并发调用承诺。

最终十组回归（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-context-native-002/ctest-identity.log`）全部通过，81.03秒；上下文实际4方法16场景、零跳过，新after-wrong-owner断言此前accepting真、拒绝后仍真、out全部保持，HTTP仅最初两GET。原46事件身份、31事件金融及全部兼容组同时通过。最终六输入与原字节见最终源码（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-context-final-001/SOURCES.json`）。

独立DELTA-001（外部历史/待归仓路径：`../../build/qmt-event-context-review-001/DELTA-001.md`）静态P1/P2=0、执行0/动态unknown；根核37来源（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-context-final-001/REVIEW-ROOT-CHECK.json`）及原字节匹配。分配异常、复制后精确D窗口及整体客户端并发误用仍未动态注入，Full/Delta与动态运行各自保留范围。

固定原版fixed-010构建（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fixed-010/result.json`）与runtime-010组合（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-010/result.json`）实际通过15方法16场景，真实SDK0。该二进制构建于预检前置之前；Standard尚不调用新context入口，原Standard/Identity/mapper路径与旧prepare正文保持。限定复用核对（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-context-final-001/STANDARD-REUSE-SCOPE.json`）明确只复用既有路径资格，新入口以最终native-002为准，不能把fixed-010称为从最终guard源码重建的制品。完整消费者装配后还须重新构建、组合与安装验收。
