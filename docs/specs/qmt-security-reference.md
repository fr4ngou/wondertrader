# Source证券名册与资料只读契约

状态：2026-11-04供Root与统一日线数据模块冻结的最小业务合同。Root负责Agent/Host及真实QMT接线，数据模块负责消费、持久化、动态价格池和WT只读投影。现行v7/v8价格、HPR与未知原请求保持原身份。本合同不要求数据模块读取终端安装文件或修改QMT正文。

## 通信与能力

复用既有RetainedReadClient、绑定、原UUID/slot、结果保存/消费及截止协议。新增操作为`market.security_universe`、`market.security_details`，策略ID均为`qmt.security-reference-read.v1`，策略版本`1.0`。Root分配独立的只读能力profile/连接；现行v7/v8的版本与协议继续兼容。消费者通过metadata.operation_profiles发现两项能力，不硬编码新profile版本号。能力未交付时返回消费状态`waiting_reference_capability`，已有股票价格与已发布结果继续可读。

以下JSON是原业务arguments和成功reply.data，不另造运输封装。两项操作均不下载、不订阅、不访问账户、不产生金融命令。参数限于公开证券范围。Source返回真正空值及字段不可用原因，不把None/NaN转换为0；供应商原有的真实0继续保留。

## 1. market.security_universe

首个请求：

```json
{"markets":["SH","SZ","BJ"],"security_types":["stock","etf","index"],"limit":256,"cursor":null}
```

后续请求保持markets、security_types、limit，cursor使用原返回值。markets和security_types是非空、去重、按SH/SZ/BJ及stock/etf/index固定顺序排列的子集；limit为1至256。cursor为null或最多512字节的Source不透明字符串。游标绑定原scope、Source绑定和同一次catalog_id，拒绝改scope或跳到另一份名单。

成功data的固定字段：

| 字段 | 中文含义 |
|---|---|
| schema | 固定`qmt.security-universe.v1`。 |
| catalog_id | 同次完整名册快照的64位小写SHA256，所有分页保持一致。 |
| captured_at | Source实际取得本份名单的UTC ISO8601时刻，所有分页保持一致；不宣称交易所生效时刻。 |
| source_as_of | SDK明确提供的UTC ISO8601资料时点；没有独立时点时为null，不以captured_at冒充历史可知。 |
| markets / security_types | 原请求范围，与原scope完全相同。 |
| state | `complete`或`partial`，描述Source取得名单的完整性；与分页传输完毕分别判断。 |
| total_count | 全部请求分组均完整时的去重证券总数；有未知分组时为null。 |
| groups | 每个请求market×security_type的分组事实，最多9项，分页重复同一完整分组说明。 |
| items | 本页实际证券，最多limit项；跨页不重复。 |
| next_cursor | 下一页游标；本快照没有剩余项目时为null。 |

groups每项固定字段：

| 字段 | 中文含义 |
|---|---|
| market / security_type | SH/SZ/BJ及stock/etf/index，唯一标识分组。 |
| state | `complete`、`partial`、`unavailable`、`unsupported`。 |
| expected_count | 只有完整名单能够确定该组应覆盖数时为非负整数，其余为null。 |
| observed_count | 此次已实际取得并去重的该组证券数，指整份快照，非本页条数。 |
| source_groups | 实际使用的QMT板块/分类名称数组，不能用代码前缀猜测类型。 |
| reason_code | 完整时null；其余使用固定原因码，例如`source_group_unavailable`、`source_call_failed`、`classification_conflict`。不返回异常原文。 |

只有供应商明确成功返回空名单，才可写`complete/expected_count=0/observed_count=0`。板块不存在、取数失败、未暴露能力均保持unknown/unsupported及expected_count=null。Source内不支持的组不能充当整个市场不存在该类证券的证据。

items每项固定为：

```json
{"symbol":"510300.SH","market":"SH","security_type":"etf","source_groups":["沪深ETF"]}
```

symbol为六位代码加`.SH/.SZ/.BJ`，market必须与已验证的原符号后缀一致；security_type为stock/etf/index/unknown。分类冲突时保留证券、原source_groups，类型为unknown并把受影响分组标为partial；不得静默丢弃。名称与上市资料由第二项操作获取。跨组同证券仅在items出现一次；有分类冲突时total_count保持null。

