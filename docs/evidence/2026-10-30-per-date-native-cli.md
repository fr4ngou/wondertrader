# 逐日原生回测的安装CLI

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B开发与接收记录。状态：产品逐日、默认及最终截止修正后的ZIP搬迁主链已验，审查和制品按本根最终收据绑定；整个模块B继续进行。规格为 [NBC-R6](../specs/native-backtest-cli.md#nbc-r6-逐日基准的配置入口)、[NRT-R28-C4](../specs/native-realtime-strategy.md#nrt-r28-逐日基准的原生回放与完整比较)。全部新增安装、缓存、临时文件、运行及制品位于 E 盘 `build/ms-per-date-cli-001` 与本仓 `.tmp`。

## 接缝与实现

原逐日400期已能通过开发API运行，操作员CLI的NSH只接最终批次族，普通SDK中也缺少可安装的ReplayCatalog入口。本次沿原CLI/NSH/Job和原逐日session接配置与身份：新纯值外层只含原session及逐窗source，目录路径/manifest归本机安装绑定。Runner通过固定安装API打开原目录，原Porter、撮合、持仓/资金/费用、NSQ和用户状态继续由原owner负责；WT框架和新增金融账本均0。

B生产修改为 `strategy_host.py`、`strategy_runner.py`、`backtest_installation.py`、`backtest_reports.py`、`retained_per_date_replay.py`。默认角色精确六发行，逐日角色增加一只明确分析core；父端核完整来源、输入组合摘要、模型、策略资本、日期和原生输出，使用原报告validator及投影。逐日CLI的scope取原逐日报告模型声明，默认scope保持。

A接收 接口需求（外部历史/待归仓路径：`../../build/ms-per-date-cli-001/INTERFACE-REQUEST-001.json`） 后交付 `root-native-replay-sdk-001/INTERFACE-001.json`。core a2 SHA256 `fa3fe6d65239694fb1684c577b68e9c8046b473c50eb00c19adb54db8111b56f`，公开 `guanheng_market_client.qmt_native_replay.ReplayCatalog` 重导出原类；SDK0.15 wheel及已有成员保持，core原11成员保持。B核原件及固定wheel并登记 CORE-INTAKE-001（外部历史/待归仓路径：`../../build/ms-per-date-cli-001/CORE-INTAKE-001.json`）。A的401日/644808对全部原值比对由其收据拥有，B的实际策略运行另取证。

## 安装与实际主链

`python-001` 为早期六发行API装配副本，只保留准备资格。正式主链使用A原corea2和原SDK wheel：`python-002` 七发行759条带摘要RECORD，`python-003` 六发行739条，均普通离线安装、pip check及导入通过，无观衡/Web。

| 入口 | 实际结果 |
|---|---|
| main002 七发行逐日CLI | 401日期、400计算、400报告投影；157.530秒，worker Job根PID69552，exit0/非forced/回收和管道确认；内层启动73852及外层49464均exit0及完整回收；98预热、77初始化、11买入、194收敛、20卖出 |
| main003 六发行默认CLI | 400计算、400投影；121.344秒，worker Job根PID62924，内层启动46312、外层45596均exit0，树0/EOF/join/资源关闭；98预热、77初始化、10买入、189收敛、26卖出 |

逐日阶段计数及原生输出身份沿各原 `RESULT.json`。`main001` 的产品CLI已完成400期/exit0，QA随后将原callback_counts键值列表按字典读取而失败；原失败完整保留，QA修正后main003通过。两种报告只证明各自模型的原生回放及CLI，不替代完整RT/BT比较。

## 同一截止的审查修正

独立审查指出，新增A目录读取和逐日session纯值构造消耗父D后，runner仍可能开始新Native工作。父Job总D已存在，本次在A.open前后、decode后及统一session.run前重查同一个原deadline，保留原budget及原owner。

`boundaries-red-001` 用原已安装runner及真实请求/安装/五资料准入，分别在A.open和session构造接缝推进同一测试时钟越过D；旧runner仍进入run替身，10项中这2项失败。`boundaries-002` 在修正后的 `python-006` 复验全部10项通过，两个run替身调用均0；错manifest、错报告族、取消、坏日期/SHA/字段及默认角色多core亦拒绝。该组真实Native加载、券商调用均0，外层PID32260 exit0及完整回收；红例PID16248预期exit1且物理回收齐全。

最终 `python-006` 七发行759 RECORD、`python-007` 六发行739 RECORD，原SDK和core身份保持；scope与截止修正后当前源冻结在各安装收据。`candidate-002` 为105文件离线材料，CONTENTS SHA256 `a04f8a76b706333022abf409e22df1286456d7d9c804fe5c9e036a0f24ee0074`；原catalog/Native/基础资料来自R28冻结candidate003，按实际新路径生成绑定。`relocated-001` 从实际ZIP提取、hash锁离线安装后再运行逐日CLI；`main004` 核最终六发行默认路径。最终运行结果按后继原件登记，前序不同源码/QA身份保持。

最终 main004（外部历史/待归仓路径：`../../build/ms-per-date-cli-001/main-004/RESULT.json`） 在原SDK六发行环境完成400期及400投影，131.452秒；worker Job根54936、内层启动67368和外层43296均exit0，完整树/EOF/join/资源回收成立。最终 relocated001（外部历史/待归仓路径：`../../build/ms-per-date-cli-001/relocated-001/RESULT.json`） 使用原require-hashes离线安装七发行752条RECORD（相对直接wheel安装少7条来源元数据），全部产品文件相同；从新payload和新解释器运行400期/400投影、12份原生输出，164.812秒，逐日scope准确。worker Job根65524、CLI启动13072，安装/QA四个受管根35052/2336/48680/7008均exit0及完整回收。该组没有另采DLL实际装载子解释器的独立OS码，Job根与整树证明按其原字段解释。

两组最终阶段计数分别等于前述默认/逐日结果；包内105文件运行前后保持，当前5份生产源与最终安装快照保持，原catalog和原R28候选保持。回测报告和请求/安装/原生输出均由原NSH校验，C可消费固定原件。C当前源的配置/绩效直接读取旧内层session字段，新增纯值外层需由其唯一输入边界接线；C交接需求（外部历史/待归仓路径：`../../build/ms-per-date-cli-001/C-CONSUMER-REQUEST-001.json`）固定三个原文件SHA和实际producer资料。B保持C生产代码原状，C归档/HTTP/页面资格由其后继验收。

## 剩余范围

独立最终审查、完整制品/文件SHA及C完成归档接收按本根最终交接核准。完整400期RT/BT、同一候选持续AWP/策略、真实跨日、未知责任核查解除和整个模块B继续。历史15:00为明确假设，来源实际known_at/received_at保持，历史首次可知与修订未知。真实账户查询、委托/撤单及生产切换均0。
