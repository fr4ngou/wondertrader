# QMT v6 原生实时行情插件

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：最终规格。状态：accepted。范围：显式 `ParserQMTHostV6` 的 `market.full_tick` 接入。原 [QNP](qmt-native-parser.md) 的配置、去重、SPI 与有界停止要求全部适用。

## NPV6-R1 显式选择与能力准入

新工厂使用原 `QmtPollingParser → QmtHostEndpoint → QmtHostReadClient`，固定选择 `FullTickV6`。旧 ParserQMTHost 的 Legacy 默认及 FullTickV3、账户 v3/v4 保持。实例只接受完整 `qmt.read-profile.v6`/control1，完整绑定、能力正文摘要、原请求 UUID 和终态字节仍经原 BoundCore 校验。版本选择无自动升级或降级。

v6 公开 profile 精确五字段；操作列表有序唯一且封闭在 full_tick/history_1m/history_prepare/account.trade_detail，包含 full_tick 和 history_prepare。逐项核验 policy、version、执行时限和全部 limits；历史准备周期有序唯一、额度及 max_queued≤max_tasks，执行时限≤total_timeout_ms，profile 总时限为各 descriptor 最大值。历史准备 limits 按 [HPR2](qmt-history-preparation.md#hpr2-固定输入与预算)严格区分版本：v1精确保留排序唯一symbols，v2精确省略symbols；[沪深北准备的显式v3](qmt-market-daily-preparation.md)沿用v2的字段和预算，市场范围由来源owner解释。三种版本均核完整profile/绑定摘要；版本变化需要新能力身份。未知版本及混合字段拒绝。full_tick 请求采用自身 descriptor 时限。组合中的其它能力仅作完整准入，本门面只发送 full_tick 和原ID结果认领。

## NPV6-R2 原生复用与责任

沿原 IParserApi 工厂/SPI、原 WTSTickData 和基础数据匹配（能力 PARSER/CTA，定位 `Includes/IParserApi.h`、`GuanhengData/QmtPollingParser.cpp`）。自有缺口限于 BoundCore 对已发布 v6 组合能力的认识及显式插件选择。协议 owner 为 `read_capabilities.py` 与 `history_preparation.py`；不修改 WT 框架，不引入报价聚合器、SourceSession 或通信账本。

报价标识、时间、价格和累计量额沿原 QmtHttpProfile 显式投影；同快照跳过、冲突/倒序隔离、未知结果保留及 worker 退出归原实现。停止确认包含 HTTP 回调排空、worker join；未完成保留对象/DLL/SPI。插件无账户、交易、下载、历史准备调用入口。

## NPV6-R3 完整模块验收

独立构建及安装 DLL，经正式已安装 Host、认证 WinSHM 和目标 Python3.6.8 完整内存正文/SDK替身到三证券 SPI，人工可核价格、标签、份额/元及正常 stop/delete；重复快照只投递一次。异常覆盖 v6 描述符畸形、来源/正文摘要变化、Unknown 原ID恢复、明确版本拒绝与默认旧插件及账户 v3/v4 兼容。固定源码/依赖/制品摘要、独立 full 审查、搬迁后安装及文档检查形成交付；真实 QMT 来源与正式 CTA 宿主接线由根集成另验。

实现：工厂（外部历史/待归仓路径：`../../src/ParserQMTHostV6/Factory.cpp`）。安装与证据见 [验收记录](../evidence/2026-10-29-native-quote-parser-v6.md)及[limits.v2后继](../evidence/2026-10-29-native-parser-limits-v2.md)。
