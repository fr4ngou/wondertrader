# 模块C独立只读部署接线清单

类型：阶段交接和实施清单。状态：in-progress。依据：2026-10-29用户最终确认的[观衡边界](../specs/guanheng-operator-platform.md)。共享WT入口、系统方案和发行装配由A统一集成；B保留运行与交易生产者，C保留页面及只读消费者。源码迁出、接口及运行资格按下列后继分别登记。

2026-10-30迁出分工已固定：A子agent独占apps/wt_runtime/guanheng_wt_runtime，迁出managed_local_process、thread_owner、qmt_host_process、history_preparation_process、quote_collection_process、source_market_process；B迁出执行及策略启动依赖。C保持原App这六份文件，待新包交付及根协调后处理退出/重导出。C后继负责App公共配置/lifespan退出运行管理，按一次交付的WT只读状态合同替换消费者。观衡当前私有历史辅助进程与WT最终数据服务分别记录，最终历史服务归WT。

2026-10-30实施后继：A独立WT交付f7b7a8d2…5283已消费，主协调确认同机公开文件读取。当前源码App/lifespan已退出Host、采集、历史、执行、账户扫描、回测运行、策略配置写和观察采集进程构造；只拥有Web读池、个人自选及观察读取。旧环境部署参数不再消费，继承旧值保持只读功能可启动，CLI Host参数退出。新a29普通29发行/4782 RECORD已安装；独立WT真实CLI+原Reader历史+采集协议替身的main002完成观衡两次正常退出、一次异常exit7、再启动读取与WT正常关闭后最后状态读取，期间同WT PID/组件PID、计数持续、历史逐值相等；App无WT控制owner、正常读池0。代码保护与业务观察仍在补齐，尚未整体交付。

账户/策略后继已沿NRT-R20实现：B在原执行owner公开状态定位现有strategies.json，沿原ready/control_id/配置SHA绑定；C读取并复用原业务投影及账户DTO3，逐组保留已知持仓/资金和时间，原未发布委托/成交分别缺失。普通a33及a34消费B main005实际结束结果，HTTP/生产SPA核持仓/可卖各200、可用82000及原P/A时间、停止后最后结果；原B文件前后摘要相等。真实券商来源及运行中联合消费继续单独验收。定位公共字段归WRI/NRT，C不猜目录、不继承执行owner；无额外金融账本。

## 迁出前入口与收敛位置

| 原文件/入口 | 旧候选事实 | 最终职责及消费者保留方式 |
|---|---|---|
| apps/guanheng/guanheng_app/app.py::create_app/lifespan | 构造并启动qmt_host_process、qmt_collection_process、execution_process；finally把三者纳入共同关闭 | 三个控制owner移交WT独立入口，观衡只创建读取客户端，关闭时仅结束自己的请求/缓存 |
| guanheng_app/settings.py、__main__.py | GUANHENG_QMT_HOST_CONFIG、GUANHENG_QMT_COLLECTION_CONFIG、GUANHENG_EXECUTION_CONFIG及SHA，CLI的--qmt-host-config | 最终观衡装配退出上述运行部署参数；保留只读服务地址、认证和读取截止，现有现场配置不改写 |
| guanheng_app/qmt_host_process.py、quote_collection_process.py | 本地Host/采集的部署校验、Job及生命周期 | 实现可由WT运行包继续复用，C停止把它们装进最终观衡生命周期 |
| guanheng_app/execution_deployment.py、execution_process.py、execution_configured.py、execution_strategy.py | B部署模型、执行进程及原生业务桥 | B/A独立运行使用；C不修改B的三个execution实现文件，改为消费其公开投影 |
| guanheng_app/execution_observation.py、strategy_runtime_routes.py | 观察器继承运行owner，GET /v1/ui/strategy-runtime从app.state.execution_process取observe_strategy | 保留中文业务DTO/只读路由和前端验证，观察连接改绑WT公开生产者；当前读取依赖本地控制owner需解除 |
| guanheng_app/execution_status.py、operations.py、collection_observation.py | GET /v1/ui/execution-process、/operations/status从本地owner取状态；采集读取器复用SDK runtime_status | 继续复用固定归约/元数据读取实现；由WT发布权威状态，C客户端只读；本地文件/PID不能代替跨部署存活合同 |
| app.py中的GET /v1/ui/qmt-host、/qmt-collection | GET本身只读，状态取App所持进程 | 可保留兼容投影，数据来自WT只读服务；GET不创建或接管控制owner |
| guanheng_app/native_chart.py、operations.py::query_status、settings.py中的MARKET_URL/TOKEN | 已使用MarketClient读取独立服务，具总截止/去敏/正常空失败语义 | 保留原SDK和行情页面；最终观衡只配置WT服务，已有远程读取路径可直接复用 |
| guanheng_app/source_market_process.py、source_market_routes.py | App可启动私有历史查询服务并观察其进程 | 最终跨部署历史服务归WT；行情读取接口保留，观衡退出相应生命周期配置 |
| guanheng_app/history_preparation_process.py、history_preparation_routes.py | App可托管来源缓存补齐进程；读取接口本身不发起补齐 | 缓存准备/下载动作归WT；观衡保留已发布覆盖/状态读取 |
| guanheng_app/account_scan.py、account_scan_runtime.py、account_projection.py、app.py账户GET | App管理账户扫描子进程并共享读取Future，执行四类只读查询 | 复用账户DTO/去敏归约/页面，账户原生查询owner归WT，C从公开只读服务取得各批事实 |
| guanheng_app/backtest_workspace.py、backtest_routes.py、strategy_host.py | App可启动/取消隔离回测和读取完成归档 | WT独立入口负责运行，C保留任务/配置/比较/报告展示；POST启动/取消退出最终观衡装配 |
| guanheng_app/strategy_configuration_routes.py及配置owner | App存在校验/PUT留存入口，页面已仅名称/简介/版本 | 实际运行参数/激活/回退归WT；C最终按只读合同展示实际版本；个人观察偏好保持与WT参数分开 |

