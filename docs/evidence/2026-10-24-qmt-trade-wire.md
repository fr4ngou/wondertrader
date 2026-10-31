# QMT交易控制协议与组合能力验证

日期：2026-10-24。类型：开发验证证据。范围：[QST-R12/R13/R14](../specs/qmt-shm-trading.md)的时钟、控制消息、组合描述与旧读兼容。继续已测嵌入加载及builtin-shm；完整配置、同策略回调、Host派发及WT交易消费继续开发，真实写默认关闭。

## 实现与实际范围

新增trade_clock.py统一Windows同次启动的uptime毫秒域，业务deadline沿原绝对值传递；转换向下取整，重复请求和接收不会重新开始TTL。本地I/O截止继续由原通信owner管理。构造时检查实际平台、实现和时钟属性，未知实现拒绝准入。没有新增终端文件、网络或DLL加载入口。

控制2.0沿原1.0固定摘要扩展agent.trade、status、events和ack语法；旧1.0默认及消息预算保持。生成器在终端外按完整整数精度验证原JSON和差异定义，再输出静态模块；不在QMT内读取JSON。新take_call_with_deadline与旧take_call共用一次交付状态，返回第一次映射的原本地截止。

组合read-profile.v4显式包含trade-profile、control2和账户读取，行情快照/历史可组合；旧v1/v2/v3生成字节及读请求语义保持。交易descriptor只公布绑定摘要和有界额度，完整私有绑定沿原契约另验。当前部署工厂、生成入口和原生客户端尚未接入v4，配置联合额度及回报持久保存后ACK仍待开发；模块验证成功不授实际order_ready。

## 冷时钟与内存验证

qmt-trade-clock-002/result.json记录开发Python3.12.14与国信Python3.6.8，双方implementation=GetTickCount64()、monotonic=true、adjustable=false、resolution=0.015625s。16个源样本848447968ms落在外部原生计数前后界[848447812,848447968]ms。原001缺少Host部分属性，002补齐且001保留。实际SDK调用0、qualified_in_qmt=false；该冷探针不授任意解释器或真实策略时钟资格。实现核查依据包含[CPython3.6.8计时源码](https://raw.githubusercontent.com/python/cpython/v3.6.8/Python/pytime.c)。

qmt-trading-memory-probe-004的87模块闭包在目标3.6.8通过。验证区禁止文件和外部导入，实际尝试0；两个SDK替身分别覆盖下单与撤单，实际SDK0。新增时钟准入、交易descriptor及control2合成双peer的原截止交付通过，事件捕获/确认及关闭后gap通过。准备和结果输出由终端外工具完成；探针没有启动真实QMT策略或共享内存交易通道。memory_runtime.py与pair.py保持前轮摘要，继续已测加载器路径。

## 回归、根因及独立审查

| 验证 | 最终结果 | 控制收据后缀 |
|---|---|---|
| 开发Python3.12纯测试 | 58通过，0.065s | qmt-trade-wire-unit-002 |
| 国信Python3.6.8纯测试 | 55通过，0.086s | qmt-trade-wire-sdk-unit-002 |
| 既有control/read/bootstrap/pair/history回归 | 99通过，1.12s | qmt-trade-wire-regression-003 |
| 87模块禁文件内存探针 | 通过，实际SDK0 | qmt-trade-wire-memory-target-001 |
| 静态生成器--check | 字节匹配 | qmt-trade-wire-generator-check-001 |

58与55的差额为3项只适用于现代构建环境的生成器测试。16项交付故障测试覆盖MemoryError、KeyboardInterrupt、字段复制及返回值构造失败、真实测试线程竞争、同步重入、close/expiry与receive更换容器。所有最终控制收据退出0、非强杀，创建前Job归属、无控制台、树归零、双EOF、reader join与资源关闭均确认。收据位于build/guanheng-workspace/account-runtime-install-001/build-加表中后缀。

独立wire full发现交付P2：原逻辑在解码及返回值完整构造前标记taken，构造失败后可能无法重取，ACK也会提前放开。统一修正为短锁领取唯一lease、锁外完整构造、复核原截止/当前条目后提交taken；异常只释放自己的lease。Future与两个CALL入口共用该逻辑，close/expiry后不回插旧条目。qmt-trade-wire-review-002/REVIEW.md静态delta闭合原P2，24输入根核无漂移；静态审查与上述实际执行分别登记。

profile独立full complete-static，无P1/P2。原报告冻结的规格摘要随后仅增加R13交付失败语义，review-inputs已核R14不变；当前源码26项与原full匹配，唯一规格差异由wire delta覆盖。联合配置、运行装配及C++资格保持未完成。

旧回归001因外部driver缺少仓库搜索路径而收集失败；002修正driver后98通过、1项旧fixture在public={}处KeyError。真实bootstrap在Journal构造前已读取max_request_bytes；测试改为沿真实validator和bound.limits产生完整public。Journal内改变外部secret及Runtime应取得旧快照的两项断言原样，独立TEST-FIXTURE-DELTA.md确认其可达性和强度，最终003共99通过。失败收据、原测试及旧报告均保留，产品bootstrap未改。

## 归档与后续

build/guanheng-workspace/qmt-trade-wire-evidence-001保存最终源码/测试/规格及探针、收据、审查原件摘要和结果汇总。前轮[通信Journal与源端回报证据](2026-10-24-qmt-trading-communication.md)继续按其原输入适用。

下一步实现完整私有配置和联合额度、沿现有策略注册SDK/回调、Host命令及回报接线，再接标准C++ TraderQMT/SPI。真实权限、SDK返回及柜台ID语义、unknown核查、独立安装、真实交易和生产分别验收。本轮旧QMT工程保持静态只读，WT框架无新增修改，完整迁入目标active。
