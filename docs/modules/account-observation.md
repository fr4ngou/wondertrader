# 账户只读观察

观衡当前持仓归属展示、唯一策略详情及分实例WT运行读取见[策略与报告详情模块](observer-strategy-details.md)。

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。所有者角色：账户接入与业务展示维护者。行为要求见[NAC规格](../specs/native-account-console.md)与[共享内存账户契约](../specs/qmt-shm-account-read.md)，部署与处理见[账户手册](../runbooks/account-observation.md)。

## 职责与原生复用

`src/GuanhengAccountScan`拥有有限的一轮采集宿主。每轮独立进程装配固定原TraderAdapter、基础资料和普通TraderQMTReadOnly，通过正常登录/四查询链、owner wait/pump取得版本化值。schema1对应inspection2/IPC1；新schema2显式选择qmt_shm_bound/v3，对应inspection3/IPC2。新原生分支已写入源码，运行资格见[账户证据](../evidence/2026-10-23-qmt-shm-account-read.md)。原生账户/订单/成交映射与持仓统计继续由原Adapter和插件承担，宿主不重复实现。

观衡账户入口由`GUANHENG_ACCOUNT_SOURCE`显式选择。wt_account_publication沿[NAP-v1](../migration/native-account-publication-proposal.md#nap-v1冻结合同)核WT根、发布定位、ready及原帧，`account_publication`交唯一validate_observation/project_account生成DTO4；金融字段沿原DTO2，持续发布阶段及最后成功时间单独拥有。默认wt_strategy沿WRI/NRT-R20只读定位生成DTO3的已知P/资金及各自时间；委托/成交等未提供组分别缺失。策略运行入口始终沿原R20。HTTP与页面继续通过原账户地址及AccountWorkspace读取。App只拥有Web读取线程和个人偏好，原account_scan的进程/管道/容量逻辑属于WT侧或独立工具能力；后文旧App托管链保留历史开发范围。原始账户事实由券商及原生owner拥有，观衡展示投影保持有限内存值。当前部署及组语义以[账户手册](../runbooks/account-observation.md)和[COP](../specs/guanheng-operator-platform.md#独立wt状态消费)为准。

## 调用与线程

新来源调用链为：浏览器GET账户观察 → 独立业务HTTP → 账户采集owner → 产品子进程 → 原TraderAdapter/只读插件/固定账户客户端 → 终端外认证Host → 共享内存 → QMT原策略线程固定三参数SDK读取。原生插件owner只在子进程主线程，worker独占客户端，原生指针不进入Python或HTTP线程。旧schema1/QRT作为原兼容与历史证据来源保留，已退役终端HTTP不进入新来源回退。

父端最多一个在途采集进程、16个异步等待者。共享同一轮scan_id；每个调用者有自己的等待截止，取消只释放自己的席位。父采集owner和两条有限管道读取线程负责本轮回收。stdout只传长度前缀的两个值帧，stderr并发消费并限制字节。未校验的半帧、乱序、额外帧或不一致退出码不能作为成功结果。

原生宿主不反复向同一个Adapter灌初始化查询。新轮使用新进程，避免原统计累加或未再出现证券的过时映射。子进程退出由OS回收原Adapter保留的模块引用，不以此授予通用热卸载资格。

## 数据与公开资格

四类数据分别保留运输绑定、请求ID、执行区间和结果摘要；共享内存来源的Host实例/运输代际与券商登录会话分别表达，缺少登录证据时明确unknown。共同展示不表示同一券商事务快照。`complete`、`partial`、`unavailable`与完整空批分别建模。source账号在内部核绑定，公开接口仅输出掩码标签。

QMT内置API的执行时间描述本次读取；原SDK读取客户端缓存，数据经柜台回报刷新，执行结束不能授予柜台瞬间一致性。三参查询保留不按策略过滤的范围，strategyName第四参只影响委托/成交；适配器须按明确范围返回，源有效时点缺失保持未知。供应商依据为[交易函数](https://dict.thinktrader.net/innerApi/trading_function.html)与[缓存说明](https://dict.thinktrader.net/innerApi/question_answer.html)，核查日期2026-10-22；实际源版本与字段资格单独验证。

公开字段含availability/value/reason。未知和非法字段保持空值；原ABI的中性零、合计pre/new槽及空userTag不升级为业务真值。原getOrders的管理活动单范围与全账户查询不同，后者通过版本化事实值展示。历史成交不重新当作push应用，策略归属与交易授权沿其独立owner。

页面显示资金卡片和持仓/委托/成交标签，记录按50条分页。刷新中或失败时保留成功结果及每批原查询时间；部分批失败可保留同来源上次成功批，明确标明本轮未更新；新成功空批清除对应旧行，已知来源改变清除跨来源回退。当前轮DTO与上次成功展示分别拥有，不合并行或统计。日常页面只显示掩码账户、实际环境与时间，技术身份留在原DTO。账户可读能力不会启用下单或撤单。

## 请求身份与重新读取

依据[ADR-0007](../architecture/adr/0007-account-observation-read-state.md)，固定四查询的原receipt仅在活进程有限内存保留。Core一次令牌和原ID GET负责本轮请求关联，Host既有Journal负责持久派发与终态。账户展示不增加客户端收据目录、恢复根锁或累计目录配额。

WT持有单轮进程；进程死亡结束旧轮，后续WT调度在确认旧子树实际回收后新建进程、Adapter及scan_id。原查询可能执行过，旧终态仍关联原Host记录；发布者失败时保存上次成功整帧及原时间。页面刷新只读取已发布文件。每阶段一次SPI、整批验证、来源/截止准入及关闭证明继续保持。该重新读取规则只适用于只读观察，真实交易未知结果沿独立执行契约处理。

自有AccountReceiptStore/RecoveryBoundary源码与接线已退出，六字段配置和原CLI保留。原生统一截止/唯一帧输出、公开DTO2/配置/HTTP类型及页面修正已有对应静态审查；真实原生/IPC2、SDK及公开API主路径已有后继[实机记录](../evidence/2026-10-28-qmt-account-public-main.md)。双角色独立安装及合成SDK下的TCP/生产SPA见[新组合证据](../evidence/2026-10-29-account-installed-app.md)，真实新安装浏览器和完整场景继续单列。

## 配置、关闭与验证

当前观衡使用四项WT读取身份及显式账户来源，字段沿[账户手册](../runbooks/account-observation.md#安装与读取连接)。旧`GUANHENG_ACCOUNT_SCAN_EXECUTABLE`和`GUANHENG_ACCOUNT_SCAN_CONFIG`属于历史App入口，当前Web忽略。独立扫描工具的binding含安装/插件/基础资料身份、来源绑定和总预算，秘密只通过指定环境变量引用。未配置时返回明确不可用；不搜索旧工程配置。`scripts/native.py --profile account-scan`使用自有构建profile；原生、业务wheel和SPA可分别发行。

WT账户发布组件停止先关闭新轮准入，有限等待当前采集；必要时终止并wait回收其自有子进程，标记forced。原已受理SDK读取可能继续完成，父关闭不宣称撤回来源操作。实际join、进程退出、管道和监听回收分别确认。观衡关闭只收回自己的读取线程，WT及其Host/Scan继续归WT。

验证按协议版本和实际执行边界登记。

| 入口 | 验证职责 |
|---|---|
| `native_account_scan/run.py`与`native_account_backend/run_native_chain.py` | 保留schema1/inspection2/IPC1范围；现有account-scan构建/搬迁入口仍使用此runner，其结果限定于该版本 |
| `qmt_shm_account/scan/test_smoke_ipc.py` | 调用同一`smoke_ipc.admit_smoke`，复用生产严格JSON与公开观察validator，核完整关闭/成功事实和非法帧；独立Python CI明确选择此纯值入口 |
| `qmt_shm_account/scan/run_schema2.py` | 普通原生程序/插件→Host→实际SHM→合成三参数SDK链；显式配置原字节摘要、inspection3/IPC2、原deadline及实际资源回收需分别验收 |
| `qmt_shm_account/scan/native-main-cases.json`与`registry.json` | 场景id与可执行case逐项对应，记录pending/实现/运行事实；定义存在、跳过或局部烟测均不授整套通过 |
| `tests/browser/guanheng_console/account.spec.ts` | 实际业务HTTP与页面正常/空/错误/恢复；不替代原生、安装或真实SDK资格 |

账户整链测试的独立安装角色与可搬迁闭包由[ATI规格](../specs/native-account-test-runtime.md)定义。此前单解释器装配存在Host/App精确依赖冲突；现有双角色普通安装已在C的账户/交易记录/总览组合中实跑，保留两侧完整锁、所属解释器原准入与独立发行身份。原run_schema2的完整45项及其他ATI矩阵继续沿测试契约逐项验收。测试marker只属于合成夹具，真实QMT Agent继续使用原SHM协议。

表中前四项测试路径位于`tests/integration/`。纯值CI不运行原生runner、Host/Agent、DLL或SDK。schema2原生runner的安装依赖与完整场景仍按其测试契约（外部历史/待归仓路径：`../../tests/integration/qmt_shm_account/scan/RUNNER-SPEC.md`）接线，当前运行结果见[账户证据](../evidence/2026-10-23-qmt-shm-account-read.md)。父端软件、原生装配、合成SDK、真实QMT来源和生产部署资格各自取证。

新schema2纯配置采用私有递归不可变快照，来源、版本及预算从同一副本判断；目标只由原生宿主在内存装配runtime_deadline_ns，部署JSON和公开请求禁止runtime_*注入。schema2按QAR保留六字段，原recovery字段拒绝。父端在配置准入时一次核对raw bytes并派生内部SHA；各child以私有--config-sha256绑定native同一次body读取，每轮父端不重读或持锁配置文件。公开DTO2.0、唯一投影及HTTP判别联合已写入源码。

历史App托管链中，schema2在严格配置准入后接到应用唯一ManagedAccountScan，capabilities说明受管入口已配置；实际来源可用性由有界查询决定。未配置和直接缺少受管owner分别明确拒绝。父端沿原ThreadOwner、创建期Job、原总截止、IPC2和资源回收；关闭异常继续处理其余owner并保留异常。真实QMT四类账户查询、Host更换后原运行策略自动重连、公开DTO2.0与正常收尾已完成主路径验证，详见[实机记录](../evidence/2026-10-28-qmt-account-public-main.md)。新安装合成SDK组合已补中文浏览器七轮及资源回收，完整原生故障矩阵、真实新安装浏览器与生产继续逐项验收。