上表省略的guanheng_app路径均相对apps/guanheng。源码位置说明当前事实，最终部署归属以COP及主会话共享合同为准。原控制类退出观衡发行与其在WT包复用分别处理，保留旧开发证据和已发布原件。

## 公共读取合同与实际缺项

行情继续消费独立MarketClient。运行状态沿WRI公开文件、策略/账户沿NRT-R20同代业务定位，C已实现只读客户端及DTO3。采集业务明细尚缺运行侧只读定位；WT原生文件、连接计数和观察原实现保持生产者所有。C不自造WT存活证明、恢复状态或第二份金融账本。

其余公开观察需求集中为一批：采集owner交接既有status/failure文件的只读定位及原control_id/PID/配置SHA；回测入口提供原任务/已保存归档和实际配置的只读定位/版本；账户名称及环境仅在原owner已知时提供有限元数据。生产者沿原schema及版本治理，C不猜控制目录、不从路径或资金推导这些事实。C在已有状态/历史/业务观察主链上继续推进，不以此恢复Web控制owner。

只读HTTP等待取消仅退出C消费，WT任务/订阅/命令责任保持。来源不可用时C保留同查询成功值和时间，明确过期/失败；WT重连后重新读取。观衡升级回退核公开合同兼容，WT持续运行和资金/委托责任独立验证。

验收沿原完整单策略主链，增加WT先运行→观衡启动/读取→关闭观衡→确认WT同PID/同控制身份、采集继续→重启观衡读取同结果。再核观衡崩溃/升级、WT断连/恢复、正常/空/失败与进程/管道关闭；现有App托管组合不提升为新部署边界已完成。

## 当前现场

本次只登记接线和修订C规格，未改变正在运行的QMT、跨夜采集或WT实例。用户预览18120为开发预览：账户、QMT Host、采集和执行均未配置；其私有历史查询服务仍由该旧候选App托管，独立观察归档已接入。该预览保持可看，最终独立部署资格待上述迁移及真实非干扰验收。现场实例不会被文档修订自动停止。

2026-10-30现场保护身份以后继主协调通知为准。先前WT74964/历史27980/采集30588的真实隔离证据保留，主协调已正常关闭该实例并交接到WT72824/HPR38432/历史4408/采集56840。当前连接仅在build/wt-live-host-data-composition-001/ACTIVE-READ-CONNECTION.json受控保存，读取凭据不进入本交接。C未操作新实例、QMT或现场消费者。上段原“本次只登记”保留最初盘点时点，后继代码及隔离验收见[独立观察证据](../evidence/2026-10-30-independent-observer.md)。
