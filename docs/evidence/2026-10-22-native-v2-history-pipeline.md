# V2历史行情到原始目标组合验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-22。范围：[NVT](../specs/native-v2-history-pipeline.md)及[NFA a3扩域](../specs/native-fixed-unit-allocation.md)。状态：开发、独立安装和开发回归完成；最终源码冻结，另一作者独立full进行中。完整策略、原生执行及真实来源尚未完成。

## 实现与复用

独立包`guanheng-strategy-v2==0.1.0a1`实际调用SST a2从历史产生信号，再调用NFA a3形成原始目标，固定原a5和tzdata2026.3依赖。两个profile沿各自历史起点，保持全部证据与原顺序。组合JSON保留完整分配和有限末特征，不重复嵌入整份信号历史；完整不可变信号及分配原件仍通过公开属性读取。

NFA a3保留v1每条8项、每项128字符输入域，新增明确v2的17项、256字符域，完整容纳SST输出。公开预算在每个入口重新快照复验；分配数学和原始总权重1.125保持。联合计算使用同一monotonic期限，各阶段传递剩余时间。策略预算作为配置，无新资本账本或逐单人工审批。

## 安装与实际开发验证

在C:/Python314的两个全新非editable隔离安装中核对9项NFA源码、13项安装文件，以及4项组合源码、682项安装文件；wheel源码成员和安装内容相符，pip重写的RECORD按安装收据单独核对。安装与运行无旧QMT源码依赖。

| 项目 | 实际结果 |
|---|---|
| NFA公开入口 | 148项通过，含旧数学/时间及新证据域、全部预算字段坏值和缺项 |
| 安装后的V2组合 | 14组通过，含双profile实际SST→NFA、可手算三灯、证据原序/重复/Unicode、空与dated-zero、历史上海偏移/夏令时、身份/不可变、单总期限 |
| 密集容量 | 4096日产生4096条信号和4096次分配，规范结果4,644,005B，本机约3.021秒 |
| 其他联合边界 | 1250日八角色通过；32768行先触发完整输入字节上限；4097日、收紧输出和10ms期限明确拒绝 |

容量与期限为本机观察，不承诺所有合法最大输入都在5秒内完成。8MiB是各次完整输入/输出字节预算，不能解释为进程总堆内存上限。

NFA wheel SHA：`2d7f8d71b5e7cb1ecda68ac82ad208c73faefc0072728713e09c72996476806b`；组合wheel SHA：`cd8cd1296264cae6a29674dc85c2f4fdc9ca67347bd4affc510f91fdc3483b30`。实际解释器、安装及依赖身份分别在`build/guanheng-workspace/v2-history-pipeline-001/installation-receipt.json`与`pipeline-installation.json`，结果在`nfa-installed.xml`、`tests-installed-002.json`及`capacity-results.json`。

## 冻结与剩余范围

最终审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-history-pipeline-001/final-002/review-inputs.json`）SHA为`a7360ac6ab5bda307cca1cbe59b761010c86dbfd356691765039043a4725292c`；752项清单（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-history-pipeline-001/final-002/artifact-manifest.json`）SHA为`80508a20811e25c47759e04df9bdeabe87a8706b56e22f0425052c329655dc67`，另含3项外部运行身份。final-001为未完成的冻结尝试，仅保留记录，不作验收入口。

独立full按另一作者预先冻结的27组矩阵开展，开发者测试结果仅作入口定位。当前不授独立审查通过资格。后继仍需明确V2原始超额目标的数量接线语义，并真实贯通NSQ、原生NSB/CTA、业务HTTP和中文页面；真实来源、账户、交易及生产逐项验收。当前结果的source_qualified、historically_produced、execution_qualified均为false。

## 后继：独立full完成

以上审查待验状态由本节更新。独立full报告（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-history-review-001/FULL-REVIEW.md`）结论complete，27组矩阵完成，新增gap为0；报告SHA为`5d323baaae71d63fd7d171d908a4e81612771dc3ad05c9db959c43bb4d55ccd5`。另一作者从冻结源码重新构建两个wheel，成员字节与作者构建相同，独立noneditable安装重跑148项NFA和14组组合测试。

另有1129项自主观察、100组Fraction人工分配oracle、14个快照后修改隔离案例通过；32组旧a2与新a3的v1完整规范输入/输出字节相等；4组双profile/ragged长历史共364条decision与公开模块组合精确一致。由原始历史实际产生信号并构造出原始总权重1.125，未改算法或授执行资格。包故障、预算、期限与联合wire上限分别取得实际结果。

根任务已逐项回核840项原件清单（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-history-review-001/artifact-manifest.json`）、5项运行身份及当前29项源码，全部相符；清单SHA为`6465f2e231501eca5a013f2b7690eae99a1c7e7f9872d93d3efb93c340513fcc`，回核收据在`build/guanheng-workspace/v2-history-pipeline-001/full-review-integrity.json`。

此结论授固定NFA a3及NVT a1的纯计算组合范围。完整producer准备、真实历史来源、数量接线、NSB/CTA、实时、共享内存、券商及生产继续按原要求逐项验收；完整观衡迁入目标保持active。
