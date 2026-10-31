# 历史查询服务的应用托管

类型：历史功能规格。状态：superseded。前缀：SMA。下文保留原App托管方案的开发范围；现行生命周期归属沿[WRI](independent-wt-runtime.md)，历史子服务合同沿[SMP](native-source-market-process.md)。WT独立管理历史服务，观衡仅消费SDK及只读运行状态，退出观衡后WT和历史查询继续运行。完整目标沿[COP](guanheng-operator-platform.md)。

## SMA-R1 职责与复用

App生命周期拥有一个SourceMarketProcess，复用原ManagedLocalProcess的创建期Job、真实PID归属、有限输出、原截止停止及树/EOF/join回收。新适配只负责部署值、固定argv和SMP收据，不修改通用监督行为。原生能力对应WT-D03/WT-D05/WT-O01/WT-O07：原NativeSourceMarket、Reader和HTTP子服务仍是数据和原生资源owner，App补充独立进程管理。与采集进程分别管理，App不复制历史、增加数据账本或重建读取器。

## SMA-R2 显式部署与身份

GUANHENG_SOURCE_MARKET_CONFIG与GUANHENG_SOURCE_MARKET_CONFIG_SHA256同时提供；空值默认关闭，配置错误只降级此项。父JSON schema为guanheng.source-market-process.v1，固定字段pythonw/pythonw_sha256、entry/entry_sha256、configuration/configuration_sha256、control_root、startup_seconds、stop_seconds、max_output_bytes。路径、摘要、E盘控制根、启动0.1..120秒、停止0.1..60秒和输出1024..1048576字节沿原父部署约束；部署正文至多64KiB。

受管启动核pythonw/entry原字节及子配置摘要。子配置业务语义由SMP子服务校验，父只提取固定listen数字回环地址和1..65535端口以绑定本次ready，原有限读检查保持。argv严格沿SMP，凭据只注入环境。SDK的URL/token独立显式配置，App不猜端口、不自动重连其他服务。

ready和closed逐字段、schema、control_id、configuration_sha256和PID校验；ready额外匹配本配置的listen_host/listen_port，真实PID/Job成员仍由原监督者核。closed须server_closed/native_closed为true，status=stopped且error_code=null。一次App生命周期只启动一次，失败保留首故障和清理状态；恢复需要维护人员核原因后重新启动App，不自动换实例重试。

## SMA-R3 应用与页面

owner先发布到application.state.source_market_process，再在既有有界池中沿一次启动绝对截止调用start。部分启动、启动超时及后续构造失败均进入同一finally。关闭先停止/排空App消费者，再关闭历史查询服务、行情采集和账户Host；所有阶段共用一次D，为各子进程保留声明停止窗口，某owner失败仍继续关闭其他owner并记录未确认结果。

安装CLI检查App全部owner的关闭总结果；资源收尾未确认返回退出码2，确认完成返回0。默认无子进程的App仍拥有读取线程，采用相同结果归约，新owner无需追加配置字段特判。

GET /v1/ui/source-market固定无请求参数，返回guanheng.source-market-app-status.v1、read_only=true、观察时间、有限process投影及data_qualification=not_checked。公开错误只用固定中文和错误码，无路径、配置、凭据或原异常。生产SPA的系统状态页独立读取此入口并展示当前App拥有的历史查询进程、原因、影响和处理；读取失败保留该卡明确失败，其他来源各自呈现。本卡ready仅证明本实例监听收据，来源质量、完整性、单位、时效另由历史查询结果解释。

## SMA-A1 验证标准

先跑正式App父owner→搬迁GuanhengMarket入口→真实已导入DSB→原Reader→SDK→App历史HTTP→生产SPA及停止回收；读取来源原值/标签/Unknown保持。A真实候选到位前可验证父接线与冻结合同，不能据此完成最终集成。

随后覆盖默认关闭、配置单缺/摘要/路径、错误ready身份/端口、错误closed/未知退出、启动失败、部分启动异常、关闭顺序/原预算、故障继续清理、只读HTTP与去敏、页面失败/重读。复用原监督者未变的生命周期证据，新增公共接线与资源边界按独立full审查，记录确切SHA。真实QMT、生产发布和真实交易另按授权验真。
