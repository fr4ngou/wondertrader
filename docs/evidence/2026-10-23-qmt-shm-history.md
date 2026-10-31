# QMT共享内存历史分钟接入

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-23。类型：开发验证与候选身份核对。范围：[QH](../specs/qmt-shm-history.md)的Python生产者、准入及Host；限定Python full已complete、产品gap 0。C++正式客户端仍在开发；预览已通过合成SHM→CLI→原QMI/DSB/Reader整链。真实终端/SDK与生产未验。

## 接入边界

Agent a2与Host a3在本仓独立构建安装；旧QMT工程仅作静态来源参考。认证的完整read profile区分原v1 full_tick与新增v2 history能力；请求不指定动态模块、文件或SDK调用。历史通过主策略线程的既有队列/完成发布链执行，精确七字段、显式窗口/行数/容量/截止；无成交或空观察保留coverage=unknown，不推断完整覆盖、不下载、不填充。

SDK调用后以及结果编码后均检查同一总截止。编码后才超期时，同一owner使用原finalizer将尚未发布的成功替换为有界超时；SDK执行一次、future发布一次、Journal保留原ID的单一终态。v1原行为继续专门回归，终端HTTP路线没有恢复。

## 安装与证据身份

final-002入口（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-product-001/final-002/review-inputs.json`） SHA `b6b48e867e60bebc09169715edc096d586680ac44c9477cebcf17473b345abd2`；源ZIP SHA `1015234c2a3dfa3e165f617d77cad0617bf3c5614a4b74ce819d23b02d7d4607`。Agent wheel SHA `7bffab3b349a776fa1461d15e5083185af623f78a01c9db100eb919c9febe374`，Host wheel SHA `7e7fc5cab4be1f7581f6439a33130899b27668be87b74fa594979d460c91723f`，精确依赖Agent a2。

作者开发验证183项通过；实际Python3.6纯9组及合成SHM、旧C++ v1两个pool原DLL链、新fixture smoke分别通过，Job均nonforced、exit0、进程与管道回收。运行原件由最终索引（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-product-001/final-002/final-run-index.json`）指向。根任务身份回核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-root-001/integrity.json`）确认10份入口原件、85份当前源码及ZIP成员、1363份安装文件和最终运行索引相符。通过条数属于开发结果，独立full尚未封存。

## C++、真实来源及容量

C++复用一个绑定/认证/receipt/GET恢复core，原FullTick门面保持签名与v1行为；新历史门面与正式CLI进入实施。已取得原九组v1抽取前后通过的开发结果；新history→CLI→原QMI→DSB/Reader仍待组合验收。首个POST前持久原body/ID/完整profile，恢复只GET原身份；未知不自动换ID重发。

本机SDK静态源码表明字段列表传入原生，并可能保留显式time列；不同接口的字符串index说明与xtdata epoch说明不能代替ContextInfo实际返回证据。因此显式time列是否存在、毫秒单位/类型、缓存读取和分钟边界仍须新连接包的真实只读验真，当前不推测、不根据index补造。股票/ETF量额单位及历史完整覆盖分别待核。

Journal保留终态的逻辑容量，达到上限明确拒绝；没有自动删除或轮换。本轮取得有界历史页开发资格后，还需确认长期保留与新epoch运维方式。历史/实时/账户多能力并用、常驻运行、真实SDK和生产资格继续独立，不由单页成功推导。

## 后继：限定Python独立full完成

独立Python full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-python-review-001/REVIEW.md`）结论complete、产品gap 0；报告SHA `0f632c98f19c76f1b2a71581a76d07ab73694ccd21e192285e441058d0d8c352`，381份原件manifest SHA `b2fb0650ba84618bcc5051e1f0ac536c395e87127eb71f08f60e5ea719a8f4b1`。83项适用unittest、15组自主边界及两组独立合成SHM场景通过；包括实际3.6.8、原v1/v2能力、Journal原ID恢复、编码完成后期限与唯一发布、关闭回归。1999行合成大页的实际data/native/envelope分别188161/188587/253065字节；声明5000ms域内观察执行53ms，总约0.500秒，该值不授真实SDK延迟保证。

