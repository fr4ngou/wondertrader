# Tushare 辅助行情源能力核查

文档类型：第一方资料研究结果。  
权威范围：Tushare Pro 官方公开接口、权限说明与官方 Python SDK；供独立可插拔辅助数据源设计使用。本文不改变现行接入规格。  
状态：研究完成；权限、数据质量与端点运行资格待独立验收。  
有效性：2026-10-21 查证。在线文档和服务端权限会变化；SDK 固定到 `093856995af0811d3ebbe8c179b8febf4ae706f0`，通过官方仓库 `git ls-remote HEAD` 核实。

后续实测更新（同日）：文档研究后的独立授权步骤已验证 HTTPS API，并对运行环境凭证与用户提供的凭证作私下相等校验。首次固定样本 `daily` 返回 1 条，`stk_mins` 返回 2 条，`etf_mins` 拒绝；第二次股票分钟返回限频/额度拒绝、ETF 分钟返回权限拒绝（均为来源码 40203）。因此当前 token 的股票分钟具有样本读取证据，吞吐与完整历史能力仍受限；ETF 分钟当前无读取资格。下文“本轮未探测”专指先前的文档研究阶段，生产资格仍待完整验收。实测输出仅保存字段名、条数及脱敏错误，不保存凭证。股票分钟样本不推定实时或 ETF 分钟开放。

## 结论与证据边界

