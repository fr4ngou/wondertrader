# 2026-10-25 未知取消 Common 原生客户端

类型：限定验证记录。关联[UC主规格](../specs/qmt-unknown-cancel.md)与[C++实施契约](../specs/qmt-unknown-cancel-cpp.md)。Common候选001限定通过，标准插件后继及旧客户端兼容重编译继续。

## 实现与根因边界

原生Common显式校验Host/Source v1/v2，分别冻结两个版本与原B/session。未知、硬故障和关闭各自保有，取消使用按操作准入，新增insert继续关闭。精确完整且原D内的cancel_pending响应才成为未受理事实；原申请与实际取消分别持有，不造别名。

新增只读lookup_cancel返回私有move-only引用；引用由本Core完整校验后一次发布，绑定原目标和实际取消receipt。首次resume_cancel及后继public resume均只GET实际原UUID；预检失败保Unknown和原receipt。历史B保留历史真值，当前proof仍由Host/Source在实际写入处核验。无金融账本或额外用户资格。

## 构建与动态结果

固定上游08b230dd05facf6d650d949bfe51054115a2ecb1编译七目标通过；只编译自有Common/插件，原Adapter不带工作树框架差异。运行使用NqpUnknownCancelCommonProbe.dll，SHA07fe1db7968de3ca766291119964a2e2bf91c5e759400a84d8c0986007680dec。故障注入宏仅进入独立测试Common库，普通Standard候选不定义该宏。

| 批次 | 实际结果 | 范围 |
|---|---|---|
| common-runtime-001 | 7方法，6通过、1 ERROR，0skip，4.782秒 | 57个故障fixture场景全部通过；真Host场景在非法SHM名字前置失败，原批次failed保留 |
| common-fixture-002 | 原失败方法1/1，0skip，0.900秒 | 修正合法qmt-broker-名字及本隔离配置显式启用写替身后，真实Host/SHM ORDER proof链通过 |
| standard-runtime-001 | 4/4，0skip，22.251秒 | 普通Common编译路径的Factory/Host/SHM公开链通过；Standard另有完成队列P2，保持未收口 |

最终Common方法覆盖6+1，58个定义场景由57协议fixture和一项真实Host组合构成。7方法首次failed不改写为整批通过。v1/v2矩阵、独立版本漂移、unknown下取消、硬错/close/gap、完整/截断/过D409、原申请A与实际B、坏关联、私有错owner/线程/原D/move、历史B及复制发布失败分别断言。

真实组合沿原AccountClient→Host BoundReadJournal/TradeOrderLinks→SHM Agent原线程读取ORDER；SDK替身insert进入后未知，query产生真实原结果/关联，随后定向cancel。实际替身insert/cancel各1、ORDER查询1，均在原源线程；原unknown及禁止insert保留。真实券商SDK调用为0，未连接运行中的QMT。测试配置只改这一方法，helper默认禁写和产品准入保持。

## 身份与独立审查

产品h c2fe9168b2c777855120a5c9a6a4a85fd9da085405560b7366dd330b9776f785；cpp 9f7b12601693b23aec519416fa9763d83dc81b1a83a7c5e25c7d61f8c680b729；native测试11775bc7b2e08f0f4f246346e415c4be895ac51395006e19bbdbbb52be9196d9；最终Python测试5d77c90510bb22bed752ebfd1ea6d4ca015ee309f7e2a7f58048e44c9e3a4f03。

独立full未发现Common产品P1/P2；原测试两项P2在fixture002 delta静态关闭，原33项输入与后继原文由根逐字节核同。原full和旧测试3c身份保持。审查为build/qmt-unknown-cancel-common-review-001；根封存为build/guanheng-workspace/qmt-unknown-cancel-common-final-001。构建、首次失败、单例复验及Standard四例的四个控制器均tree0、输出EOF、reader joined、资源关闭且未强制终止。

## 未完成与风险

Standard001正常四场景通过后，独审发现完成队列push可能分配失败并丢尚未移交的Started/U；该候选不授完整产品资格。自有Standard正在改为I/O前预留完成槽、无分配交付，并补真实状态机和分配异常验证。旧native_trade_client/native_order_query/native_event_context将用当前Common重新编译运行，旧二进制不冒充新源码兼容。

双Started、逐字段替换、精确预算边界、完整容量/父死亡、一般insert解除、生产query/live首次及重连、全部保留业务/历史/独立发行分别继续。Factory保持原入口，event_consumption_complete=0，无真实委托/撤单、终端重启、WT新增框架修改或旧QMT变更，整体目标active。

## 同日后继：最终Standard003与旧客户端回归

旧Common五个Python模块使用三个当前Common固定002重编探针制品执行37方法：compat-runtime-001为36通过、1失败，原批次保持failed；过期source_unknown关闭断言在唯一fixture更新为Source v2与真实双ACK门后，compat-fixture-002原失败方法1/1通过。最终按36+1覆盖37个唯一方法，产品Common保持原h/cpp身份，SDK均为替身。独立fixture delta无新增P1/P2，17份源码原件由根逐字节核同；本轮不把旧整批改记为通过。

Standard001/002发现的完成交付和未计费普通结果问题已在自有003修正，最终公开4/4、私有49场景2126断言通过，旧标准按30+1覆盖31方法。具体候选身份、失败历史、独立审查及未覆盖范围见[Standard后继证据](2026-10-25-qmt-unknown-cancel-standard.md)。完整生产交接、一般insert解除、故障矩阵及整体发行保持未完成。