根任务核对（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-root-001/python-review-integrity.json`）381份审查原件、85当前源码与1363安装文件相符。C++R6、客户端receipt/分页计划/QMI、真实SDK/单位/覆盖、持续容量和生产在该full中明确unknown；本段不关闭整个QH功能。

## 后继：新CLI预览进入原生文件消费者

新增联调入口（外部历史/待归仓路径：`../../tests/integration/qmt_shm_history/reader/flow.py`）使用冻结final-002安装Host/Agent及原合成fixture，显式请求2021-11-01/02的十个单分钟、不重叠窗口；覆盖午休、换日及回放结束之后的未来分钟。C++预览EXE SHA `a1c31060d5c5a9ab926e677ac08d0ab4a90f0bd3a475a5e77dbbebbc18802075`复制后固定，不随并行编译改变。fetch与原root resume共两次CLI，来源SDK总调用十次；十个原ID及恢复native原字节保持。

新文件消费者（外部历史/待归仓路径：`../../tests/integration/qmt_shm_history/reader/consumer.py`）直接消费该CLI产出的原QMI manifest/CSV，复用既有导入实现、已验原Helper/有界文件ABI及原WtBtPorter bin文件Reader；没有外部loader、Parser或目标setter。十行进入新DSB，完整回读原时间/OHLC/量额相等；显式right边界及量额factor1只代表合成profile。原生初始化可见两行，随后七个闭合分钟和七次计算、共八次完整前缀核对相符；第十行位于回放结束之后，未进入当时的可见前缀。coverage保持unknown，稀疏窗口没有填行。

实际Job约7.47秒、exit0/nonforced、进程及管道回收，所有参与者受同一creation-bound Job；内存上限512MiB、输出监测上限32MiB，实际输出约3.75MB。原生结果及调用时钟见运行目录（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-reader-001/runs/799a49a2ed514aa58ced9d3d77c7f1cd/result.json`），再次核对（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-reader-001/audit.json`）重算八个前缀SHA并核恢复字节/源请求/依赖身份。133份原件封存（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-reader-001/SEAL.json`）manifest SHA `52f93ae7b678421a0c5d03e970dbe31f002c422d5905fdd380c25283555d41b2`。

这条链当前为开发预览；正式C++安装、完整负向/容量/故障审查后，需用最终同一安装身份重验。该探针只证明分钟文件消费，没有完整策略篮子/日线/辅助输入，不能授业务策略、真实QMT源或交易资格；本轮未改WT框架或任何运行终端配置。

## 后继：最终C++安装到原生文件消费者

使用`qmt-shm-history-native-001/install-d1d748258bf742b7951e7d92ae466f94`正式独立组件安装，EXE SHA `2b7d7c1889edfecaa81edd21dafe9ea773ca8c33b3858219b8c7cf80ef7ca7e7`，安装清单SHA `bb1ab382af4b2a7a2cf7ec2c38bcfcfe30fd4958feb50ea30a210f2f13b80d69`。本次复制并核实完整11个app运行文件，含10个CRT侧载文件；全部启动入口显式隐藏，没有运行手工新建控制台场景。正式安装的普通/故障矩阵及独立审查另由其候选入口登记。

根任务以相同十窗口重新执行合成SHM → fetch → 原ID GET恢复 → CLI原QMI manifest/CSV → 原Helper/DSB → 原WtBtPorter文件Reader。SDK实际调用十次，恢复没有重调；十条原时间/OHLC/量额匹配，两行预热、七闭合分钟、八完整前缀以及未来行排除均通过。新Job约7.724秒，exit0、nonforced、进程与管道完成回收，输出5,798,904字节，内存/输出上限仍为512MiB/32MiB。

