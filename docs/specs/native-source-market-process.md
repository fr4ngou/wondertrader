# 原生来源历史查询受管进程

类型：功能最终规格。状态：accepted。前缀：SMP。负责人：模块A。依据：[三模块交付](../migration/parallel-system-delivery.md)中的A历史服务与M1/M3；WT按[WRI](independent-wt-runtime.md)托管本服务，独立观衡消费只读接口。

## SMP-R1 复用与范围

正式入口`integrations/guanheng/source_market_service.py`在终端外运行。复用NativeSourceMarket、NativeHistory/原生文件ABI、MarketHTTPServer和现有MarketClient的显式源分钟/日线查询；不复制行情、不新增数据库、不改QMT策略或WT核心。允许source-store/source-stores及[DSH4](qmt-source-daily-history.md#dsh4-统一公开查询与目录)显式source-catalog配置，普通market_service旧入口保持。

独立原生安装组件`GuanhengMarket`包含原生Reader/Helper、所需运行库、Python闭包及许可证。入口通过绝对安装路径以`pythonw -I -B`启动，从安装自身根装配固定模块，不依赖旧QMT源码、工作目录或PYTHONPATH。来源store位于显式外部数据目录，包与数据分别管理。

## SMP-R2 输入与身份

入口参数为`--config <绝对路径> --config-sha256 <摘要> --control-directory <新绝对目录> --control-id <UUID>`。控制目录末级等于control_id，由子进程沿既有私有目录工具创建，已存在即拒绝。

子配置固定schema=`guanheng.source-market-service.v1`，字段：source_configuration、listen、token_env、socket_timeout。source_configuration固定path/sha256，引用至多1MiB的原source配置；先读并核摘要，再把同一字节解码交NativeSourceMarket，避免再次读取脱离身份。listen固定host/port，host仅数字回环，port为1..65535。token_env是环境变量名，凭据只从环境读取。socket_timeout为0.1..30秒。原Reader DLL、store收据和内容摘要继续由原owner校验。

## SMP-R3 生命周期与控制

一个创建线程拥有Reader与HTTP server。全部目录注册及监听完成后发布ready.json：schema=`guanheng.source-market-ready.v1`、control_id、pid、configuration_sha256、listen_host、listen_port；ready只证明本次监听/来源注册，行情时间和完整覆盖另验。

父进程复用ManagedLocalProcess，停止文件合同为schema=`guanheng.source-market-stop.v1`、control_id、deadline（monotonic绝对秒数）。子服务逐请求之间读取停止，不续期；每个HTTP请求沿原socket/原生处理范围，父Job负责不可中断原生调用的最终硬截止。

收到停止后先停止HTTP准入，创建线程关闭server及原Reader；在原截止内确认后发布closed.json：schema=`guanheng.source-market-closed.v1`、control_id、pid、configuration_sha256、status=`stopped`、server_closed=true、native_closed=true、error_code=null。发布使用已有完整临时文件/原子替换工具。失败只发布固定stage/异常类别，不输出配置、令牌、路径、证券逐行数据或原异常文本；不发布成功closed。实际退出/树/EOF/join由原父owner另核。

WT父配置沿现有受管字段pythonw/sha、entry/sha、configuration/sha、control_root、startup_seconds、stop_seconds、max_output_bytes组合，历史组件由WRI登记并沿原ManagedLocalProcess启停。A交付子服务及部署合同，C配置独立观衡的只读SDK地址；观衡启停不改变本服务生命周期。默认未配置历史组件时保持关闭。

## SMP-R4 验收

先验证安装/搬迁入口→真实已导入DSB→原Reader→实际HTTP→同版独立SDK的首次历史查询、旧值标签/来源/单位保留、原停止文件及实际进程回收；再由C接App/页面。完整目录注册与抽样读取分开，来源单位unknown不能被此进程改为标准股/元。

随后覆盖配置/摘要/令牌/地址拒绝、无来源、错误stop身份、过期关闭、已存在控制根、HTTP异常及关闭证明，核旧market_service入口兼容；独立审查按公共接入/生命周期变化触发full。真实QMT、交易、生产切换均不在本切片范围。结果在模块A证据登记，不能以库安装代替M3整体验收。
