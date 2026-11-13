# 原生 Reader 离线构建

类型：构建规格。状态：implemented，运行资格以本次制品证据为准。范围：NMR 分钟组合器、显式连续日线发布读取，以及其原 WT 库依赖。

## 源码与选择

`config/native-reader-sources.json` 声明 Git `08b230dd05facf6d650d949bfe51054115a2ecb1`、19 个既有批准覆盖的原/新 SHA-256，以及 Reader 自有源。构建直接取得 Git blob 并核 Git 对象摘要；覆盖只取声明的永久材料并核摘要。共享工作树的上游 `src` 不作为输入。批准依据仍为上游覆盖登记、原 CTA 停止、订单查询同步和股票元数据所有权规格。

原版 `WtDataStorage.dll` 使用固定基线；显式 NRC 文件从独立快照编入 `app/nrc/WtDataStorage.dll`；`--writer-lifecycle` 通过既有已批准 WLC 材料生成独立 `WtDataStorageLifecycle.dll`。三个选择各自保持文件身份，默认原版保持。组合器本身沿原 `minute_native` 和 `daily.publication` 配置选择读取路径，保留缺省 HTTP 分支。

## 构建闭包

公开入口 `scripts/native_support/reader_product.py` 要求新工作目录、显式离线依赖归档目录及工具身份文件。工具身份文件绑定 Python、Git、MSVC cl/link/lib/rc/mt、CMake、CTest、Ninja 的绝对位置和 SHA-256；执行前后核身份。固定 Git 对象须预先存在，构建禁止延迟下载。依赖来源、版本、归档摘要、展开文件集合和许可证沿 `config/native-dependencies.json`，本入口始终使用离线模式。固定 Git 内嵌依赖的通知与补充完整许可证由 Reader 源声明绑定并随安装保存。

窄 CMake 入口 `cmake/native/reader_product` 从同一快照实际编译 WTSUtils、WTSTools、WtCore、WtDataStorage、WtDtHelper 和 Reader。它不输入预编译 WT 静态库或对象文件。原 WT CMake 负责原组件编译，自有 CMake 负责依赖传播、MSVC 编译选项和独立安装目录。

输出包含普通安装文件、许可证、上游/自有/NRC/WLC 输入清单、命令、工具清单和 `BUILT.json`。每次构建使用新目录，失败保留原记录；任何改动的源或工具身份须以新构建收据重新表达。

`--seconds` 固定本次原截止。阶段准入、同步阶段返回、命令启动/返回及成功发布均检查同一截止；到期拒绝后继工作和成功收据。Git/工具环境等同步调用沿复用工具自身的有限等待，入口在返回后核原截止；本参数不声明能抢占同步文件读写。外层受管 Job 继续拥有进程生命周期和最终回收。

## 验证与边界

主链从安装 DLL 的公开工厂初始化、读取冻结历史原值和时间、分钟通知、显式连续日线更新，再停止并释放。连续日线沿同一原 CTA/WtDtMgr 读取已验发布样本。静态样本证明本次 Reader 及其依赖的可重建和读取资格；原实时写入、多进程并发、交易、完整 P30 执行系统和生产资格各自独立。

分钟回调沿原 sink 交付。逐证券闭合回调抛出异常时记录标准证券代码、K 线分钟和原异常；异常继续沿原 Reader 路径处理。整批分钟结束阶段的错误记录原截止时间。

必要边界包括原 NRC 数量回归、分钟配置与停止准入、缺省 HTTP 兼容、日线坏发布保持旧事实/旧切片释放，以及构建输入身份拒绝。自有构建层的问题在接线层修正；新的上游行为修改须另行批准。
