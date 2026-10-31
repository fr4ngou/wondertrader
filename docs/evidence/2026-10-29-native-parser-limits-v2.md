# Parser v6对历史准备limits.v2的完整准入

类型：验证记录。状态：模块主链、边界、独立full审查及搬迁交付通过。范围：[NPV6](../specs/qmt-native-parser-v6.md)、[HPR2](../specs/qmt-history-preparation.md#hpr2-固定输入与预算)、[RS15](../specs/qmt-source-history.md#rs15-来源支持范围与补齐配置)。

## 根因与实现

正式来源保留read-profile.v6，history_prepare的limits已按HPR2切为v2并省去symbols。原C++准入精确要求v1和symbols，因此拒绝整个组合binding，full_tick也无法初始化。自有`QmtBoundReadCore.cpp::profile_v6`现在按schema分为两种封闭形状：v1精确含symbols并核排序/证券格式，v2精确省略symbols；原period/day/task/queue/time和descriptor最大时限继续校验。完整profile与binding摘要沿原实现核实。Factory仍只有full_tick和原ID查询入口。

前版core SHA `90e5c5eb44fade15abe998fa9c94fe06238fa4137e91369d14a48784a43b797c`，新core SHA `6bd42a6dbe1be18e7fe077fa61a8fb40ba98e6ada0fa33c7d8a5795bfcc69c1f`。v6函数以外字节完全相同。构建复用原独立候选固定源码快照及静态库，仅替换这一个实现；WT框架和其他Common保持。

## 安装主链

独占目录`build/native-quote-parser-v6-scope-001`。新DLL SHA `31bf05de7c2f4ee14363dee5a02aed7850c673055d724be78ad7c51ff3b1346b`。新统一HPR安装manifest SHA `819ae7497b765f4005afc230f3d6bc46d5c58c70d47fcb615173d4c62af45ba1`。

`chain-v1`、`chain-v2`均使用实际安装Host→认证WinSHM→实际CPython3.6.8完整生成内存正文→纯SDK替身→原Factory/ParserAdapter标准SPI。两种limits各取得恰好三次回调：SZSE.000001价格4/累计10000份/400元，SSE.510300价格5/10100份/505元，SSE.600000价格6/10200份/612元；标签均2021-11-01上海09:31:00。重复快照无额外回调，stop/delete成功；源SDK只在原线程调用，history/download未调用，forbidden_attempts=0。来源、Host、Job、线程、管道均正常关闭，外层exit0。

最终`ParserQMTHostV6-scope-002.zip`经实际搬迁至`relocated-002`，沿同一新HPR完成`relocated002-v2`完整主链，exit0及全部资源闭合。实际PE依赖已独立解析并与固定Windows/MSVC依赖清单比较相等，无额外WT DLL。统一候选原组件契约要求的bare `MANIFEST.json`已按新文件集重建；旧001包及旧搬迁原件保留，最终002身份优先。

## 边界、兼容及交付

`build-contract002`共17项（16通过/1明确skip），包含27组v2非法limits、最小/最大资源边界和周期子集、v1/v2旧能力摘要混用、profile摘要错误、binding中途变化，以及原丢POST/Unknown原ID认领与原字节/时限/线程检查。每个非法limits均核实零派发。旧v6候选接受v1且拒绝v2；Legacy默认拒绝两种v6。旧Legacy矩阵9项（8通过/1同类skip），账户v3/v4及34个事件向量通过。两组原矩阵各保留一个未供应独立fault-only探针的skip；本次没有宣称该内存故障注入已执行。

固定输入、安装、包、主链及审查身份由该目录最终`DELIVERY.json`绑定。`CANDIDATE-INTEGRATION.json`提供原统一候选mapping所需新组件origin/version/路径；共享构建/打包映射保持只读，由根合入并做真实QMT来源验收。本轮真实QMT、账户、交易、下载、UI操作和生产切换均为0。

独立`REVIEW.json`的Standards/Spec及NPV6-R1～R3均complete、无阻断发现。审查者实际重跑最终002搬迁主链和17项矩阵（16通过/1明确fault-only skip），原件分别位于`review-output/relocated002-v2`及`review-output/build-contract001`，所有自有资源关闭；文档检查exit0。审查结论绑定INPUTS冻结快照；当前并行工作区的其他WT头差异保持，未混入本候选。


## 根统一装配与真实来源后继

根将已审原MANIFEST 348508d2…1f93a登记为v6-market-scope001，统一候选位于build/native-quote-parser-v6-scope-001/unified/relocated-001。总manifest SHA为228cd7f9021a7396252253f733e03be44106b820cc67235a6cbe9878f0113919，ZIP SHA为05662422af1662e70f0523b4822a4538310317e2852ef965e14f24fabda26a0d，共1162成员（含总清单）；其他五组件与来源范围候选的原件完全相同，逐成员对照在UNCHANGED.json。旧候选和默认配置保持。

真实GH_WT_MEMORY_VERIFY当前正文99a8d6…372e、limits.v2省略symbols，沿已有私有配对和受管Host读取。real001在Host进程ready后立即调用原探针，连接false/errors1/无报价；该次外层及Host正常关闭，原件保持。隔离诊断对同一公开profile/元数据复现binding503的相同失败形态；binding就绪则三证券成功，默认响应预算可用，详见diagnostics-001。

real002在同一启动总截止内先认证GET read-binding，实际先8次503后200，再运行最终统一包中的原探针和DLL。SSE.510300/SSE.600000/SZSE.000001各一次SPI，connected/stopped/deleted均true、errors0。源日期20261029，源标签约16:27；本轮是盘后快照连通证据，不授盘中新鲜度。使用源raw-observation倍率1:1，份/元及全部字段逐位资格继续沿原来源证据。本轮真实full_tick之外没有下载、委托或撤单，源正文逐字保持。352外层14.031秒exit0，无强制、树0/双EOF/线程join/资源全关闭，Host state closed/pending false。

新统一包沿353复跑普通SDK历史、原NMR snapshot、正式Host/3.6.8正文替身/新Parser和App采集owner四条组合，87.593秒exit0及完整关闭；snapshot明确使用上午冻结副本，不冒充当前实时数据。354通用装配回归53.344秒exit0，真实符号链接创建因Windows权限1314明确未执行，其余按原报告。打包344/搬迁345、UNCHANGED、real002/RESULT及各外层收据保存于本目录；project.py check通过。注册映射增量的独立审查与整系统策略/长期运行/生产交付分别登记。


根增量独立审查已完成：root-review001/REVIEW-INDEPENDENT.md的Standards/Spec在R7范围均complete，必要修正0。审查者独立核完整新安装、17个消费入口、五组件逐字节、原R6兼容、30项装配拒绝用例、实机三证券与四组合原结果及352/353/354完整关闭；真实符号链接权限缺失保留未执行，整策略/长期/生产资格保持unknown。该审查未启动QMT或Host。最终根交付固定在INTEGRATION-DELIVERY.json和INTEGRATION-HANDOFF.md，原Agent交付原件保持。
