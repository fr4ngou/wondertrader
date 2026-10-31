# 当前国信QMT与共享内存来源分层诊断

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：只读现场证据。日期：2026-10-26。状态：进程/指定监听分步观察完成并独审；策略状态、Host加载源码及配对代际尚未核实。

## 已确认的现场范围

2026-10-26T00:19:47Z写出的单次收据记录以下元数据。Toolhelp、IPv4/IPv6 LISTEN表和目标句柄查询分步完成，结果不作为原子进程/监听快照。只选两个进程名称和三个端口，不读取命令行、环境、配置、日志、窗口正文或SDK。

| 对象 | PID / 父PID | 当前image路径 | 会话 | 创建UTC |
|---|---|---|---:|---|
| 国信终端 | 25144 / 48748 | D:/software/guoxin/bin.x64/XtItClient.exe | 1 | 2026-10-22T11:53:24.959Z |
| 报价进程 | 6272 / 25144 | D:/software/guoxin/bin.x64/miniquote.exe | 1 | 2026-10-22T11:53:41.806Z |
| 18017监听进程 | 41336 / 30964 | C:/Python314/python.exe | 1 | 2026-10-23T07:25:50.380Z |

18017监听PID为41336，58610和58341均为6272。进程名/路径、创建时间与会话仅描述该次观察；Python镜像不能证明其加载本仓Host源码，也不能据进程仍在判断QMT策略在运行。端口归属不证明Full QMT下载缓存映射或58341服务协议，未尝试替换端口。

2026-10-26T00:33:30Z单次GET 127.0.0.1:18017/health为HTTP200、status unavailable、profile restricted-read-only、order_ready false、reason OSError。仅输出固定白名单字段，SDK操作0，见健康原件（外部历史/待归仓路径：`../../build/qmt-source-diagnosis-001/LIVE-HEALTH-CURRENT.json`）。该结果与终端/报价/Host进程存在同时成立；当前尚缺原策略回调、配对/代际和认证失败阶段，故本轮没有发历史窗口或账户交易请求。

## 实际执行与审查

metadata probe002及controller已逐源静审；001跨行字符串及GetProcessTimes未退出时undefined字段判断两处问题已在运行前修正。GetExitCodeProcess的259仅保留其有限观察含义。候选仅临时诊断，不增加产品服务/队列/数据库。

根实际保留Node句柄11068与controller PID一致，child11468直接使用固定base Pythonw；child和外层均exit0，外层253.548ms，原30秒D/子映射至多10秒，2GiB Job、首stdout/stderr各64KiB。stdout959字节、stderr0；无forced，Job树0、双EOF、reader join、句柄关闭均确认。probe和controller前后SHA保持，完整FILETIME以十进制字符串保存。见根收据（外部历史/待归仓路径：`../../build/qmt-source-diagnosis-001/METADATA-ROOT-VERIFIED.json`）。

probe静审（外部历史/待归仓路径：`../../build/qmt-live-source-metadata-independent-001/static002/REPORT.md`）、控制器静审（外部历史/待归仓路径：`../../build/qmt-live-source-metadata-independent-001/controller003/REPORT.md`）及实际原件独审（外部历史/待归仓路径：`../../build/qmt-live-source-metadata-independent-001/dynamic004/REPORT.md`）已通过，21项检查无新增P1/P2。原WinAPI资料和源码身份随审查封包保存；实际Node句柄事实来自根保留对象，独审按根收据与controller原件交叉核实。

## 下一步与边界

继续核现有运行制品、策略回调及Host配对代际，再准备可审阅的恢复材料。终端重启、策略替换/重新配对和活动Host切换须沿明确操作授权；本轮保持现场实例。历史数据继续按[缓存映射调查](2026-10-26-qmt-external-quote-path.md)处理，已下载文件仍在，外部SDK的空结果不足以判定数据不存在。本轮没有操作真实委托、删除数据或切生产。

## 后继只读健康观察

2026-10-26T01:23:56.759Z在隔离回测UI验收结束后单次GET原18017/health，6.004ms、HTTP200，仍为unavailable、restricted-read-only、order_ready=false、reason OSError。只输出白名单；SDK行情/历史/账户请求0，未改变终端、策略或配对。原进程元数据仍保其00:19采样语义，本次健康不追认当前加载源码或具体共享内存失败阶段。见后继原件（外部历史/待归仓路径：`../../build/qmt-archive-retry-continuation-001/LIVE-HEALTH-AFTER-UI.json`）。


## 用户截图与实时界面后继

2026-10-26，用户指出策略尚未运行并提供截图。根随后以computer-use读取真实国信QMT主窗口，确认QMT_METRIC_GATEWAY和GH_WT_MEMORY_VERIFY均显示待启动三角控件；此前进程/监听检查缺少这一层。GH_WT_MEMORY_VERIFY磁盘正文SHA e105005f871e63de6f35590b308335b47c1f6120cae32c312e7d65ac510c80ec与已验账户004精确匹配，只允许账户四查询及full_tick，无下单/撤单。当前尚未点击运行，正核本仓独立配对Host及安全启动顺序。18017属于另一旧行情安装，不能据其健康推断本仓18018强绑定来源。策略未运行已确认；成对启动后的实际回调和读取仍须验证，现阶段不把OSError归为共享内存协议缺陷。


## 首次恢复实际结果后继

已在QMT实际单次启动GH_WT_MEMORY_VERIFY，执行策略计数0→1；配对18018未取得绑定或tick，真实读取请求0，本次Host正常关闭。查看运行页后界面工具连续failed to activate captured window，已停止界面输入并请求用户仅停止该策略，结果待确认。连接时序根因仍待实际运行错误与精确时点核查；[首次恢复证据](2026-10-26-qmt-existing-strategy-restart.md)保留原件、实际退出及范围。
