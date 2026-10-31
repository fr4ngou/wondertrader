# 事件触发账户查询的纯匹配验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：SEV-R5c纯匹配模块、独立原生编译与72项检查通过；真实补查worker、P8来源与Standard交付尚未接线。依据[事件规格SEV-R5c](../specs/native-qmt-standard-events.md)。

## 实现与根因

AccountEventMatch仅消费原事件文本、已由原Core采用的完整QmtAccountResult、绑定和显式额度，返回唯一原查询行index及有限诊断。完整扫描后区分非法行、可能匹配但定位不足、重复/多匹配、共有事实冲突、未补齐和唯一完整匹配。ORDER采用真实后续整行并核共有不变量；DEAL比较完整作用域和共有事实，不对多笔成交做合计或字段拼接。匹配结果本身不认证账户来源，也不授金融发布权。

首版自查发现原json_text在返回std::string时仍持有StringBuffer，长备注会同时保留两份序列化文本。revision002在实际编码前核U+2×(L+1)，再与后续U+(L+1)+row_inspection占用取最大值；U已含完整DTO十个字符串、原事件、固定预留和event_inspection。共享编码器、唯一mapper、Common、P8和Standard均保持原样。旧001原件保留，尚未编译或运行的旧定义不作为通过证据。

## 实际结果

| 验证 | 结果 | 原件 |
|---|---|---|
| 独立full与接线delta | 最终002和三TU接线无阻断后续验证的发现；执行0 | 独立报告（外部历史/待归仓路径：`../../build/qmt-event-row-match-independent-full-002/REPORT.md`） |
| 固定原生编译 | 原上游08b230、323上游/156自有输入；NqpAccountEventMatchProbe独立EXE；61.969秒正常结束 | 编译收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-event-match-fixed-001/result.json`）、控制器（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-event-match-build-controller-001/build-qmt-account-event-match-build-001/result.json`） |
| 纯匹配实际检查 | event match checks:72，全部通过，0.281秒；覆盖后续订单、成交作用域、多匹配、尾部坏行、潜在定位、原始index、强失败及容量 | stdout（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-event-match-runtime-controller-001/build-qmt-account-event-match-runtime-001/stdout.txt`）、探针源码（外部历史/待归仓路径：`../../tests/integration/qmt_shm_account/mapping/event_match_probe.cpp`） |
| 独立人工容量oracle | 完整DTO=data_json.size()+126，两个inspection各405；4096字节备注明确覆盖双文本峰值、exact need/need-1与旧少计额度拒绝 | 同一72项实际探针 |
| 生命周期 | code0、无强杀、tree0、双EOF、读线程join、资源关闭、无控制台；真实SDK0 | 运行控制器（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-event-match-runtime-controller-001/build-qmt-account-event-match-runtime-001/result.json`） |

实际EXE SHA20b9f09ca5b4e24f6971ad8a0cfbda59d3e16e3601f32a09cf31224cfbe8fb6f；owned清单SHAaf39ff2b2737fd0da1f315da640b1cc59cf83e41f1daf7ba4d3861eba1c3252e。构建只含new probe、AccountEventMatch.cpp、AccountMapping.cpp三个编译单元；QmtAccountResult是只读值类型，没有Common客户端实现、HTTP钩子或新线程。分配注入只存在该独立EXE，生产模块未加测试钩子。

## 资格与后继

一次真实first-new异常证明调用失败保持原输出；本批没有覆盖全部分配点、RapidJSON CrtAllocator或所有OOM路径。逻辑额度包含所声明载荷，不等价于进程物理内存。原D/control由调用者在同步纯函数前后检查，本函数没有新TTL或I/O。

原mapper的128/115/31/142实际证据仍匹配未改mapper源，见[部分事实验证](2026-10-25-qmt-account-row-inspection.md)。当前mapper的Common/Standard整链兼容另以本次固定构建及指定回归登记，不用旧冻结mapper版本的结果代替。

完整R5后继仍需：同worker原D/TaskCredit的真实只读create/submit/resume、完整查询与原事件分别保留的P8来源入口、既有归属/去重及锁外SPI、并存峰值和停止恢复。此纯匹配片没有接入生产Factory，也没有新增持仓资金账本或人工交易资格。R8首次/重连覆盖与真实券商来源仍待验。

独立动态与兼容驱动delta已完成：报告（外部历史/待归仓路径：`../../build/qmt-event-row-match-dynamic-independent-001/REPORT.md`）。670份原件含冻结源、实际EXE、编译规则、72实际断言与回收；根逐SHA复核原件，见根收尾记录（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-match-closing-001/VERIFIED.json`）。该报告对59项兼容回归只授验证准入，运行结果由后继批次分别登记。


## 当前唯一mapper的后继整链兼容

本段使用R5c固定构建中的156份自有输入（含当前R5b唯一mapper），与前述旧R5a冻结版本分别登记。独立复核通过的身份小delta只更新输入SHA、固定路径/cache/原探针，不改变原59方法、8目标、166份Python测试或原D。追加编译沿既有CMake tree，未重新配置，快照与原匹配EXE保持；追加收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-current-mapper-compat-append-001/result.json`） SHA5a0309a7ecda1a71a09d295f4fce342ff033bb870ff6f11cff603d7068efbf05。

| 实际批次 | 结果 | 原件 |
|---|---|---|
| Common兼容 | 19/19，无失败/错误/跳过 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-current-mapper-common-001/result.json`） |
| Standard及共享内存组合 | 31/31，无失败/错误/跳过，严格19原事件场景 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-current-mapper-standard-001/result.json`） |
| 事件读取恢复 | 9/9，无失败/错误/跳过，排除继承的额外方法 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-current-mapper-retry-001/result.json`） |

三批controller均exit0、forced=false、tree0、双EOF、读线程join、resources_closed；耗时18.453/38.235/55.578秒。每批前后核156/323/166快照、cache、8份实际二进制及原EXE，源码与制品原件见根收尾（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-match-closing-001/VERIFIED.json`）。这补充当前mapper的既有完整字段行为兼容；缺字段补查/P8双来源/Standard新调度仍未接线，完整R5和R8不由59项通过推定。

当前59后继独立动态复核通过：delta报告（外部历史/待归仓路径：`../../build/qmt-account-current-mapper-compat-independent-delta-001/REPORT.md`）。758份原件包括逐方法日志/COLLECTED、8二进制与运行复制品、648输入与清单、19事件原件及四控制器回收；根逐SHA核raw一致。资格继续限定既有完整字段兼容和纯匹配，不授补查接线、R8或生产。
