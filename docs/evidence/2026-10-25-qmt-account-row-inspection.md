# 账户事件部分字段检查验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：SEV-R5b 独立纯值检查、旧mapper回归与原生编译通过；完整缺字段补查与生产查询/回报交接仍待交付。依据[标准事件规格](../specs/native-qmt-standard-events.md)的SEV-R5b。

## 实现与职责

AccountMapping 以同一 RowFacts 解码服务完整映射和部分字段检查。检查结果区分 Complete、MissingRequired、Invalid，返回16个字段位和独立的数量关系位；已知0保留为0，缺失值保持optional，非法值保原诊断。输入/输出逻辑容量与结构/分配失败走异常，调用失败不发布半结果。检查是纯值函数，原截止、查询、账户结果来源和WT回调仍由调用者负责。

旧完整映射的金融值、views、canonical、TradeID和source_to_output继续沿原入口。独立EXE包含inspection探针和唯一mapper两个编译单元；分配故障钩子仅在测试EXE，生产库没有新增钩子。原有金融、规范和事件回归先运行，再执行新增检查。

## 实际结果

| 验证 | 实际结果 | 原件 |
|---|---|---|
| 独立full与接线delta | 没有确认P1/P2；审查执行0，动态独立登记 | full（外部历史/待归仓路径：`../../build/qmt-account-row-inspection-independent-review-001/FULL-REVIEW.md`）、接线delta（外部历史/待归仓路径：`../../build/qmt-account-row-inspection-independent-review-001/WIRING-DELTA-001/DELTA-REVIEW.md`） |
| 固定原生编译 | 固定WT08b230，323份上游及153份自有输入，158构建步骤；单选NqpAccountInspectionProbe | 收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-row-inspection-fixed-001/result.json`） |
| 原金融与规范回归 | currency128、canonical115、event31全部通过 | 实际stdout（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-row-inspection-runtime-controller-001/build-qmt-account-row-inspection-runtime-001/stdout.txt`） |
| 新部分检查 | 142次：逐项删除/null/坏值、定位、关系、可选unknown与真实0、独立输出、need/need-1、异常及恢复；全部通过 | 同上原日志，原实现inspection探针（外部历史/待归仓路径：`../../tests/integration/qmt_shm_account/mapping/inspection_probe.cpp`） |
| 退出与回收 | 实际运行0.312秒、exit0、forced=false、tree0、双EOF、读线程join、resources_closed、无控制台 | 实际controller（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-row-inspection-runtime-controller-001/build-qmt-account-row-inspection-runtime-001/result.json`） |

EXE SHA256：dbdfc94c40e33d31452b483ab5daf7bc8f797cd57f3f1cbf15e22e25c22b2f34。owned输入清单SHA78461bd0a3e498fcf6793ae7d72c026f344feb30d2d1045942dc65a44326be70；上游输入清单SHAa1eba950a1bcdeb1980094ab1f29c5e8de6352e7b4a386c24ff43ff2a2092766。根在运行后复核两份快照regular文件全集与逐项SHA一致。26份框架保护文件保持本轮开始时的身份。

## 资格边界

分配失败检查实际首先可能发生在canonical_admission的结构预算；本批没有定位到每个解码分配点。RapidJSON CrtAllocator的malloc/realloc没有由global new覆盖。保留这两个覆盖范围，不能宣称全部OOM路径已验。

这是mapper级实际回归；R5a的Common19/Standard31/Retry9兼容回归使用其冻结旧mapper，各自输入有效，不能替代当前R5b对全部Common/Standard消费者的运行回归。本片尚未把缺字段结果接到真实补查、P8来源或Standard FIFO；没有新增持仓资金账本，也没有真实SDK/委托/撤单或生产切换。

独立动态证据复核通过：报告（外部历史/待归仓路径：`../../build/qmt-account-row-inspection-independent-review-001/DYNAMIC-REVIEW-001/DYNAMIC-EVIDENCE-REVIEW.md`）。35份原件含实际EXE与476项源码校验、323个原Git blob一致；实际Ninja规则证明两个编译单元，编译数据库未导出该父target，不借此虚构记录。根复核35份raw与原输入一致；范围限制保持。

后继当前156份自有输入已重新编译原8个兼容目标，Common19/Standard31/Retry9实际全部通过。见[当前mapper后继整链兼容](2026-10-25-qmt-event-row-match.md)。该结果补原既有完整字段行为的版本缺口，完整缺字段接线仍待验。
