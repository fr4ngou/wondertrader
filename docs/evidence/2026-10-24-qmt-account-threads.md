# QMT账户身份消费的线程分工验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-24。范围：[STQ-P8](../specs/native-qmt-standard-trader.md#stq-p8-账户消费的线程分工)。状态：本切片通过；标准交易插件、事件消费、恢复、正式安装及生产继续开发。

## 实现与原因

原账户身份入口在同一线程完成WT金融对象构造和HTTP关联查询。标准插件需要一个I/O worker与一个WT owner，故将同一实现拆成begin/resolve/finish：owner调用唯一mapper并持有Candidate；worker只接受独立值Plan、产生独立值Resolved；owner验证原批次/线程/截止时点后统一写原WT身份槽。原顺序入口复用这三阶段，金融规则和原UserTag语义保持。

错owner或错ticket同时保留两个句柄，正确owner能继续完成。Candidate销毁仍由调用者保证在原owner；模块不替调用者调度析构。原deadline.end和累计预算跨阶段连续，stop可先在owner退役WT候选，晚到worker结果只销毁独立值。没有新增WT框架修改。

## 实际结果

- 六目标构建（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-thread-build-001/identity-build-result.json`）通过，编译来源无漂移。目标只含自有Common/mapper和测试，不以该一般构建授予WT核心或标准插件资格。
- 六组原生CTest（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-thread-native-001/ctest.log`）全通过，65.81秒：codec、原生交易客户端、故障、账户投影、身份、旧金融映射。身份15方法展开73场景，其中原57保持、新增16；旧金融128场景保持。
- 独审指出timeout-finish未明确证明前一阶段成功，测试增加Resolved.status.ok先决断言。最终受影响身份组重验（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-thread-regression-003/ctest-identity.log`）通过，25.41秒，最终来源无漂移。产品源码未因该测试修正改变。
- 新16场景覆盖真实不同std::thread的I/O resolve、原owner finish；销毁原输入后独立值；错owner/错ticket双保留；原D在resolve/finish两窗口过期；累计预算；owner退役候选后的晚到纯值释放；双消费。成功数组在worker已drain/join后仍可读取金融值和原WT身份。
- 原生客户端组继续实际通过认证Host/Win32 builtin-SHM到原策略线程SDK替身的四查询、下撤单和原ID恢复。新增跨线程场景使用真实认证HTTP合成fixture；实际券商SDK调用0。
- 本轮Python产品代码未改，前轮529/目标3.6.8兼容结果保留其原输入资格；本轮没有重复宣称重新执行529。改变的原生测试已由上述CTest实际执行。

## 独立审查与来源

full及最终测试delta审查（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-thread-review-001/NOTES.md`）complete-static，最终P1/P2为0；Reviewer执行0。根对27项来源逐项核同（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-thread-final-001/REVIEW-ROOT-CHECK.json`），无漂移。P9候选插件在该审查范围之外。

最终汇总（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-thread-final-001/SUMMARY.json`）保存最终身份DLL摘要。四份成功控制器（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-thread-final-001/CONTROLLERS.json`）均证明无协调器控制台、Resume前已入Job、退出码0、自然结束、tree0、管道EOF、reader join及资源关闭。

构建/报告采集期间的旧测试夹具配置与临时驱动字符串错误保留在对应工作目录，最终通过结论只取上述成功输入；未重写失败原件。

## 固定上游拒单语义诊断

独立固定原版诊断（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-rejection-verify-001/result.json`）从08b230dd原Git blob编译真实TraderAdapter，无框架覆盖。四场景复现：同步orderInsert返回-7后买/卖undone分别残留+100/-100；后继原onRspEntrust(error)均使其回0，持仓1000不变。真实SDK/网络均0。

该结果证明适配器必须完整交回原生失败通知；没有证明WT在所有券商插件下普遍失败，也没有授权框架修改。标准候选插件的确定未提交错误、unknown与有限队列行为仍须按真实调用链验收；必要核心修正另提证据和批准。

## 剩余范围

生产Factory仍创建旧ManagedTrader。StandardQmtTrader及其真实候选工厂正在接线，尚未完成实际Adapter/SPI/关闭验收、事件重复消费和查询交接、重启恢复。完整独立发行、真实终端非空委托/成交字段、授权真实下撤单及保留观衡入口分别待验；整体目标active。
