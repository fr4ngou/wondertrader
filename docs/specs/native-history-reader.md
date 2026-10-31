# 原生策略历史可见性适配

后继约束：本页记录已有开发候选及其已验范围。用户要求全部复用WT重合能力后，接线按[原生能力收敛方案](../migration/native-market-integration-plan.md)重新核定；同步HTTP调用和自有窗口链继续暂缓作为最终默认架构。

类型：功能最终规格。状态：accepted，细化已授权的统一行情与原生策略适配；前缀 NHR。目标为同一原生CTA策略在数据缺失后补齐、增加分钟或修订已有分钟时，下一次读取获得当前合格历史，旧切片继续有效。复用[策略统一行情](strategy-market-access.md)，保持框架源码审批边界。

## NHR-R1 职责与宿主

链路为原生CTA stra_get_bars(m1) → 原 WtDtMgr(force_cache=false,times=1) → 自有 IDataReader DLL → 独立只读reader HTTP服务 → 既有StrategyMarket/CalendarProvider/MarketClient → WT原生Store与QMT。Python服务独立运行，无wtpy；不在C++复制日历、来源合并及补齐规则，不增加业务账本。数据源和金额/时间/日历资格仍由现有模块验证。

原生标准代码到六位.SH/.SZ证券使用受管配置中的明确映射，不推断产品、复权或连续合约。原生插件仅声明基础未复权m1能力；其他周期返回空。WtPorter强制缓存和重采样仍由其既有缓存语义处理，本规格不授它们同实例历史修订能力。验收须实际调用原WtDtMgr和CTA上下文，不能以新建reader代替。

## NHR-R2 尾部历史与服务契约

StrategyMarket增加 `tail_history_1m(symbol,count,*,end=None,as_of=None)`。count为正整数且不超过max_bars；end缺省为as_of向下取整分钟。沿权威日历由近及远按最多3日窗查找最后count个预期分钟，以同一总deadline和max_windows限制；校验复用原日历逻辑。日历返回足够分钟后，只读取选中的窗口；补齐、来源及全有或全无语义复用history_1m内部实现。预算内预期分钟不足时Pending，不制造历史、不以来源现存稀疏行数绕开缺口；非法值、未来时间和依赖异常沿原错误模型。

SDK版本增至0.7.0，基础六源码清单与storage extra保持；现有0.6接口向后兼容。原生reader服务随独立观衡运行适配交付，基础SDK不引入WT DLL或服务器依赖。

新增本机回环只读服务 POST `/api/reader/v1/history`，Bearer凭证必填且来自受管环境。协议 `guanheng.reader.v1`；请求严格字段：`api_version,id,action,symbol,end`及tail的`count`或range的`after`。id为32位小写十六进制；action为tail/range；symbol为六位.SH/.SZ；end为0或上海右端YYYYMMDDHHMM，range的after为排除端点。0表示服务时钟当前整分钟；显式end不能超出服务时钟。range调用既有history_1m(after+1分钟,end)，空范围可返回Ok空数组。

响应严格顶层 `api_version,id,instance_id,policy_id,status,data`，status为code/reason。instance_id为服务启动时的新UUID hex，policy_id为受管来源/日历配置版本（非空文本，最多128字符），插件固定期望policy_id并在首次成功时绑定实例，实例变更需显式重新初始化。失败data为空，reason固定脱敏。成功data为 `symbol,as_of,bars,provenance`；as_of为本次服务时钟的上海整分钟；bars每项 `minute,open,high,low,close,volume,amount,delivery`，量额已规范化。tail delivery为historical；range中恰等于服务as_of的条目为current，其余recovered。保留StrategyMarket的完整来源谱系，不重新提升资格。服务返回前校验原结果status/日期/来源引用及数量，不信任错误注入实现。

服务使用单个拥有线程创建和调用StrategyMarket，HTTP只读串行处理；凭证、factory和来源配置不由请求修改。请求/响应、socket读取和依赖调用均有明确预算；拒绝重定向、分块请求、重复字段、超大体、错误认证和版本。服务不接受账户、交易或任意透传操作。连接不保留，原始异常/配置不写日志。

## NHR-R3 插件读取与切片所有权

插件导出原createDataReader/deleteDataReader；配置模块为GuanhengHistoryReader。配置包含loopback base_url、token_env、policy_id、symbols映射数组（std_code/symbol）、timeout_ms、max_bars、max_live_bars、max_slices及max_symbols，全部校验后一次生效；无有效配置返回nullptr并保留固定错误原因。每个reader只允许初始化一次；重新绑定服务实例须停止旧reader并创建新reader，保持已返回切片有效。回调异常后恢复须同时重建可能暂存旧bar指针的宿主sink。

readKlineSlice仅处理已映射代码、KP_Minute1、合法正count及截止分钟。etime=0由服务确定当前闭合范围，显式etime保持未来拒绝。每次请求均重新调用统一服务，不保留历史负缓存或同条数缓存；响应须核对request id、版本、实例、policy、证券、时间、计数、顺序、合法OHLCV/量额及delivery。失败、未就绪和零条结果返回nullptr，避免CTA访问空slice末条。

