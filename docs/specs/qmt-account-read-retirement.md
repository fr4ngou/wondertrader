# 账户只读结果的消费确认与有界回收

类型：最终规格。前缀：AAR。状态：accepted / implementing。沿[ADR0007](../architecture/adr/0007-account-observation-read-state.md)、[RR](qmt-read-retirement.md)和原账户/交易契约。范围为显式v3账户、v4混合交易通道中的account.trade_detail，只读结果生命周期。

## AAR1 明确选择与兼容

Host配置/Agent完整profile显式声明原read_retention={schema:qmt.read-retention.v1,max_lifetime_ms:N}，N保持100..300000整数。v3沿原control1，v4沿原control2与trade_profile/私有账户绑定。省略时原配置/profile/UUID4/HTTP/Journal路径及默认行为保持；金融写授权和order_ready不由此字段改变。HPR/v7当前已验能力和冻结制品保持，后继共用同一规则。

## AAR2 原请求、结果与进程内交付

Native仍由原QmtBoundReadCore/QmtHostAccountClient负责四查询；原move-only token一次POST、原ID跟随/控制/总D和来源/账户/金融DTO验证保持。显式模式复用RR的ticket、内容UUIDv5、原八字段请求、retained外层、GET/lookup及consumed。ticket使用同机GetTickCount64和当前Host epoch，期限不重授；原resume使用保留的原ticket/完整binding/请求/结果，不改ID或重POST。网络未知/404/410/未知终态继续原责任。

账户消费边界为：原完整结果、原raw bytes、原data片段及来源/DTO/截止校验均已完成，并由本进程返回值取得有界内存所有权；随后才在同一原D内发送原正文SHA/结果SHA的consumed确认。该确认表达本轮观察已可交付，后续mapper/Adapter失败按原整轮隔离处理；它不代表账户事实永久存储。确认未取得时保持原身份和失败/待确认，不报告成功消费。真实持仓/资金/订单值继续只来自本轮券商查询。

原scan_id与四请求仅在活进程，进程死亡后按ADR0007确认旧树回收，再由明确的新刷新开始新scan。没有强制客户端slot/恢复目录、账户快照数据库或新账户账本。自有Native receipt可增加显式内存ticket元数据；全部受影响自有Native消费者同批重编，原WT C ABI/框架保持。

## AAR3 Host回收与金融隔离

Host复用原独占SQLite owner、原read_operations及RR事务。仅消费者已确认、确定terminal且原票据结束或epoch结束的只读记录可回收；queued/executing/operation_interrupted及其他未知保留原ID/原结果和逻辑额度。确定分类继续由RR result_confirmed唯一公共规则定义。ACK丢失/重读不得生成替代请求。

原金融order link仍引用的ORDER结果属于金融proof闭包；即使消费者已确认，也保留该原读行及票据，直到原金融算法自然更新引用。状态以held_financial_proof单列真实占用；金融proof占满时保持原责任并报告等待，不能扩大额度或删除引用来推进。历史proof的能力身份仅沿下述精确旧profile关系准入，当前查询仍核当前完整来源。

v4复用同一金融Journal文件，新增的读取责任元数据与read_operations同事务关联。trade_commands、交易identity、事件、订单关联、认证续接和未知金融责任不进入回收SQL、不变更其重发规则或原预算。启用/重开不得清空金融数据或另换空金融根。已有不含票据的读责任保留并计入实际占用，不能据缺票据猜测其未执行或批量删除；如需新增只读元数据，明确校验既有owner/金融身份后以附加事务初始化。显式v4可保留当前完整profile仅去read_retention所对应的既有事件identity及历史认证原件；当前来源仍核新完整profile，其他profile/预算变化拒绝。半套schema、身份/额度改变及不支持的混装明确失败，原金融材料保持。

## AAR4 有界与状态

原max_records、max_journal_bytes、交易预算和RPC/任务/关闭D保持；不通过扩大配额解决累计占用。回收维护沿原请求/确认/状态入口执行，不新增后台线程/运输。状态将有票据责任、未知和不含新票据的既有责任如实计数，retained不得隐藏仍占用read_operations的行。QMT仍由同正文/原SDK线程调用，无文件/网络或新增SDK线程。

## AAR5 验收

先跑普通安装与原Native真实主链：正式v3/v4 Host+实际3.6.8/WinSHM账户SDK替身→原QmtHostAccountClient及Scan/标准Factory，固定原容量跨过连续扫描上限，记录实际四查询数量和占用高水位；成功确认后Host读责任保持有界。v4同时保留原金融命令/事件原件，读取回收前后逐行/摘要一致，金融SDK不因回收新增。

主链后只做必要默认、unknown/同ID无重发、确认前/后失败、截止/停止及Host重开/既有金融Journal保留回归。新Native组件、账户工具、Host/Agent普通wheel和完整依赖同批形成可由SRI消费的固定交接。真实QMT、生产、跨日/Source冷重启及整个系统资格分别验收。

## AAR6 Host HTTP拥有的读取消费模式

为沿用现有Source正文与SDK能力，v4交易Host可显式配置http_read_retention，形状复用read_retention的schema/max_lifetime_ms，二者互斥。此能力仅出现在已认证read-binding的limits.http_read_retention，不进入Agent配置、完整Source profile、binding capability SHA或SDK请求正文。默认省略保持原模式。

Native同批账户客户端识别该HTTP能力，复用原v1票据、内容UUIDv5、retained提交、lookup及consumed。receipt仍保存原Source profile/SHA；v4票据独立核原Host epoch、完整原请求和内容ID。公开resume只有原票据lookup能力，不能制造新POST令牌。首票据期限取配置上限与调用剩余D的较小值；Host在首次事务内按票据原D收紧排队期限。

新模式复用RetainedTradingJournal原回收条件、金融proof保护和同事务消费确认，附属身份同时固定HTTP能力及Source profile。旧无票据读行、原ID、正文、结果、金融命令/事件/关联均保留。仅该显式模式将不可变terminal且已有结果的读行按实际原正文/结果长度加原元数据上限计费；在途、无结果等仍按最大预留计费，不改既有reserved_bytes或金融额度。max_records与max_journal_bytes保持原配置，新成功消费且原票据结束的读取按原规则回收，使连续读取保持有界。

验收先以原满额库的隔离副本确认：旧行/ID/结果/金融原件逐字保持、默认原模式拒绝超额、显式HTTP模式可准入且不改Source字节；实际Native/Host/WinSHM与SDK替身连续查询跨过小容量上限，确认占用有界。再核原票据未知、金融proof、关闭及同账完整主链；原Source和实地权限按真实资格分别登记。
