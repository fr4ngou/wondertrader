# QMT分钟来源日线

类型：最终规格。状态：accepted。适用：已成功导入的QMT schema2分钟来源仓到WT schema3来源日仓；前缀QMD。原日线合同沿[DSH](qmt-source-daily-history.md)。

## 目标与职责

QMD1：8个主指数和既有50个常用指数清单可沿原MarketClient.source_daily_history_query取得真实非空OHLC日线；准确记录常规2021-11-01及后发布指数的有效目标和实际缺口。QMT为主；本实现读取既有QMT原生分钟仓，不连接QMT/SHM、数据库、网络或交易，不修改WT框架。更长观察归档保持原件，本次未将缺失amount、未知原供应商身份或仅close表冒充QMT日线。

QMD2：复用WT-D04/D05/D08。固定上游08b230dd的WtDtHelper.resample_bars→WTSDataFactory.extractMin1Data负责六字段聚合；原store_bars、schema3 Importer和NativeHistory负责写入与回读。最薄适配仅负责分钟标签准入、明确调用参数、来源溯源与独立输出目录。240个连续交易分钟标签为09:31..11:30和13:01..15:00，09:30为可选附加来源记录；其它标签、重复、倒序及缺失任一必需标签均排除该日并登记原因。

## 时间、单位和原件

QMD3：使用原Helper的241槽聚合，坐标段09:29..11:30、13:00..15:00，align=false。09:29用于容纳可选09:30并避免原生零分钟减一的无符号溢出，真实开市时间保持09:30。输出必须恰好每准入日一根、原生标签15:00；逐日open=首条open、high=max、low=min、close=末条close、volume/amount=同序求和全部相等后，才写来源日期00:00+08:00的schema3 CSV。单位和原始数值沿原profile，无股/手倍率推测。源标签聚合支持当前只读，实际供应商官方日线等价、源分钟边界、交易日历覆盖和历史知晓时刻分别保持未核实。

QMD4：新目录必须不存在；父目录须已存在。CONFIGURATION.json冻结原字节配置；PROVENANCE.json绑定原仓、收据SHA、每证券DSB SHA/chunks/profile、有效目标、首尾、前后缀缺口与逐日排除标签。保留输入DSB和生成CSV；dataset_version=qmt-native-session-daily.v1。所有来源文件只读，写者仅拥有新根。失败保留本次输出，最终RESULT.json缺失表示模块未全部完成。原导入收据独立证明其对应成功store，不提升整次转换资格。

QMD5：配置schema=guanheng.qmt-minute-daily.v1；字段minute_store/receipt_sha256/native_reader/helper/selection均必填，native_reader和helper包含实际library/sha256，selection为唯一symbol/start/end列表（1..10000项，日期ISO格式）。入口为integrations.guanheng.qmt_minute_daily，参数--configuration和--output-root；执行线程独占Reader、Helper及回调，finally关闭，按原Reader每证券最多100万根/256MiB、原Importer总量预算准入。安装沿[操作手册](../runbooks/qmt-minute-source-daily.md)。

## 来源单位与消费

QMD6：来源unknown量单位允许完整OHLC及原量归档，响应中的单位标识持续保留。适配器继续拒绝跨请求窗口单位变化。comparison_model对显式unknown量单位输出activity=null，清空均量预热；单位变化后积累20个同单位来源交易日。同日价格、原量与activity独立于固定基价赋值；缺固定基价仅影响rebased列。已存在的无单位字段归档保持其原口径。价格、原量、已核物理单位和量指标各自登记资格。

## 验收

QMD7：原分钟→原Helper聚合→schema3/day DSB→原Reader→隔离WT history/source_market工厂→原MarketClient，8主指数和50清单逐项非空；日期和六字段与生成CSV全量相等，来源/周期/单位透传，同实例原分钟继续可读。覆盖不完整首日、内部缺分钟、可选09:30、重复/额外标签、输入SHA不符、未知量单位、单位变化、空查询和缺证券。WT正常关闭且其history子服务确认server/native关闭和OS exit0。001真实运行沿[首批证据](../evidence/2026-11-02-index-source-daily.md)；002根因修正与当前接入边界沿[后继证据](../evidence/2026-11-02-index-source-daily-002.md)。

QMD8：全量聚合日仓可作为独立只读来源；接续既有完整WT目录时保留已有证券日线owner。当前保留000300.SH/000016.SH原日仓，仅为其它48项补路由；按原factory验证旧年份的返回和metadata保持。禁止用短聚合仓的base优先级遮住已有长历史。观察replace_tables继续要求原表日期全部在新响应中；覆盖不足时保留原表并明确market_existing_coverage_missing。单来源批次有任一表失败时保留该批全部原表；本规格不放宽完整替换、不拼接未分段注明来源的量序列、不删除旧表。

QMD9：上证参考在唯一attach_sse_reference责任层一次写入原cffex和四basis，主指标保持。复用已审REFERENCE-ORDER-CODE-001函数；同次最终化后参考一致，再次处理相同输入的数值保持，覆盖外原归档参考保留。