Source需要为分页保留同一份不可变名单，不能每页重新扫描后拼成混合版本。建议至少900秒可消费期、最多2份快照、每份最多20000证券、总缓存原件最多8MiB；Root若采用其他有限预算，在能力limits声明并同步本合同。到期或被回收返回`security_catalog_expired`，不得用同一游标隐式返回新名单。消费者保留旧槽，将本次捕获标为未完成后才能开始明确的新捕获。

## 2. market.security_details

请求：

```json
{"catalog_id":"<64位SHA256或null>","symbols":["510300.SH","000001.SH","920000.BJ"]}
```

symbols为1至64个互不重复的上述市场符号。catalog_id非空时证券必须来自该名单；该身份绑定选择范围，不宣称逐只SDK调用在同一瞬间完成。null用于已持有明确证券身份的资料缺项恢复。成功data固定为schema=`qmt.security-details.v1`、catalog_id（回显原请求）、captured_at、source_as_of（缺失时null）、items。items与请求证券集合完全相同，每只恰好一项，包括未返回资料的证券。

每项字段：

| 字段 | 中文含义 |
|---|---|
| symbol / market | 原符号和SH/SZ/BJ，不由名称猜测。 |
| status | `observed`或`unavailable`；某字段缺失不必使整项unavailable。 |
| name | 原名称字符串或null；空串/无效值在raw_fields保留，在此为null。 |
| listed_on / expires_on | 明确且有效的YYYY-MM-DD或null；0/99999999等哨兵值不转换为日期。 |
| trading_status | `active`、`halted`或`unknown`；缺少明确状态时保持unknown。 |
| observed_at | 本证券详情实际取得的UTC时刻；SDK无资料时也记录本次观察时刻。 |
| field_reasons | 缺失/未准入字段到固定原因码的字典；已准入字段不要求条目。 |
| raw_fields | 供应商原字段值的有限白名单；用于核对映射，不返回账户等无关资料。 |

raw_fields白名单：`ExchangeID`、`InstrumentID`、`InstrumentName`、`OpenDate`、`ExpireDate`、`IsTrading`、`FloatVolumn`、`TotalVolumn`。存在的原字段保留原名和原值；未提供的字段可缺省；非有限数转为null并在field_reasons列`source_nonfinite`。其他原因码至少包括`source_missing`、`source_unavailable`、`source_invalid_value`、`source_market_conflict`。每项编码最多4096字节，整次data最多300KiB。不能从FloatVolumn推造历史股本、从未成交推造停牌、或从代码推造证券类型。

详情不可用项仍回传symbol/market、status=unavailable、其他资料null或unknown及原因；价格池继续保留此证券。分类沿名册source_groups；详情不另造代码分类。数量单位若没有独立说明仍为unknown，raw_fields中的原数值不自动换算。

## 截止、错误及消费准入

单次请求沿原有限30秒ticket及调用方总截止。Source调度预算可更小；消费者可选择每批少于64以避免长回调。所有结果继续保存原binding、request_id、原bytes/SHA和消费状态，换代及未知请求不重派。

参数错误、游标范围/身份错误、`security_catalog_expired`沿原失败reply.error_code表达；部分组或部分证券失败使用上述成功data内的明确状态，不抹掉已取得项目。原异常正文及凭据不进入业务结果。

数据owner仅在分页结束、全页身份/时刻/scope一致、无重复证券、条数与已声明完整计数吻合后取得相应完整资格。partial目录可以保存并补充已知资料，仍保持逐组未知计数，不能宣称全类别100%。详情缺失逐项记录，不能删减应采证券。

价格日线继续由原v8/HPR获取。旧价格契约无法提供完整OHLC或量额时，保存原响应和缺失原因，维持旧成功档；不补0、不以close推造OHLC，也不因资料成功赋予价格完整资格。原始真实0与缺字段分别处理。

## 分工与验收

本模块的职责、源码及缓存边界见[模块说明](../modules/qmt-security-reference.md)，固定安装和完整正文接续见[运行手册](../runbooks/qmt-security-reference.md)。

Root交付新能力metadata、非敏连接声明、凭据环境引用及Host/Agent实现；保持现行价格/HPR通道及QMT运行边界。数据模块先完成消费接缝，以注入的原retained客户端调用两操作、保存原槽和派生资料；缺少能力明确等待，现有日线继续服务。

双方以分页身份一致、过期不偷换、逐组部分失败、详情缺项保留证券、分类冲突、原0/None/非有限值及原UUID恢复为准入样例。完整业务验收另核真实QMT全类别名册、价格应覆盖与已覆盖、真实尾日/缺口，以及日后同一数据owner自动推进。