正式安装链封存（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-reader-002/SEAL.json`）包含151份原件，manifest SHA `cf6f16bd7919fc4425ab85612b6e5f8347ecc356e0d31fc473ae53f82ce85274`；独立逐字段复核入口（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-reader-002/audit.json`）重算全部前缀与原请求/恢复字节。case结果SHA `96f1ad0cf9278a24ea2ad56eba9482649ad1d543948c528ea2c4c4d83812c666`。原133份预览原件保留，本轮资格由新的安装及测试快照绑定。当前结论限合成安装整链；真实ContextInfo返回、单位、覆盖、长期容量及生产继续单独验收。

C++最终候选入口（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-native-001/final-001/review-inputs.json`）SHA `4c7b289d9a8f12512038922e03c91cf14fef00c55a77f9dcdb0731c59ff14a9a`已冻结。根任务完整性复核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-root-001/cpp-integrity.json`）1791份原件及9个当前产品文件均无差异，安装CLI身份仍为本段同一`2b7d7c…ca7e7`。不同作者首次full进行中，完整矩阵、适用缺项和真实来源资格按其最终报告分别登记。

## 后继：限定C++独立full完成

C++独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-cpp-review-001/REVIEW.md`）已complete，9产品/C++阶段新增gap 0。独立18项契约、9项v1兼容、13项新增边界、晚回调四场景及d1d真实Win32合成SHM normal/empty/300ms超期→原ID恢复通过，源替身各只调用一次；九个受管Job均自然exit0、进程/管道回收。审查未运行编译、可见控制台事件或真实SDK。

审查还核151份原Reader链原件、十页原字节/CSV、八前缀/七闭合分钟及未来排除。根任务最终回核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-root-001/cpp-review-integrity.json`）502份审查原件、9个当前产品均一致；报告SHA `4392f4ae46b07ffa3cd831de030a75fbd0719869bcf1ce1f7701de648012b0a9`，manifest SHA `d1f423a051a15d64da3ed497e8f9fd9a4a5f424380e5c60a0c7ee97c730c024d`。原构建工具快照与后继无窗口工具变更分别绑定，安装EXE/CRT没有变化。

Python full与本次C++ full分别完成其限定职责，证明冻结两端及原生文件消费者的合成开发整链。真实ContextInfo字段/time列、量额单位、股票/ETF覆盖、历史与实时混合能力、长期容量和现场生产仍未授资格；不将两个限定full合并解释为整个QH或整个观衡迁入完成。


## 后继：既有共享内存安装的真实分钟有界读取

恢复授权后，经现有外部Host 18017→共享内存→QMT完成四次只读 market.market_data_ex 请求，每次只提交一次原ID、同ID有限轮询。保持QMT运行现状，下载/订阅变更/账户/交易调用均0。两轮控制进程均实际exit0、整树0、双EOF和reader join/资源关闭已核；原件位于qmt-real-history-001（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-real-history-20261023-001/result.json`）和002根核观察（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-real-history-20261023-002/root-observation.json`）。

000001.SZ在2021-11-01两次各返回10条。第一次只选价量字段；第二次显式请求time/stime，两列均返回，10条毫秒时间戳与UTC+8分钟字符串逐行一致，窗口结果14:50至15:00。510300.SH在2026-10-22及2021-11-01抽样均返回空列表。此结果证明所选股票早期样本可读，整体覆盖仍unknown，ETF空样本的缓存/请求原因继续核查；count=10不代表完整日或全市场。成交量换算尚未取得足够真实证据，本轮保留原值，未向WT写入未定单位的数据。

该安装属于已交接通用Host协议的现场观察；本仓独立bound-profile适配、安装身份和真实账户验收仍单列，不以此次历史读取授其资格。退休终端HTTP18010保持不用，通达信未参与对照。