基础权限适合把股票未复权日线列为辅助来源候选。历史 1 分钟、实时分钟、ETF 日线和基金净值分别受权限约束，token 的存在不能证明这些能力可用。官方权限表把 120 积分档列为非复权日线，限 50 次/分钟、8000 次/日；各类分钟权限单独开通，与积分独立。[官方权限表](https://tushare.pro/document/2?doc_id=290)

“用户只有最基础权限”是本次任务输入。本轮没有查询用户积分、权限或 token，没有调用带凭证接口，没有进行行情样本实测。因此下面的“官方事实”代表公开文档能力，用户实例的能力全部保持未核实。本文的“建议”属于设计推导。

## 鉴权、端点与错误协议

官方事实：Pro 使用 POST JSON，请求体包含 `api_name`、`token`、`params`、`fields`。token 用于识别用户；SDK 支持构造 Pro 对象时直接传入，文档也提供会保存凭证的 `set_token` 方式。直接调用协议返回 `code/msg/data`，成功示例 `code=0`，`data.fields` 对应 `data.items`；文档明确 `2002` 表示权限问题。[官方调用说明](https://tushare.pro/document/2?doc_id=40)

官方公开调用说明写出的地址是 `http://api.tushare.pro`。固定 SDK 的 `DataApi` 同样把该 HTTP 地址写在类字段中，构造参数只有 token 与 timeout；`query` 直接 POST 到该地址。[调用说明](https://tushare.pro/document/2?doc_id=40)、[固定 SDK client.py 第17—40行](https://github.com/waditu/tushare/blob/093856995af0811d3ebbe8c179b8febf4ae706f0/tushare/pro/client.py#L17-L40)

**HTTPS 状态：本轮所查官方资料未确认生产 HTTPS API 地址、TLS 证书和凭证请求支持情况。** 官网文档采用 HTTPS，并不能证明 API 同样支持 HTTPS。本轮没有试发 token，也没有测试猜测的 HTTPS API 地址。建议上线资格必须包含官方确认的 HTTPS API 与证书校验；在此之前保留为待资格化来源，配置禁止自动降级 HTTP。该措施是本项目建议，不代表官方宣称 HTTPS 不可用。

官方源码事实：SDK 对非零业务码抛出通用 `Exception(result['msg'])`，调用者通过这个异常拿不到原始 `code`；成功则创建 pandas DataFrame。该方法没有显式 HTTP 状态检查、重试或限速逻辑。[固定 SDK client.py 第32—51行](https://github.com/waditu/tushare/blob/093856995af0811d3ebbe8c179b8febf4ae706f0/tushare/pro/client.py#L32-L51)

建议适配器保留 HTTP 状态、原始业务码和脱敏消息，区分 `permission_denied`、`rate_limited`、`transport_error`、`schema_error` 与成功空结果。官方资料仅在本轮核实了权限码 `2002`；限频错误的稳定数值码、HTTP 状态、重试头和等待时间均缺少本轮证据，不编造码表。权限失败不作为“无行情”落库，也不推进补齐完成水位；限频采用有界退避和预算，避免无限重试。日志、异常和测试夹具都不包含请求体中的 token。

## 各数据能力与基础权限判断

下表每行均为 2026-10-21 查到的官方事实；“基础档”指公开的 120 积分档，不代表已经核实用户实例。

| 能力 | 官方接口、范围与额度 | 基础档判断及来源 |
|---|---|---|
| A 股历史日线 | `daily`；交易日15—16点入库，未复权，停牌期不提供行；最多6000行/次 | 权限表列为可用候选；账户可用性未测。[daily](https://tushare.pro/document/2?doc_id=27)、[权限表](https://tushare.pro/document/2?doc_id=290) |
| A 股历史1分钟 | `stk_mins`；1/5/15/30/60min，超过10年历史；8000行/次、500次/分钟，30万次/滚动24小时；按代码和时间分窗 | 需单独“A股历史分钟”权限。[专页](https://tushare.pro/document/2?doc_id=370) |
| A 股实时1分钟 | `rt_min`；频率参数大写 `1MIN` 等，支持多代码，1000行/次 | 需单独“A股分钟RT”；不能由历史分钟权限推定。[专页](https://tushare.pro/document/2?doc_id=374) |
| A 股当日分钟回补 | `rt_min_daily`；单只股票当日开盘以来分钟 | 同样需“A股分钟RT”；当日累计接口不能替代跨日历史接口。[专页](https://tushare.pro/document/2?doc_id=457) |
| ETF 盘后日线 | `fund_daily`；当前专页为ETF收盘后行情，超过10年，5000行/次，按代码/日期循环 | 当前专页至少5000积分；旧总览冲突见下节。[专页](https://tushare.pro/document/2?doc_id=127) |
| ETF 历史1分钟 | `etf_mins`；1/5/15/30/60min，超过10年，8000行/次 | 需单独“ETF历史分钟”，与股票分钟分别确认。[专页](https://tushare.pro/document/2?doc_id=387) |
| ETF 实时1分钟 | `rt_etf_min`；1/5/15/30/60MIN，1000行/次，支持多代码 | 正式权限指向独立权限说明；基础档不推定可用。[专页](https://tushare.pro/document/2?doc_id=416) |
| ETF 当日分钟回补 | `rt_etf_min_daily`；单代码，当日开盘以来分钟，1000行/次 | 专页要求正式权限；独立核实。[专页](https://tushare.pro/document/2?doc_id=470) |
| 股票/ETF 实时行情快照 | `rt_k` / `rt_etf_k` 是当日实时日K，含最新价、日内OHLC和量额；股票单次最多6000行 | 分别需“A股日线RT” / “ETF日线RT”；不是分钟订阅权限。[股票专页](https://tushare.pro/document/2?doc_id=372)、[ETF专页](https://tushare.pro/document/2?doc_id=400) |
| 公募基金净值 | `fund_nav`；场内/场外，单位净值、累计净值、复权单位净值，区分公告日与净值日 | 至少2000积分；基金净值是独立数据类型，缺少OHLC和分钟成交语义。[专页](https://tushare.pro/document/2?doc_id=119) |
| 股票复权因子 | `adj_factor`；盘前9:15—9:20完成当日入库 | 2000积分起，不能假定基础档有复权链。[专页](https://tushare.pro/document/2?doc_id=28) |
| 基金复权因子 | `fund_adj`；2000行/次，支持日期分窗和offset/limit | 专页2000积分；旧总览5000起，保留待核实。[专页](https://tushare.pro/document/2?doc_id=199)、[旧总览](https://tushare.pro/document/1?doc_id=108) |

官方权限表给出的实时分钟总额度为500次/分钟、每次最多300家公司；具体 `rt_min` 专页另有1000行/次。建议同时满足代码数和行数限制，避免把两个维度当作同一个限制。ETF专页没有给出同样清晰的每分钟数值，不能直接复制股票限额。股票/ETF实时日线权限表为50次/分钟。[权限表](https://tushare.pro/document/2?doc_id=290)、[rt_min](https://tushare.pro/document/2?doc_id=374)、[ETF实时分钟](https://tushare.pro/document/2?doc_id=416)

### 官方资料的冲突与处理

- `daily` 专页写“基础积分每分钟500次”，权限表把120积分档列为50次/分钟、8000次/日。建议以50次/分钟和8000次/日作为基础档初始预算，实际权限受服务端裁决；500次不作为用户承诺。[daily](https://tushare.pro/document/2?doc_id=27)、[权限表](https://tushare.pro/document/2?doc_id=290)
- `fund_daily` 当前专页至少5000积分，旧总览2000；`fund_adj` 专页2000，旧总览5000起。建议能力 profile 记录冲突及查证日期，ETF日线候选按5000门槛规划，两者实际调用资格均待服务端验收。[fund_daily](https://tushare.pro/document/2?doc_id=127)、[fund_adj](https://tushare.pro/document/2?doc_id=199)、[旧积分总览](https://tushare.pro/document/1?doc_id=108)
- 旧总览仍列部分120积分非行情接口，新的权限表写120档“其他接口无法调取”。本任务只把股票非复权日线列入基础候选，不承诺证券列表、交易日历、ETF、财务或宏观接口。[旧总览](https://tushare.pro/document/1?doc_id=108)、[权限表](https://tushare.pro/document/2?doc_id=290)

## 单位、复权、时间与完整性

| 接口族 | 官方字段含义 | 建议归一化与保留项 |
|---|---|---|
| `daily` | `trade_date` 为YYYYMMDD；`vol` 手，`amount` 千元；`pre_close` 是除权昨收，涨跌幅也按除权昨收计算 | 保留原始单位；转换到股/元时显式×100/×1000并校验目标证券单位；原始OHLC标记未复权。[专页](https://tushare.pro/document/2?doc_id=27) |
| `fund_daily` | `trade_date`；价格元，量手，额千元 | 日线单位转换单独定义；复权状态专页未明确保证，保留未知直到资格验收。[专页](https://tushare.pro/document/2?doc_id=127) |
| `stk_mins` / `etf_mins` | `trade_time` 为无时区字符串；请求起止示例为YYYY-MM-DD HH:MM:SS；量股、额元 | 保留原时间字符串和来源；复权/分钟边界尚待核实。[股票](https://tushare.pro/document/2?doc_id=370)、[ETF](https://tushare.pro/document/2?doc_id=387) |
| 实时分钟及当日分钟 | `time` 交易时间；量股、额元；历史频率小写，实时频率大写 | 字段名和频率转换由该来源负责，统一层不直接透传。部分当日示例第一行09:30，不能据此推定所有行都是同一种起/止标签。[股票实时](https://tushare.pro/document/2?doc_id=374)、[当日](https://tushare.pro/document/2?doc_id=457)、[ETF实时](https://tushare.pro/document/2?doc_id=416)、[ETF当日](https://tushare.pro/document/2?doc_id=470) |
| `rt_k` / `rt_etf_k` | 最新价作为close，日内OHLC，量股、额元；可选交易时间 | 按当日快照处理；轮询快照无法保证重建真实1分钟OHLC。[股票](https://tushare.pro/document/2?doc_id=372)、[ETF](https://tushare.pro/document/2?doc_id=400) |
| `fund_nav` | `ann_date` 公告日，`nav_date` 净值日；`unit_nav` / `accum_nav` / `adj_nav` 含义不同 | 单独建净值类型；回测可见性由公告时间证据控制，不能用净值日冒充可见时间。[专页](https://tushare.pro/document/2?doc_id=119) |

官方 `pro_bar` 是SDK组合逻辑，官方说明不能直接作为HTTP通用接口调用。`adj=None/qfq/hfq` 仅针对股票，当前说明只支持日线复权，并依据 `end_date` 动态复权。因此前复权历史会随锚点改变；不能把不同终止日的结果拼入同一个无版本序列，也不能由 `pro_bar` 描述推定分钟复权已支持。基金有单独 `fund_adj`。[pro_bar](https://tushare.pro/document/2?doc_id=109)、[fund_adj](https://tushare.pro/document/2?doc_id=199)

实测缺失与未知：本轮官方专页没有充分定义分钟起/止时间标签、起止参数的闭区间规则、时区、排序稳定性、集合竞价并入方式、实时最后一根是否已收盘、迟到修订、停牌/无成交分钟填充、服务时延SLA或内部缺分钟完整性证明。Asia/Shanghai 可作为国内市场适配假设，必须在实际接入验收中确认。`trade_time` 字符串和8000行页上限都不能证明请求窗口完整；补齐模块必须独立按交易日历、证券有效期、停牌和会话规则验收缺口。[历史股票专页](https://tushare.pro/document/2?doc_id=370)、[历史ETF专页](https://tushare.pro/document/2?doc_id=387)、[实时股票专页](https://tushare.pro/document/2?doc_id=374)

## 建议的独立能力 profile

以下均为提案，不是本轮实现或已验能力：

1. 增加独立 `source=tushare` 辅助只读数据适配器，保持QMT主来源和现有事实所有权；策略通过统一行情接口选择来源能力。Tushare不进入委托、撤单或账户链。
2. 每个 `(asset_class, api_name, timeframe, adjustment)` 单独记录 `documented / unverified / qualified / denied`，附端点资格、查证时间、实际权限结果、限流预算、最大行数、代码数、历史边界、单位、时间标签与最终性语义。凭证已配置与权限已证明分开表示。初始股票日线仅为 documented 候选；所有分钟和ETF/基金能力保持 unverified，不自动发起开通或探测。
3. 归档键和来源元数据包含source/API、证券身份、周期、复权模式/锚点、量额单位、时间解释及版本。Tushare数据经现有单writer与完整性发布链进入原生存储；源端权限失败、空页、上限截断与未知完整性都不标记 source_complete。跨源补齐需显式兼容检查与来源记录，避免静默覆盖QMT数据。
4. 历史按有界时间窗请求，必要时缩窗；不能仅凭“返回不足8000行”断言内部分钟完整。实时REST轮询若将来资格化，由适配器转为受控分钟事件，并分别处理形成中、收盘、修订与去重；本轮没有证实股票/ETF服务端推送订阅能力。
5. 凭证由受控运行环境注入，仓库只记录秘密引用。端点必须先通过HTTPS资格检查，拒绝携带凭证跨主机重定向和HTTP降级；错误信息统一脱敏。本轮无token收集、输出、持久化或权限探查。

后续最小资格验收应覆盖：官方HTTPS确认、授权范围内指定能力成功/拒绝、频控分类、历史/当日分钟交界、时间标签与闭区间、日线与分钟量额核对、复权锚点、修订/重复/截断、空结果与权限失败区分。需要凭证的验收由获授权的独立步骤执行；本文不把公开文档当作该验收结果。
