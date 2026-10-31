# 个人观察自选与WonderTrader原生能力的边界

类型：源码核实记录。状态：静态核实；实现与运行待验。适用范围：独立观衡应用的个人观察自选。

## 已核实的接缝

| 能力 | 实际源码依据 | 职责与本功能的使用方式 |
|---|---|---|
| WT-S05 策略自定义状态 | 固定来源CtaStraBaseCtx.cpp的save_userdata/load_userdata、stra_save_user_data/stra_load_user_data；ICtaStraCtx.h公开接口 | user data在策略上下文持有，文件名ud_加策略名；保存标记在tick/调度等策略路径处理。继续供策略状态使用。个人自选独立于策略启动和策略名，偏好保存由应用拥有。 |
| 原生运行配置 | 固定来源WtRunner.cpp的initCtaStrategies/initEngine/initParsers/initExecuters | 配置用于装配策略、行情与执行。自选增删只改变个人观察偏好，策略配置保持其原生owner。 |
| WT-D06 历史读取 | 当前WtDtServo.h/.cpp的get_bars_by_range/get_bars_by_count及现native_chart.py | 点击列表代码继续沿现分钟图→SDK→WT读取。现证券准入为normalize_chart_symbol的六位数字和.SH/.SZ。 |
| WT-D06 行情订阅 | 当前WtDtServo.cpp的subscribe_tick/subscribe_bar与WtDataManager.cpp的subscribe_bar | 订阅改变行情接收状态并持有实时bar；保存自选独立于订阅，实时订阅按其规格另行接入。 |
| 应用有界I/O | 当前reading.BoundedReader与app.py生命周期 | 原2 worker/4 queue处理偏好I/O；复用现线程owner与关闭序列，配置关闭时零偏好API。 |

固定来源取自既有build/native-execmon-owner-001/upstream；本轮逐项读取副本并核对source-identities.json内摘要，未运行Git、编译或上游程序。Servo条目明确为当前工作树接口，不能据其身份声称纯上游。来源清单共44个上下文文件，覆盖实际main→IndependentApp→MinuteWorkspace、旧未挂载MarketPage/api/types、App/设置/读池/同源guard及上述原生接缝；范围之外的插件与第三方应用能力未作完整清点。

## 最小应用差额

已核接缝分别拥有策略状态、运行配置和行情数据。独立SPA的个人偏好需要明确的应用owner，采用一个显式根中的小型JSON及OS单写者锁，完整替换带版本比较。行情数据仍由WT保存，实际账户事实仍由券商/对应查询观察，策略理论状态仍由WT上下文拥有。旧Control服务、旧数据库及旧自选audit_event_id不进入此链。

单操作者模型与旧未挂载1.0 DTO的兼容边界、容量、并发、结果未知和重启验收由[个人观察规格](../specs/personal-watchlist.md)统一定义；长期归属见[ADR-0008](../architecture/adr/0008-personal-watchlist-ownership.md)。本轮执行0，不授安装、界面、原生或生产资格。
