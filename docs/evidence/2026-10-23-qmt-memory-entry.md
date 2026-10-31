# 2026-10-23 QMT 无文件策略接入

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：当前接入验证记录。状态：pending-verification；自有候选开发与隔离验证，券商终端安装及真实资格待验。

## 依据与职责

用户指定的后继接入手册与此前归档原件 SHA 相同：`0d476afe88802f84f5f4a7ddf4f6e92b7edeb01e24498da22f3df552db4cad6a`。完整核对见[来源交接](../migration/qmt-successor-source-handoff.md)，最终行为见[QSW-R12](../specs/qmt-shm-wt-binding.md#qsw-r12-受限终端无文件启动)。

终端外生成器冻结本仓 Agent、目标 CPython3.6.8 标准库、许可与配置，输出 ASCII 策略正文及逐字节身份；终端内私有加载器只消费内存源码和真正内建模块，传输使用内建 mmap。外部 Host 独立安装，可拥有认证 HTTP 和通信 Journal。QMT 自身加载策略、SDK 管理缓存与策略主动文件读取分别取证。

本轮未执行或修改旧 QMT 工程，未重启、替换、重新配对运行中的终端/Host，未发真实 SDK/账户/交易指令；WonderTrader 框架新增修改为 0。诊断使用自有一次性 pythonw 进程、创建时绑定 Job 和隐藏私有控制台，实际进程退出及资源回收单独核实。

## 候选与实际验证

组合候选001（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-combined-001/candidate-map.json`）完成两角色标准全离线非 editable 安装，依赖解析、pip check、wheel/安装源码身份均核实；没有向已安装目录覆盖源码。新运输、原 native cleanup、Agent/Host 生命周期及真实 Windows 双进程 Session 测试共 30 项通过。其双进程为 3.12 对 3.12 的协议测试，真实目标 3.6.8 业务初始化与端到端仍待验。

原配对 v1 与新内存配对 v2 实际生成/verify 均通过，保留 qualified_in_qmt=false / order_ready=false，配对过程没有创建 Journal。新策略约 1.43 MB，正文 ASCII，Python3.6 语法准入；完整依赖为 81 个源码模块。

实际目标解释器为国信安装的独立 CPython3.6.8 pythonw，解释器 SHA `49cfc2336b4386b851d575d97e649a1c2bf6f18f339b172386423820e2026c85`，python36.dll SHA `54fa9e8511cb57be78be995a9973676cf3eba2b54aa36f6244dd0cb5977c4002`。它与运行中的 QMT 进程相互独立。

## 私有模块隔离的根因与回归

独立 full 审查覆盖 148 份源码/要求及 3 份二进制身份，根逐项复核摘要一致。原复用代码的私有模块表仍会共享解释器可变状态，实际诊断确认两条触发链：

| 触发 | 原结果 | 自有生成器修正与实际结果 |
|---|---|---|
| 宿主已配置 warnings 过滤顺序，私有库导入共享 _warnings | 高优先级过滤规则被重排；原探针 exit 1 | 从私有 builtin 白名单排除 _warnings，使用目标 CPython warnings 自带纯 Python 状态；同一探针验证对象、内容、优先级及 ignore/error/once 全通过 |
| 完整生成策略在宿主 canonical Thread 中加载 | 私有 _MainThread 重新认领线程退出哨兵；完成事件已触发，原 join 8 秒后仍显示 alive | 私有闭包借用 CPython 原 _DummyThread 记录；owned Thread 保留原启动/join。完整策略四回调装载后宿主约 0.11 秒退出，原锁释放/原 join 完成 |

原失败证据保持 exit 1，外层失败码 2；均自然退出、未强停、整树归零、管道 EOF、reader join 和句柄关闭。此处只证明独立宿主 Thread 的条件性缺陷；QMT 实际策略线程模型尚未测定。

最终隔离修订002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-isolation-delta-002/result-manifest.json`）生成器 SHA `d1d740f73c759dea4ea7d9c7f7609a55d114c64cb557818affd93d79edf8f8d4`；实际发射 runtime SHA `b96195c3548c7fabf82308dce60483f7f309f47b8a4c0388d3e33fc1e48333f6`。生成器保留原 stdlib 文件 SHA、变换生成器 SHA 和发射文本 SHA。源码形态检查拒绝缺失、重复、链式、注解、增量、解构、不同调用及带参数调用八类漂移，并核其余线程原文完整保持。

该最终修订实际完成五组受控运行：生成、物料检查、warnings、完整策略宿主线程、81 模块冷启动。每组 exit 0，未强停、整树归零、reader join 和资源关闭。物料检查另有错版本/字段/二进制/许可/缺模块等 10 项拒绝。冷启动覆盖实际账户转换的三个合成 SDK 调用、静态属性访问、原生 datetime 精确身份、两合法/十非法分钟日期、JSON/HMAC/Decimal/UUID/中文/regex、私有 Thread 与队列 join、模块/文件/DLL/网络拒绝、篡改和错版本 gate。

这些 cold-load 证明完整依赖及所测调用路径。完整策略探针没有调用 init，没有真实 SDK 或映射业务；不能据此授全部 81 模块已执行、券商限制已通过或真实业务就绪。最终修订独立 delta 审查（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-isolation-final-review-002/REPORT.md`）完成、未发现新增可行动问题；根复核98份来源摘要一致。

## 并发、资源与发布字段证据

组合001 full 审查还发现 listener 构造锁可阻塞跨线程停止，以及 Windows 安全描述符/SID/token 临时释放失败时缺乏持久 owner。这两处位于自有连接层，修订候选及真实持锁/原生释放失败测试正在准备；组合001保持冻结，不登记为可交付。

机器证据目录（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-builtin-machine-evidence-001/README.md`）已由根在独立 3.6.8/3.12.14 进程实际采集 Python DLL、mmap 槽、已解析 IAT/CRT 地址与匿名映射对齐，并对实际复制调用取得有界反汇编。两次采集均 partial、exit 2，保留 WS2_32 ordinal import 限制；外层未强停、资源实际回收。6+5 个反汇编窗口完成。后继同进程采集确认Host实际 memcpy 入口已改变跳转立即数，与磁盘初始目标不同；另取1个实际目标窗口及加载跳表，实际目标正文与对应磁盘字节一致。实际 memcpy 为特定 CRT 版本和运行分派的机器路径；完整原子发布及负载排序证明仍 MEM-G1=unknown。架构名称、HMAC、单次对齐样本、压力测试或 memoryview.cast 均不能替代该证明。

## 新组合002：落源码与实际业务增量

最终组合002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-combined-002/candidate-map.json`）已完整离线构建并安装两角色，依赖解析/pip check及安装源码核验通过。新安装实际运行48项运输/生命周期/安全资源回归，0失败、0错误、0跳过；旧Win32后端的真实内核映射、终止进程/ACL/损坏/背压、业务和关闭22项回归也通过。目标SDK warnings、完整策略宿主join和81模块冷启动均按本次安装重生成并通过。

公共资源owner及完整消费者的独立full审查（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-builtin-cleanup-independent-review-001/REPORT.md`）在Spec/Standards两轴均无阻断发现；根核59份源码/6份要求摘要一致。26份明确自有接入/测试文件经before摘要全量核对后已落入仓库，逐字节匹配独立安装候选，备份及最终摘要见live-applied（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-combined-002/live-applied.json`）。未改WonderTrader框架，未操作旧QMT工程、Git或运行版本。

实际混合解释器业务：Host结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-combined-002/mixed-run-001/result.json`）及目标结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-combined-002/mixed-run-001/target-result.json`）。实际生成策略SHA `246609e5ba1ee063f0ee316487adbfe82af869e00500a8246b52ac35508c1204`，1429752字节；完整runtime SHA `c430e0aeae9f1ef0cf43b4662d78ec4173bc8ec0b24aecc9501a636af6ffb6f9`。目标3.6.8调用真实init/agent_tick/stop，内建mmap与独立3.12.14 Host完成真正BoundReadJournal/认证Session/full_tick全链，合成Context读取一次且只在原线程，三B/双层SHA/两端generation一致。全程约1.438秒，策略文件访问计数0，实际导入新增仅真内建，包含mmap。双方worker、view、connector、listener及Journal回收确认；外层Job未强停、整树归零及reader join均另核。

混合001原始passed保持，证明业务结果与上述回收事实。独立夹具审查（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-mixed-fixture-review-001/REPORT.md`）发现正常关闭断言P2：任意I/O异常也会置stop，原测试未区分。正常peer-close资格暂缓，修正只在测试夹具002进行；不回写原passed、日志或产品failure，不把业务证据一并抹去。

机器路径独审（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-builtin-machine-analysis-001/REPORT.md`）32份来源已由根核同；已覆盖两端实际8字节单qword复制、实际Host分派以及非重叠payload/NT屏障。MEM-G1整体仍unknown：精确制品/分派、硬件排序模型及目标named映射对齐/保护属性的资格前提仍须限定；不扩授当前或未来运行环境。

## 后续验收

1. 混合夹具003已完成正常peer-close/意外workerfailure区分；实际运行、14项装配回归及独立delta通过，具体后继见下节。
2. 按精确新安装继续历史/账户组合和其余原生消费者的对应验收；full_tick互操作资格保持范围。
3. 核清实际发布字段复制及内存排序边界；证据不足持续 unknown。
4. 交付可审阅的新安装材料后，按具体授权完成升级券商终端真实只读验收及后续独立业务入口。当前活动安装保持；账户与交易资格分别核实。

整体观衡迁入目标继续 active。本记录只反映内存接入切片，不关闭历史真实覆盖、完整账户矩阵、原生实时执行、业务页面、正式发行与生产验真。


## 严格关闭验收后继003

夹具002实际运行保留失败：装配把发射源码的CRLF摘要按LF比较，且试图在Agent构造前访问尚未按需导入的模块。这两处属于测试装配；002原始退出码、日志和产品failure保持。夹具003按生成器真实raw bytes→utf-8-sig解码→utf-8编码计算发射身份，并在真实init的Context.run_time注册窗口安装只读trace；该窗口位于Agent构造之后、worker.start之前，不预热产品模块、不改业务函数。

夹具003（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-mixed-sdk-tests-003/review-input.json`）的14项回归实际通过，含原10项严格关闭定义与4项CRLF/真实init装配定义。新配对、新映射及新Journal独立运行，完整策略SHA `7f820aed4d713c9773ef4f66e6c5032f10ecd4ce849c0c71f421eaf01a0ba025`。实际3.12.14 Host与国信独立3.6.8目标进程约1.438秒完成认证binding、真实Session/BoundReadJournal及合成full_tick业务；SDK替身仅在原策略线程调用一次，策略文件访问0。

正常关闭汇总（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-combined-002/normal-close-verification-003.json`）保留原failure：两端均为OSError；trace分别确认来自同一实际framer、实际worker及精确本地停止/对端关闭raise，且同一异常进入_run，各有一次run进入和返回。该精确来源满足本次预期关闭，意外I/O失败仍拒绝；没有把任意stop或进程exit0当正常关闭。双方trace恢复、worker join、映射/listener/Journal关闭均通过，外层三个受控运行均未强停、整树归零、管道EOF、reader join及资源回收成立。

本次产品源码零改动，补强只在隔离夹具。独立静态delta003（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-mixed-fixture-review-003/REPORT.md`）已完成，新增问题0，两项装配P2关闭；根复核61份来源无漂移。MEM-G1保持unknown，升级后真实QMT限制、真实行情与账户/交易资格分别待验。后续整体业务切片为既有PWL-R18独立安装/生产SPA/实际保存和进程重启验收，来源见保留业务审计（外部历史/待归仓路径：`../../build/guanheng-workspace/retained-business-current-audit-20261023-002/REPORT.md`）。

## 真实终端后继验证

此前“真实终端待验”保留当时范围；后继[实机读取证据](2026-10-23-qmt-memory-terminal-read.md)记录新专用完整内存策略在国信QMT实际运行、行情快照/原ID恢复及Host正常关闭。原运行安装保持，正式账户与交易能力继续开发和单独验收。
