# WonderTrader 历史读取与同实例可见性

类型：长期模块说明。范围：官方 `WtDataReader`、历史 loader、原生策略数据管理器与自有 reader 插件接缝。状态：固定源码设计已核实；运行验收需分别绑定 reader、宿主、策略入口及数据身份。

本文以官方提交 `08b230dd05facf6d650d949bfe51054115a2ecb1` 为准。DSB 编解码、writer 生命周期及文件故障语义见[原生存储设计](wondertrader-storage.md)；策略业务接口和来源资格由[统一行情规格](../specs/strategy-market-access.md)定义。

## 历史数据与运行缓存的职责

```text
外部历史生产者 → WtDtHelper.store_bars → his/min1/<交易所>/<代码>.dsb
                                           ↓ 首次装载
策略 stra_get_bars → WtEngine → WtDtMgr → IDataReader.readKlineSlice
                                  ↓           ↓
                         可选重采样/强制缓存    WtDataReader 历史缓存
                                              ↑
                                  IHisDataLoader 首次同步填充
```

`store_bars` 写入一份完整的压缩历史文件。应用要增加历史条目时，需要合并原数据并发布完整新文件。文件发布成功、原 helper 回读成功、同一 reader 可见和同一策略可见，属于四项独立结果。

原 `WtDataReader` 以 `stdCode#period` 缓存历史数组。`readKlineSlice` 只在 key 尚不存在时调用 loader 或读取 DSB；后续读取直接使用已缓存数组。缓存建项发生在文件存在性和数据结果确认之前，因此第一次读取缺文件，也会留下空缓存项。增大 count、改变 etime、更新文件、再次调用 init，均不构成该实现中的历史失效协议。依据：[首读与缓存命中](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataReader.cpp#L1421-L1584)、[初始化](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataReader.cpp#L151-L187)。

`onMinuteEnd` 遍历已订阅缓存，并检查 `rt/min1`、`rt/min5` 映射中的新条目；它推进实时游标并回调 sink。该路径没有历史 DSB 重新装载操作。发布闭合源 1m DSB 后，需要自有消费适配安排历史重读及当前分钟投递，不能从 DSB 文件变化自动推导出 WT `on_bar`。依据：[分钟闭合处理](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataReader.cpp#L1995-L2104)。

公开 `IDataReader` 提供 init、readKlineSlice、onMinuteEnd 和行情读取，当前版本没有 invalidate/reload/clear-history 接口。工厂允许创建独立 reader；新对象会重新装载历史，原对象的缓存和原策略的状态仍按原生命周期保留。[接口定义](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IDataReader.h#L148-L249)。

## 历史 loader 的实际契约

| 接口 | 责任与实际调用时机 |
|---|---|
| `loadFinalHisBars` | 提供最终历史序列；原 reader 先尝试该入口，成功后复制到历史缓存，后续不再进行普通原始数据加工 |
| `loadRawHisBars` | 提供原始历史序列；final 返回 false 后由原始/复权/连续数据装载路径按需调用；直接原始路径再失败则回退 DSB |
| `FuncReadBars` | 本次加载的同步回传；reader 在回调中复制条目。回调参数不含读取窗口、count 或请求截止预算 |
| `loadAllAdjFactors/loadAdjFactors` | 复权因子装载；其成功不能代表 K 线数据已刷新 |

loader 的布尔结果和缓存资格应一致：调用方需在返回 true 前完成完整且合格的同步回传。原接口允许应用首次按需取数；同一个已缓存 key 的再次请求不会触发 loader 重查。初次失败后的自动补齐，应在进入原 reader 前完成，或由自有数据访问层承担缺口恢复。依据：[loader 声明](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IDataReader.h#L85-L143)、[final 回调复制](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataReader.cpp#L850-L885)、[raw 与文件回退](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataReader.cpp#L1463-L1505)。

`WtPorter.register_ext_data_loader` 将 C 回调交给 `WtRtRunner`。runner 为本次加载记录单一 `_feed_obj`、`_feeder_bars`，再调用外部 loader；外部在该调用中通过 `feed_raw_bars` 回传数据。该 feed 接口没有证券、请求编号或缓存版本，无法表达任意目标的独立刷新。raw 装载保存的 obj 指向当前加载栈上的临时 buffer，延迟回传会跨越其生命期；应在 loader 返回前完成回传。依据：[Porter 导出](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtPorter/WtPorter.cpp#L77-L90)、[runner 加载与回传](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtPorter/WtRtRunner.cpp#L194-L288)。

该固定版本的 `feedRawBars` 检查 `_ext_fnl_bar_loader` 是否已注册。使用 Porter 的 raw 路径时，也需要注册 final 回调；final 可明确返回 false，再让 raw 回调同步填充。直接 `IDataReader::init(..., IHisDataLoader*)` 的验证仅覆盖 reader/loader 接口，Porter C 封装的行为须另验。

## 同一策略还受数据管理器约束

`CtaStraBaseCtx::stra_get_bars` 经 `WtEngine::get_kline_slice` 调用 `WtDtMgr`，基础 `m1` 对应 `KP_Minute1`、times=1。上下文在非空 slice 上直接访问末条数据，所以正式 reader 的无数据、失败和未就绪结果应返回 nullptr；返回非空零条 slice 无法满足此消费前提。依据：[CTA 入口](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp#L1579-L1619)、[引擎转发](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtEngine.cpp#L598-L627)。

| 宿主/请求 | 数据管理器行为 | 适配影响 |
|---|---|---|
| 原生 `WtRunner`，基础 1m | 默认 force_cache=false，times=1 时每次转发给 reader | 自有 reader 可在保持同一实例的情况下逐次返回当前合格快照 |
| `WtPorter/WtRtRunner` | init 明确传入 force_cache=true，基础周期也复制到管理器缓存 | 仅替换 reader 无法保证后续相同 count 的策略请求重新调用 reader |
| 重采样周期 | 经过管理器缓存；已缓存条数足够时直接返回 | 历史修订还需要相应派生结果重建语义 |

依据：[WtDtMgr 缓存条件](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtDtMgr.cpp#L397-L487)、[WtRunner 默认初始化](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtRunner/WtRunner.cpp#L419-L429)、[Porter 强制缓存](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtPorter/WtRtRunner.cpp#L878-L890)。

`IDataReaderSink::on_bar` 会进入 `WtDtMgr::on_bar`；强制缓存的基础周期直接 append，随后 `on_all_bar_updated` 将事件交给策略引擎。这个接缝适合按序的新闭合分钟，缺少历史替换和去重语义。历史补发、已发布分钟修订或重复投递，应按业务消费契约处理；直接回放为当前 `on_bar` 会改变策略事件和缓存内容。依据：[管理器回调](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtDtMgr.cpp#L104-L217)。

## 保持框架源码的适配路径

1. 外部业务策略使用统一 `StrategyMarket`，每次从既有服务 Store 读取经过来源和覆盖验证的当前 DSB；历史预热与 current/recovered 闭合分钟分别按现有消费规格处理。该路径的验收覆盖业务调用本身。
2. 原生 WT 策略需要使用 `stra_get_bars("m1")` 时，通过 `data.store.module` 装载自有 `IDataReader` DLL。原 `WtDtMgr::initStore` 已从模块取得 `createDataReader` 并注入 sink/loader。插件保持同一个实例，按请求读取经过准入的官方 DSB，或委托既有权威 Store；保留原 helper 作为唯一 DSB 编解码实现。模块选择是既有配置接缝。[模块装载](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtDtMgr.cpp#L50-L86)。
3. 自有插件负责快照和切片生命期：原 `WTSKlineSlice` 保存指针，默认不拥有数组。可以派生有所有权的 slice，让每份返回结果持有其数据，直到调用方 release；新文件到达时不修改仍被消费的旧快照。原 `WTSObject` 有虚析构，允许该所有权方案。[slice 布局](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSDataDef.hpp#L205-L263)、[基类生命期](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSObject.hpp#L21-L50)。
4. 正式适配先限定已验宿主及周期。WtPorter 强制缓存、重采样和历史修订继续保留独立验收；可让其中的自有策略直接调用统一历史入口。要求原 `stra_get_bars` 对这些情况也提供实时历史修订时，需要另定完整管理器/消费者语义，并按上游维护规则评估接缝或申请框架变更。

插件的必要合同包括证券/周期准入、来源/会话/资格校验、日历覆盖、截止预算、DSB 内容身份、异常与空结果、并发所有权、快照内存上限、当前分钟事件与历史恢复分类。直接逐次调用 helper 的实验只能证明公开接口可实现同实例重读；完整合同、真实输入和策略调度仍须完成正式实现与验证。

## 验收必须区分的结果

- 同一个 reader 首先读到两条历史，外部发布第三条后再次读取；同时比较条数、分钟、OHLCV 和量额。
- 初次读取缺文件，外部补齐后同一个实例重试；记录 loader 实际调用次数。
- 外部修订已存在分钟，保持条数不变；核对新读结果与仍持有的旧 slice 各自内容。
- 分别执行 helper 直接回读、原 reader、raw/final loader、自有插件和实际策略入口；新建实例单列为对照。
- 使用真正运行宿主验证相同 count、最新时间、跨日、重采样、Porter 强制缓存、空结果和异常结果。
- 对闭合分钟验证当前事件只按约定进入策略，历史/recovered 保持预热语义；同实例历史可见性与策略事件投递分别通过。

原样 reader 的缓存事实用于决定适配责任。只有绑定完整宿主和消费者的正向及异常验收通过，才能声明同一运行策略已具备自动补齐后的历史可见性。
