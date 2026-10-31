# 受管策略读取原生分钟文件

类型：功能规格。状态：accepted。前缀 NMR。范围：模块A向原CTA宿主交付可停止的原生分钟Reader，沿[三会话分工](../migration/parallel-system-delivery.md)。

## NMR-R1 配置与复用

现有 `ReaderGuanhengRealtime` 组合器新增可选对象 `minute_native`。缺少该对象时保留原 StrategyReader/HTTP 分支。提供时选择原 `WtDataReader` 读取及分钟通知，日线分支保持原规则；WT框架与虚接口不改。

`minute_native` 只允许原 `path`、可选 `his_path`、`adjfactor`、`adjust_flag`；路径/标量按现有组合器验证。原顶层 `symbols` 继续配置std_code/symbol映射和允许读取证券，原max_bars/max_live_bars/max_slices为分钟分支的有限复制预算。原HTTP字段在native模式中不创建客户端。禁止两条来源同时服务同一m1请求。

## NMR-R2 读取与分钟通知

native模式在初始化时将原生分钟配置和真实基础资料交给原WtDataReader。标准证券代码须在配置映射及基础资料中存在。按原上下文当前日期/分钟或显式截止读取；显式截止不得晚于当前上下文。源数据时间有序、有限数值、条数和块数在请求预算内；返回副本拥有独立载荷，不返回原缓存借用地址。数值、时间标签、原文件格式、原索引及复权逻辑由WT拥有，适配器不另算分钟或换算单位。

onMinuteEnd沿原WtDataReader执行并通知原sink，调用阶段和线程沿WT原生调度。组合器只提供既有准入与生命周期，不新增聚合器、时钟或框架并发保证。历史追赶的回调不自动取得当前可交易资格，策略预热与调度由原上下文和业务核维护。

## NMR-R3 停止与兼容

复用现有Flight准入/计数：stop关闭新调用，等待在途读取和分钟回调返回，再销毁同步原生delegate；回调内stop返回未完成，控制线程后继收口。此前已返回的复制切片可保持至其最后release。原stopDataReader/deleteDataReader导出、默认HTTP和d1行为保持；DLL保留到进程退出。所有等待受原超时及外层Job总截止管理。

## NMR-R4 验收

先以真实上午三证券的稳定副本及活动采集根沿安装DLL的create/init/read/onMinuteEnd/stop/delete走完整链：各120根与原Helper逐值一致，09:31预热后各119后继事件、重复0，stop后拒绝读取且旧副本可读。再覆盖配置拒绝、空/短窗口、未来截止及原HTTP/d1兼容，并核实际原CTA宿主装配；实际下午自然调度、重连、跨日和完整策略分别取证。


### NMR 实施细则

显式native模式的symbols继续严格数组/唯一映射准入，std_code经原CodeHelper解析，symbol的证券/交易所须与解析及真实contract/product一致。原HTTP字段允许随组合配置保留，在此模式不读取token环境、不创建HTTP客户端。minute_native未知字段拒绝；分钟复制预算使用顶层max_bars/max_live_bars/max_slices和原默认/上限，与daily自己的预算独立。

显式native模式在两个原WtDataReader初始化前，沿原StrUtil标准化路径，并用实际映射证券核渲染字节容量：分钟RT完整文件名（含结尾零）不超过原256字节，两个delegate的初始化日志、历史文件错误日志及可选adjfactor错误日志（含结尾零）不超过原512字节。组合路径及原默认his子目录共同计入；超限直接拒绝，原实现不接收该配置。缺省HTTP模式保留原配置行为。验收覆盖RT渲染255/256字节、初始化日志511/512字节及长path/his_path/adjfactor组合，并确认拒绝发生在原init之前。

组合器仅序列化同一原生分钟delegate的同步调用；同步回调/loader/logger重入同一delegate立即拒绝，避免适配器等待自身。这不授原WT跨线程调度/快照一致性保证。当前native分钟调用被Flight纳管，控制线程stop等待在途同步回调，回调线程stop只关闭准入并返回false，后继控制线程收口；旧HTTP回调路径保留原停止规则。

复制前按原block计数核总量，时间标签不越当前上下文/显式截止、无溢出且有序，交易日字段有效、所有原double字段有限；不强行标准化价量/OHLC关系。原Reader完整初次加载/缓存/压缩及调整仍由WT负责，复制预算不声明限制原Reader冷加载全部历史分配。

构建固定原WtDataReader源码与原已验依赖，原导出只在构建时重命名以避免与组合器导出冲突；不改上游文件。原CTA宿主资格通过固定已验WtCore/WtDtMgr的require_stop装配与真实原值读取/stop/release核验，完整B CtaExecutionSession及自然时钟后继组合分别验收。
