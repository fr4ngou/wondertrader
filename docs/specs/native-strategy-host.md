# 隔离策略回测的受管父宿主

类型：功能最终规格。状态：accepted。前缀：NSH。细化[NSK-R5](native-strategy-kernel.md)与[NSB](native-strategy-backtest-session.md)的进程边界；业务核、阶段转换和原生撮合继续由各自模块承担。

## NSH-R1 固定入口与输入准入

父宿主只启动受管安装中的固定策略runner模块，Python解释器、业务模块、纯核、数量包、原生DLL和ABI探针身份来自显式受信安装绑定。HTTP参数或输入行情不能指定任意命令、可执行脚本、模块、DLL或工作目录。使用绝对路径、固定argv、shell=False和隔离Python搜索路径，禁止旧QMT源码/环境注入。

每轮取得全新独占UUID目录。冻结完整会话输入、原生基础资料及身份，JSON拒绝重复字段、非有限值、过深嵌套、未知结构和超限内容；不执行输入中的Python代码或动态loader。请求显式含schema、run_id、输入摘要及资本/费用/来源，子端在加载原生前复核。启动前目录和文件准入拒绝逃逸路径、symlink及Windows reparse；子端只访问本轮合格冻结字节。输入/输出/原生文件及全部等待有明确可收紧上界，超限保留中文原因。

## NSH-R2 单一期限与进程所有权

创建、输入准入、复制/校验、启动、运行、输出核对、关闭和wait共用一次monotonic绝对截止。预算开始后不另起完整重试期限；异常清理也使用剩余预算。纯核5秒协作截止与父宿主期限分别成立。

Windows子进程CREATE_SUSPENDED，成功归入独占KILL_ON_JOB_CLOSE Job并核membership后才Resume。父死亡、异常及取消均不能留下仍执行native的孤儿；启动/Assign/Resume失败必须停止并回收自有挂起子进程。所有线程、句柄、管道和强引用有明确owner。root退出后仍对尚存后代持续检查取消、管道及目录容量和原截止，不以阻塞整树wait暂停这些守卫。线程owner在start前保存；start异常且bootstrap尚未确认时保留未知，禁止从ident缺席或is_alive=False推定未创建。线程入口或start正常返回只授标准join准入，全部标准join证明取得后才释放管道、Job资源与运行根lease；每次等待共用原绝对截止。禁止停止其他QMT/WT进程、扫描终止同名程序或热卸载DLL。

CreateProcess写出的PROCESS_INFORMATION须在调用前已由资源owner持有，避免成功返回至Python再次转交之间的异常丢失process/thread原始句柄。该窗口中断时保持真实pid/句柄，关闭Job后仍按同一剩余期限等待自建进程并释放句柄；不得以尚未复制到普通属性为由报告无进程或跳过wait。原API成功返回前后及线程/管道后继窗口分别保留故障证据。

产品优先采用创建时Job列表属性，消除CreateProcess返回至单独Assign之间的用户态窗口；本Windows profile要求支持该接口，能力缺失时拒绝启动。管道继承使用显式handle列表，Job句柄不继承。依据[Microsoft的UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)和[进程创建说明](https://learn.microsoft.com/en-us/windows/win32/procthread/creating-processes)，JOB_LIST支持Windows10/Server2016及以后；实际父死亡窗口仍须测试，不把接口说明扩大成所有内核创建中断阶段的完整结果保证。

父宿主每owner最多1个活动运行、零隐式排队；重复/并发请求按明确身份复用或返回繁忙，不自行执行第二份原生任务。断开一个展示等待者不自动重跑；主动取消由运行owner处理并标中断。多进程共用同一运行根时取得OS排他准入锁，正常释放在child wait之后；父死亡遗留目录保持不可发布，后继使用新UUID。

## NSH-R3 有限通信与完成协议

stdin不承载任意代码。stdout/stderr分别有有限字节预算及排空线程，超限中断并保留诊断；不将原生stdout日志误当JSON成功帧。子端在本轮根写有限、原子发布的结构化结果，绑定run_id、请求/安装身份、会话report及所用原生输出；父端重新核对。

只有非forced、子进程exit0、结果身份/内容验证通过、原生输出在预算内、进程已wait且管道结束，才能返回completed。退出0、存在旧结果或只有completion字段分别不足以确认成功。native提交中断、结果缺失、协议/身份错误、取消、超期或资源回收未确认均返回incomplete及原因，原目录保留并隔离，禁止发布部分目标为完成回测。

## NSH-R4 容量与结果消费

输入、单轮原生目录、结果JSON、管道、累计保留目录和活动运行均有显式预算。父宿主不自动删除历史文件；容量满时拒绝新运行并显示所需处理。无账户/订单/成交数据库或新的任务事实账本。

公开结果为不可变运行投影，区分completed/incomplete/busy及来源/模型资格；后继业务HTTP/页面消费受管结果，不直接加载DLL、调用native上下文或自行解析未完成目录。真实QMT来源、RT、实盘与生产发布按各自资格和授权处理。

## NSH-R5 验证

独立安装产品贯通NSB真实原DLL小样本，逐日核完整策略输出及原生CSV。异常包含输入/身份/路径/重解析点、重复和并发、启动/Assign/Resume各失败窗口、父在DLL前/后死亡、超期、取消、管道满/不结束、exit0但缺/旧/畸形结果、提交前中后中断、输出预算及目录容量。实际OS句柄与进程证明回收，不以日志或标记文件代替。

首次full独立审查；固定反例修正按实际影响delta。产品、安装包、实验及生产分别登记，不用单个happy-path或测试工具的Job证明整个宿主生命周期。

## 完成原件的后继只读归档

[NBW-R6](native-backtest-workspace.md#nbw-r6-已完成回测只读归档)复用本宿主既有UUID原件。HostResult在真实退出、reap/join和最终清理事实成立后返回；持有该结果的业务责任层才可发布完成receipt，禁止从子result.json反推父完成。归档状态与原执行状态分别显示，发布失败不修改HostResult事实，不重新执行；新归档实现不扩大NSH的来源、执行或生产资格。
