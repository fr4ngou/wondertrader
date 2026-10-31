# 模块B执行组件的永久源码干净构建

类型：开发构建手册。状态：implementation-in-progress / pending-verification。
范围：标准Trader、原执行工厂、受管策略桥、CTA Runtime/Host及它们的静态依赖。
完整模块资格沿[模块B交付](../migration/module-b-delivery.md)，构建通过与安装后业务
验证分别登记。要求为[NRT-R7-C1–C4](../specs/native-realtime-strategy.md#nrt-r7-结果与独立发行)。

## 输入和批准范围

永久入口为[scripts/execution_product.py](../../scripts/execution_product.py)，唯一清单为
[execution-product-build.json](../../config/execution-product-build.json)。自有源码取自该
清单列出的永久目录；WT取固定Git对象，叠加[既有执行覆盖](../../integrations/wondertrader_execution/README.md)
和已批准的股票借用引用覆盖。覆盖的原字节、允许文件及最终内容摘要全部核对。
原工作树内其他冻结WT差异保留在原处，构建不读取它们。

原桥的相对include需要相邻WT头。构建器将同一已验证WT快照镜像进owned输入，
每份镜像保持批准后的原摘要；它们属于固定上游来源，永久自有源码检查另列。
公共查询结果新增快照消费标志后，账户结果384字节、原票据136字节；标准交易
内存银行沿实际sizeof计算，并以当前布局阻断混编。

第三方依赖只接受[锁定清单](../../config/native-dependencies.json)的官方源码压缩包，
逐包核SHA并在新构建根重新解压和完整复核。Boost/WTSTools/WTSUtils/WtCore等本次
实际链接库由新目录中的源码重编；Windows系统库沿原MSVC工具链使用。
已有build中的项目obj/lib/DLL不作为新构建输入。

## 执行

在仓库根执行以下入口，`--work`必须为全新E盘目录且父目录已存在。所有临时、依赖
源码、对象、库、安装结果和日志均位于本次根。已有C盘解释器和MSVC仅供执行。

```powershell
C:/Python314/python.exe -I -B scripts/execution_product.py `
  --work E:/workspace/wondertrader/build/execution-clean-001 `
  --archives E:/workspace/wondertrader/build/native/downloads `
  --seconds 1800 --jobs 2
```

正式自动批次按[隐藏Job手册](build.md#后台构建的窗口与日志)置于有界进程所有者内；
不要从观察超时推定构建结束。`--seconds`为本次构建操作预算，外层Job保留其明确
回收预算。入口把工具链探测、固定Git和依赖准备/复核各自装入受管Job，均使用
本次剩余截止；超时先由原Job回收该阶段全部后代，后续阶段停止。失败根保留原件，
后继使用新目录。

## 输出和验收

`SOURCE.json`登记永久自有源码和批准覆盖；`inputs/`保存实际编译快照；
`COMMANDS.json`及逐阶段日志保存命令和结果；`cmake/`保存本次对象和库；
`installation/`为全新安装输出。最后的`RESULT.json`绑定安装文件以及本次实际
项目链接输入。原永久源码、固定快照和依赖源码在构建后再次核对。

五个实际运行组件各自生成[绝对显式输入收据](https://learn.microsoft.com/en-us/cpp/build/reference/link-repro-full-path-rsp?view=msvc-170)，
并启用[实际库搜索输出](https://learn.microsoft.com/en-us/cpp/build/reference/verbose-print-progress-messages?view=msvc-170)。
本机MSVC的真实pragma DEFAULTLIB样本确认，显式收据会省略该隐式库；因此验收同时
读取两类实际证据，不用生成命令清单代替链接闭包。工具链环境只保留明确字段，
库路径限定本次构建及本机VC/SDK，外部CL/LINK等选项退出构建环境。

成功要求完整Host依赖链从全新目录构建、五个运行组件及公开头/静态库安装齐全、
项目链接输入全部来自本次构建目录。随后仍须执行普通安装主链、关闭恢复及独立
审查，方可形成模块候选资格。此入口不启动业务Runtime、连接账户或调用SDK。

旧P30候选曾复用14份对象和旧库，其业务证据保留在原身份下；该候选不能证明永久
源码干净重建。当前永久Standard源码已纳入此前独立验收的P30准确字节，新的构建
和安装证据按本手册后继补齐。
