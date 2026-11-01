# 行情日线来源恢复与自然周月公开读取

类型：修复、固定安装与真实只读验收。日期：2026-11-02。状态：通过。

## 根因与实现

300308.SZ和588170.SH的公开日线请求在18122/18123均返回来源不可用。直接调用18132来源SDK时，分钟查询成功，日线查询返回source not registered。活动`source-collected`配置只登记分钟仓；同时适配器只把分钟查询路由到supplements，日线查询固定落到base，新增日线仓也无法进入公开调用链。

修复在来源所有者层完成：本地DAT导入器支持86400日线并生成schema3收据；`CollectedSourceMarket`按证券和1d周期选择唯一supplement，多个日线来源保持不可用；App公开合同增加1w/1mo、daily_limit和years，日/周/月共用真实日线尾窗。自然周按ISO周、自然月按公历年月聚合，O/H/L/C/V依次使用首根/最大/最小/末根/求和，标签使用周期内最后实际交易日，source_bar_count记录实际日线数。

WT框架修改为0。QMT/SHM请求、下单、撤单均为0。

## 数据与固定身份

已登记证券7,127个；有效日线5,274个，共12,885,459根；源文件缺失1,836个；17个源文件因时间、价格或负数量校验失败并保持隔离。全量导入收据SHA-256为`9e2171c224abbf6e2e6336cc66825b6169de954a782f44a2eeb6b36a957ee2f7`，覆盖收据SHA-256为`ffb32606ba569e6e39e4c035baeaf94d46e2926977b6ac22d10a47d81745d8fa`。

固定GuanhengMarket组件复用039原生库，191个文件，原生未重编；ZIP SHA-256为`c1744c26ede827ad48b9eb897e38600bb92df1f7574411e870613828903ab5f2`，INPUT SHA-256为`53eb525d91d4157ada79f9218a1e9a269a1efee5553897e8b17d49505e5e7956`。安装内`collected_history.py`与仓库源码SHA-256同为`fff7f3f5898309981cb1570871d1600960368983d4e8031bebcbed33bb9dd359`。固定源码表位于`build/daily-history-acceptance-002/SOURCE-MANIFEST.json`。

独立source配置SHA-256为`0e9b7f383ed294d10da72b566de0a8955b4b1171040237444e0e2f7d662df83f`；服务配置SHA-256为`33cf8e5eefcbd16a2e53b7426ef79c8ea86d7b0e02b16ad857734ca30b25fc8d`。配置绑定全量日线收据和固定Reader，不改变活动18132配置。

## 真实公开接口验收

隔离来源服务18134发布正式ready收据，源码App在18135读取该服务。`build/daily-history-acceptance-002/RESULT.json`完成15组真实HTTP验收，文件SHA-256为`4219e1dbfce3fd92e2b5c87000f9dec08f6b87554d48660ba800faf8b3d14c34`，规范化结果摘要为`f76c197f6c589b25c909140ba342b6dff154b298d21d2337c8bebd8a2331da41`。

- 300308.SZ：60/5根日线通过；60根日线聚合14周和4月；一年窗口243根日线、52周、13月。
- 588170.SH：60/5根日线通过；60根日线聚合15周和4月。
- 510300.SH ETF返回60根日线；000300.SH指数返回5根日线。
- 周/月每个OHLCV和标签均与同次公开日线逐字段重算一致；不生成缺失交易日。
- 日线省略limit返回60根，分钟省略limit保持240根。
- daily_limit用于日线、years与daily_limit并用、分钟使用years三类请求均返回422。

隔离服务正常关闭，closed收据确认server_closed/native_closed均为true；18134/18135关闭。既有18120、18122、18123、18130、18132持续监听，原实例未改变。

## 回归与剩余风险

App Console、采集来源和DAT导入扩大回归143项通过、1项按既有条件跳过；前端相关3个文件27项通过；`types.ts`单文件TypeScript检查通过。全量TypeScript检查仍被`PersonalWatchlist.test.tsx`既有属性类型错误阻断，该文件不属于本修复范围。

`python -B scripts/project.py check`执行完成并返回失败；失败项为仓库中30份既有未索引文档，覆盖`docs/evidence/*-2026-10-21`及`docs/research/2026-10-29-market-observation-indicators.md`。本次新增证据已进入`docs/evidence/README.md`，未出现在失败清单中。
