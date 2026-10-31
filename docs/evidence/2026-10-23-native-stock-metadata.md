# 2026-10-23 原股票算法商品引用观测

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：固定上游原二进制的负向初始化观测。状态：原样引用缺额及独立核证已完成；等待两处最小修正批准，未修改框架、未测试正常销毁。

## 根因与原件

固定上游`08b230dd05facf6d650d949bfe51054115a2ecb1`的Local/CTA/ExecMon沿BaseDataMgr返回借用商品。StockMinImpact及StockVWap的init保留缓存引用，随后get_minOrderQty再次借用并release，使缓存引用被抵消。Contract.setCommInfo只赋原指针，未增加商品引用。首次完整静态审查（外部历史/待归仓路径：`../../build/guanheng-workspace/native-execution-lifecycle-static-review-001/STATIC-REVIEW.md`）共23组：17静态结构符合、1缺口、5未实现/未执行边界；56原件根核一致。

观测源码（外部历史/待归仓路径：`../../tests/integration/native_stock_metadata_ref/README.md`）只编译一个自有cpp，调用原DLL的createExecFact及原Unit.init。使用原WTSHashMap.add(false)/get复现同一借用语义，不增加保命引用、不按调用次数改变getter。主程序没有WT库链接或WT目标；原算法实现来自已核原WtExeFact.dll。

## 实际结果

| 原算法 | init前引用 | init后引用 | 缓存正常持有时应为 | 商品getter次数 | 业务调用 | 诊断退出码 |
|---|---:|---:|---:|---:|---:|---:|
| StockMinImpact | 1 | 1 | 2 | 2 | 0 | 10 |
| StockVWap | 1 | 1 | 2 | 2 | 0 | 10 |
| 普通MinImpact对照 | 1 | 2 | 2 | 1 | 0 | 0 |

三个独立cwd/进程的原始observation.json及受管收据保存在`build/native-stock-metadata-ref-001`，case-results.json只索引实际数值。股票case的10为预先声明的负向诊断码，不是委托错误或崩溃。StockVWap使用合法非零total_times，仅经过引用相关初始化片段，不提供真实VWAP文件、不授完整算法就绪。

所有case写入并关闭结果后主动_Exit，绕开尚有引用缺额的析构路径。因此本轮证明初始化引用缺额；销毁后的悬空访问仍属静态推导，没有宣称发生动态崩溃或正常停止已通过。普通对照也使用相同_Exit，退出0不授完整生命周期资格。

## 来源、窗口与回收

原DLL SHA `a6610d0d7838688fb4061eae74ecf338aeb26c389b9781f553e5739901961dbd`；探针EXE SHA `e67c59da5a69e29b70c05214da350a0b5a28ed9b0d38906245ab017756a065ff`。CMake compile_commands只有metadata_ref_probe.cpp一个单元，实际配置为MSVC19.51/x64/Release/动态CRT；新旧357上游文件全部匹配。编译含原头的WIN32_LEAN_AND_MEAN重复定义警告，未改原头。

仅恢复该单文件编译，使用已验hidden_build私有隐藏控制台及冻结ProcessJob创建期绑定；编译6.047秒自然exit0，三诊断各约0.09秒、未强杀、Job成员先于resume、父PID及管道均回收。顶层console不存在，原生探针自检无可见控制台；2GiB编译/512MiB单诊断及有限输出预算分别登记。完整WT构建、浏览器、终端、网络和真实交易均未启动。

## 后续范围

两处最小[修改提案](../migration/native-stock-metadata-ownership-proposal.md)已准备，待独立复核后提交批准。原框架文件继续冻结；不会把临时retain、getter调用次数特判或换算法作为缺额修正。批准后才可构建候选并验证引用平衡、原数量规则及完整停止链。

## 后继：独立核证与审批状态

独立核证（外部历史/待归仓路径：`../../build/guanheng-workspace/native-stock-metadata-ref-review-001/EVIDENCE-REVIEW.md`）已complete，仅授固定原DLL的初始化引用诊断。55原件、49索引原件及361构建输入均核对；根任务另逐项核55原件与当前来源，差异0。审查入口SHA `ba4e3afcf9397518c16e0d14a670bfe0ffe828ab6bfbc77ccb9f544f1adc54a4`，报告SHA `e441e3775b628a6d6abb0f28420e01ef4f1396bbf097f083fd69a69a2dee1ce4`。本次独审复用原始实测，未新增进程；正常析构、崩溃和完整产品资格继续未验。

收据没有持久化实际cwd或顶层Node创建flags字段，独审明确保留这项启动来源元数据unknown，不以目录名补造。已有源码传参、启动器console自检及程序无可见控制台断言分别保留；该缺项不改变引用计数诊断，无须为此重复原观测。后继新入口补齐启动元数据，原收据保持原样。

已向用户提交两个头文件的最小辅助函数修正请求及确切差异（外部历史/待归仓路径：`../../build/native-stock-metadata-ref-001/proposed-framework-change.diff`）。当前等待批准，框架尚未修改；账户只读SHM契约梳理独立继续。
