# App托管原生执行进程验证

类型：开发、独立安装和实际隔离链验证。状态：done（EAM切片）；模块C/M1整体继续in-progress。规格：[EAM](../specs/execution-app-management.md)。真实QMT操作、真实下撤单与生产切换0，新增WT核心行为0。

## 根因与正确实现

B已交付原生产品及ManagedExecutionProcess，App此前只托管账户、采集和历史查询，执行进程仍须独立手工装配。新父部署门面绑定安装/原生配置摘要并消费B唯一ExecutionProcessConfig；App启动前发布原owner，沿现有读取池/_start_process启动，关闭纳入统一截止和CLI结果。

关闭依赖顺序为读取消费者→执行→历史查询→采集→账户Host；部分启动及单组件关闭失败保持其他owner回收。默认不启动Job。新只读状态接口取当前owner白名单，系统状态卡支持刷新及失败隐藏旧观察，资格固定not_checked/recovery_ready=false。策略目录继续仅展示名称、简介、版本。

## 固定身份

- 原件根`build/execution-app-001`。Appa8 wheel SHA256 `4bc45f70c84e461a83574db806206490d345127934b45b82f38532ef2f45692b`；49个App构建输入及副本见app-source-sha256.json/app-source，47个运行文件与实际安装匹配。新Python3.12.14环境21包检查通过，SDK0.14及最终纯包002沿固定摘要安装。
- B组件002 SHA256 `1fe7e1f540a179095400fa3b30555510ced7eb36c998afb11a11701d7d02a168`；native_install逐文件核验。冻结B夹具来自ms-business-001/final-input-002，原CTA/SDK断言保持；合成策略/Parser/Reader各自SHA保存于原件。QA运输使用已核A039闭包，不加载真实券商。
- native.py仅把冻结B夹具的start/close映射到实际已安装App；App内部实际owner类型仍为B原ManagedExecutionProcess，配置加载/启动/关闭均走生产实现。App/SDK模块实际路径位于新安装环境。测试替身只承担合成策略、行情和SDK源事实，金融目标/组合仍走原CTA及执行器。

## 实际调用链与结果

实际App→B原生exe→原Factory/CTA ticker→A600/B400→原组合/唯一执行owner→执行器/Adapter→真实Host/WinSHM→SDK替身。

| 场景 | 结果与原件 |
|---|---|
| 正常主链 | 一次替身买1000，A600/B400，四查询；native-run/RESULT.json、NATIVE-APP.json |
| 生产SPA错误/恢复后同链 | 保持同PID，GET503注入后隐藏旧状态/PID，解除后恢复；仍一次替身买1000及四查询；native-recovery-run/RESULT.json、NATIVE-APP-recovery.json、browser.json |
| 已有状态拒绝 | 四查询、零替身委托、原文件字节保持，首unexpected_exit保留；native-failure-run-002/RESULT.json、NATIVE-APP-failure.json、faulted-browser.json |
| 实际关闭 | 正常轮次Appshutdown_complete=true，原Job/整树/双EOF/readersjoin/reaped确认，两个App读取池线程0、监听关闭、pending/forcedfalse |
| 失败归约 | 已有状态拒绝轮次资源同样归零、监听关闭；shutdown_complete=false保留原失败结果，不授正常退出或自动恢复资格 |

本次验证原生exe路径。冻结B夹具的actual_installed_runtime_dll=false表示未选择Python callback分支；正式Python业务桥和该分支保持未验，组件内存在DLL不扩大本次资格。

## 界面与回归

Browser plugin not available；现有Playwright/Edge，实际生产SPA和HTTP，1440×1000及390×844。生产页面显示原进程PID、“已启动”及资格说明，刷新全GET；名称简介版本目录正常。503注入仅拦状态GET，预期资源错误与意外错误分开；解除后恢复同PID，意外错误0。原生启动拒绝页面显示失败和未知PID；窄屏无横向溢出。截图在本会话visualizations/execution-app-001，desktop/mobile/read-failure及faulted对应原件，桌面已人工查看。

121项后端回归覆盖父部署58项、App默认/启动失败/构造失败/关闭异常、原来源/Host公共生命周期；28项前端覆盖独立壳、执行卡、刷新/错误/恢复；TypeScript和生产构建通过。加载器专项真实文件5项与58项完整组为包含关系，分别登记。所有命令经原native.run隐藏Job、有限D/输出及资源收束。

初次native作业缺少QA的Host/source导入路径，在创建交易夹具前结束；补用固定A039测试闭包后主链通过。首已有状态作业的QA错误要求退出后PID仍非空；父实际正确报告未知，修正QA后二代通过。失败目录保留，产品未为测试新增特判。

两名独立审查者分别完成EAM full。规格审查曾标记生产SPA错误恢复缺证，补上同原生链的503→隐藏→恢复后delta complete；规范full无P级问题。16文件产品清单review-sources.json前后一致，App/B制品身份保持。最终来源/证据SHA随DELIVERY冻结，文档检查通过。

## 剩余范围

B正式Python业务桥、真实业务核的同BT/RT对照、金融目标/绩效公共投影、撤单/异常恢复及完整M1继续；源单位、闭合知晓及实时准入沿A/B事实核实。统一安装升级回退、全部保留版本/独立观察和完整操作材料继续模块C。没有发布或关闭完整goal。