每个返回slice拥有独立数组，并用共享内存预算对象计费；调用方release后归还预算。新读取不修改旧slice，reader对象销毁后旧slice数据仍有效；插件DLL及依赖须维持加载至最后一个slice完成release。stop不等待调用方持有的slice释放，DLL卸载由宿主在全部slice释放后编排。旧slice尚存时再次读取受max_live_bars/max_slices约束，不能无限增长。网络I/O在有限总预算内，不在锁内调用宿主sink。

## NHR-R4 分钟事件与恢复

首次read尝试即登记代码及所需count；即使缺历史返回nullptr，后续仍可恢复。成功tail读取建立该代码的事件基线，首次历史预热不投递on_bar。尚无基线的代码在onMinuteEnd用已登记count重试tail；完整历史取得后，仅当末条=宿主本次闭合标签=服务as_of时才投递该当前条，其余只作预热。已有基线时onMinuteEnd请求range(after,end)，沿统一历史完整性和预算；缺口/错误不推进基线。成功range只把仍为服务当前闭合分钟、且等于宿主本次闭合标签的current投递给sink；recovered用于历史可见性并推进基线，不伪装当前事件。历史修订只影响后续读取，不重复投递已确认分钟。

一轮所有代码先取得并验证结果，再向sink逐项on_bar，最后on_all_bar_updated。bar内存保持至最后回调返回，覆盖原WtDtMgr暂存指针及WtCtaEngine等待pool的行为。回调正常返回后确认本轮基线；回调异常结果未知时隔离事件投递并保留诊断和本批数组，禁止自动重放可能已执行的current。再次tail不重置已存在事件游标。退出期间停止准入新批；已开始投递的批完整执行到on_all_bar_updated，确保原WtDtMgr清空暂存指针。

## NHR-R5 并发与退出

真实宿主可能从初始化线程、行情/ticker线程和策略pool调用reader。插件支持并发读取与串行分钟事件；网络及状态互斥有明确职责，等待锁也计入截止。回调时释放所有会阻塞readKlineSlice的锁，允许on_bar/on_all_bar_updated内同线程或pool线程读取历史。重入/并发onMinuteEnd明确拒绝或跳过本轮，不能递归投递。

提供自有受管stop入口（C++方法及可选导出）停止新准入并等待在途读取/事件结束；同步或pool回调请求stop仅标记并返回Pending，已准入的完整回调批返回后完成关闭，禁止自等死锁。析构前宿主停止调用并完成stop；若原WtRunner没有调用插件销毁，其进程退出行为须如实记录，不能据此声称优雅释放已完成。类不创建后台线程；仍需证明网络截止、旧slice持有、并发发布、回调重入和停止等待的边界。

NHR-R5补充：provider异步系统回调属于停止依赖。IReaderHistoryProvider提供绝对截止的drain_callbacks；同步provider缺省无需排空，异步实现必须覆盖。StrategyReader关闭准入并等待active=0后，释放控制锁，在同一个stop截止内调用provider排空；Pending/Timeout/错误保留对象、SPI和DLL，外部继续确认。多个stop可并发调用，provider内部串行排空并计入锁等待。批回调执行期间所有线程的stop均保守返回Pending，防止同线程或pool反向等待；外部管理者在批结束后再次确认。

ReaderHttpClient复用WinHttpSessionDrain系统通知，固定64个未排空session槽，创建session前准入；并发read在短锁内登记session，网络与用户代码不持此锁。drain与登记由带截止的互斥保护，stop成功须证明session最后回调返回。直接client调用方在最终drain前停止新read并等在途read结束；drain本身不禁止后续读取。旧式析构保留等待排空的安全兜底，可能无界；受管宿主必须使用显式有界stop。切片仍独立持有，最后slice释放前保留DLL。

本轮必须验证真实WinHTTP同步关闭及晚到回调、并发read与停止、stop截止后保留与再确认、回调内stop和宿主保留slice。使用测试专属门闩观察真实回调，生产制品不含门闩；分别记录未持有slice时显式卸载和持有slice时必须保留DLL的资格。

## NHR-R6 验收与交付

必须覆盖：同实例首次缺失→补齐、增加分钟、同数量修订、持有旧slice；真实HTTP服务→既有SDK/nativeStore链；来源/日历缺失、身份变更、恶形响应、空/未来、预算/超大、并发读、回调pool重入、重复/恢复分钟、未知回调结果和退出。使用原WtDtMgr/CTA上下文读取同一实例，区分插件单测、原生宿主和真实来源资格。受管服务正常/故障/空状态、配置示例、模块/操作文档、独立full审查、原生打包和搬迁验证均须完成。

首次实现沿本机回环独立服务验证；生产日历、服务发现、发布切换、完整业务页面及交易恢复继续按总验收地图推进。新增实现不修改冻结WT框架文件；发现原公开接口不足时给出原样证据和具体方案，再按用户批准边界处理。
