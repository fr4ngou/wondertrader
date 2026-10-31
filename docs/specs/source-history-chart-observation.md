# 来源历史范围与分段来源展示

类型：功能规格。状态：accepted / in-progress。前缀：HCO。依据COP-A1/A2及A的RS13正式SDK0.15合同，沿[行情消费者](native-market-consumers.md)和[来源日线](source-daily-chart.md)保留既有语义。

## HCO-R1 事实与调用链

源服务/SDK拥有Archive、Observed、Partial、source_window、source_rows、selected_rows/requested_limit、preparation_state及原请求身份、跨谱系provenance。App通过SDK0.15原source_history_query读取并验证其闭合合同，投影完整来源分段原metadata及各段对应的实际返回时间；两个行情入口读取同一图表DTO。App不重建历史、不触发额外准备/下载/查询、不推导完整市场覆盖或捏造捕获会话。

根因在native_chart投影丢失原data.observation/provenance。修正该唯一层及共有前端来源说明，原normal/empty/error/refresh/停止语义保持。默认disabled及原来源连接、预算与进程owner保持。

## HCO-R2 公开图表1.7

有SDK来源观测或分段来源的1m原值响应使用schema1.7，保留既有candles和source_label时间/单位。新增source_observation为有限typed值：source_schema、state、from_at/to_at组成的实际source_window或None、source_rows/requested_limit/selected_rows、preparation_state与原preparation_request_id或None。原reason不透传，面向用户原因沿有限枚举生成。选中行数等于返回candles数。

source_provenance保存原offset/count及完整原metadata，metadata的source保留provider/instance_id/session_id/generation，不由集合伪造；每段first_at/last_at由其实际返回行取得。段数至多2000、offset/count连续且恰好覆盖全部candles，首尾时间与对应行一致。集合顶层native_source保持SDK SourceSelection内容身份，不挂虚构会话。没有分段时保留空列表，不制造新来源事实。

1.7仅限1m原值source_label，至少携带观测或分段；2000根/有界枚举/标识/时间、数量与对应行一致性均校验。原canonical1.4、无新增来源字段的1.5及来源日线1.6保持原JSON字段与语义；旧版本不输出新增空字段。无新增信息的旧来源不冒名Archive/Observed/Partial。失败响应保留该查询条件的上次成功图表和原来源状态，并标明上次数据时间及本次刷新失败；首次读取失败按无可读结果展示。

## HCO-R3 用户说明

2026-10-29用户明确：观衡面向日常使用者，内部来源资料归诊断材料。MinuteWorkspace与保留MarketPage共用简短行情提示。页面仅显示读图所需的交易日或北京时间、复权口径与成交量单位；Partial说明部分历史缺失，补齐异常用可理解的原因和重读/重试动作表达。Observed、Archive与正常补齐无需额外状态面板，返回条数达到请求量也不推导完整覆盖。

数据集版本、内容哈希、来源实例、会话、代际和逐段单位列表保留在原API响应和内部验收资料。产品页面移除相应详情入口；代码直接停止渲染这些字段。已有长时间缺口继续由图表空白和简短说明表达。同一标的、周期与截止条件加载或失败时，保留上次成功图表和说明，显示原数据时间及刷新状态；切换查询条件使用该条件自己的结果。成功的空响应按实际为空展示，恢复和手动重读成功后更新当前响应。时间保持北京时间，浏览器其他时区不改变交易日。

## HCO-R4 验证与交付

先跑SDK0.15已安装来源组件→独立安装Appa18公开HTTP→生产SPA独立行情入口的完整主链，明确有限离线数据/源SDK替身及真实来源资格边界。保留的MarketPage组件与当前MinuteWorkspace沿同一DTO和共有说明组件回归，分别覆盖同查询条件读取中和失败保留上次结果、查询切换、真实空结果及恢复；生产入口由main.tsx实际挂载决定。至少包含跨根分段Partial、Archive、Observed、Unknown准备、旧模式及日线、空/失败/恢复和停止。原来源实跑与明确DTO边界替身分别登记，Observed及Partial含义沿原状态，返回条数达到请求量也不改报状态。实际桌面和390px窄屏核中文提示、内部身份不渲染、重读、北京时间、无横向溢出及console状态，不能以loading态代替完成态。

然后覆盖坏计数/不连续段/错集合身份/未来或错误窗口、无新增字段旧协议兼容和异常去敏，核调用次数和所有进程/线程/Job/端口关闭。独立App/SDK及新SPA成员SHA/RECORD、固定源/规格/配置/原件和适用独立双轴审查完整绑定；真实QMT/137/140不重复操作，不真实下撤单或发布。完整M1/所有策略及统一升级仍按各自实际资格继续。

