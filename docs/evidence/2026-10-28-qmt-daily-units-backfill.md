# QMT日线单位与内置补齐实机验证

日期：2026-10-28。范围：[DSH](../specs/qmt-source-daily-history.md)源日线、首策略9ETF的来源字段与补齐主路径。状态：单位修订及单ETF内置补齐已验证；共享内存按需补齐能力、其他证券缺口及盘中采集继续开发。无真实下单、撤单或生产切换，WT框架未修改，旧QMT项目保持只读。

## 来源单位及证据边界

迅投[现行K线字段表](https://knowledge.thinktrader.net/docs/cloud/data_function.html)明确覆盖1d并将volume定义为手；amount仅定义为成交额，未直接声明数值尺度。[沪市ETF规则说明](https://www.sse.com.cn/assortment/fund/etf/question/c/c_20240118_5734754.shtml)与[深市ETF指南](https://www.szse.cn/www/investor/warning/t20210104_584079.html)说明ETF一手100份，基金价格为人民币元/份。公开接口族定义、本机接口映射及数值一致性分别记录。

本机外部qmt_api.api.getMarketData固定源码SHA256为cc695081bf5e018e98e6ad2a0d56526c48c1fe91869f3329482346adf874ab34。绑定period=1d、dividendType=none、9ETF清单、显式日期及逐原始响应SHA；camelCase封装与官方接口族的关系属于本机窄范围映射，官方页面没有直接点名这个安装文件。新profile采用price_unit=CNY、volume_unit=lot、amount_unit=unknown；lot在这批ETF表示100份基金份额。数值保留原样，转换为基金份额须由明确消费规则执行，不能泛称股数。

全部原7739行的amount/(volume×100)位于该日OHLC范围内，是金额可能为人民币元的数值佐证；本次没有据此提升amount单位。原始检查及公开证券资料在build/qmt-daily-unit-check-001，包含9只证券上市日；515080、588000、159780、510050、512100的缓存起点晚于上市日期，确有历史范围缺口。589680、589000从2025-03-05起与其上市日一致。场外IsTrading=false不作为永久停牌判断，VolumeMultiple=1不作为手转份因子。

原7739行unknown-unit数据根保持。新的manifest、UNIT-EVIDENCE及PROVENANCE在build/qmt-daily-unit-profile-001；051从固定039安装包使用原Helper/day DSB和Reader完整回读7739条，源数值、日期及新profile一致，5项原日线布局拒绝回归通过。实际2.032秒exit0、无强制、树0、EOF/join及资源关闭。052通过042固定SDK wheel、搬迁039组件及同一服务混合读取原分钟和新日线，21.781秒正常结束。单位修订没有改变旧DAT分钟或全推profile的资格。

## 外部SDK与内置函数的实际差异

国信当前安装的xtquant.xtdata可显式连接本机报价进程127.0.0.1:58610；048读取510300/589680日线仍均为空，data_dir保留默认相对路径。安装源码中的get_local_data为返回None的空实现，连接成功本身没有证明可用历史读取。049仅尝试一次外部download_history_data，先保存589680原缓存备份；函数立即返回None，源缓存SHA/大小未变，内置查询尾部仍为2026-09-28。此结果记为补齐未成功，没有重复请求或以返回None判定成功。

迅投[内置行情函数](https://dict.thinktrader.net/innerApi/data_function.html)同时提供全局download_history_data；本轮在原GH_WT_MEMORY_VERIFY正文追加一次诊断after_init，固定589680.SH、1d、20250305..20261028。诊断保持原行情正文、配对及订阅清单，不读文件、不建立网络连接、不调用账户/委托/撤单。050使用安装自带CPython3.6.8编译检查通过；在QMT原编辑器编译保存后，界面确认框无法激活，重新选择并重试一次仍失败，用户随后确认运行。其他策略未改动。

build/qmt-daily-builtin-backfill-001/OBSERVED-001.json的固定诊断标记证明：全局函数可调用、实际94ms返回，随后ContextInfo.get_market_data_ex(subscribe=False, fill_data=False, dividend_type=none)读到401条，首20250305、尾20261028。缓存由24584字节变为25672字节，SHA256由91ebd135f9bfa92686d36680e45a411b6797bac8479741082cc8fbd46a9d3014变为13b622c67a1a0b3e00b7d9f02ac5c78195aa17d85f9ab5100e5288b34011c03e。函数返回、文件变化与原API回读共同证明这一次补齐成功。

原策略磁盘正文已逐字恢复为fb10247053776adc1fc0e700a22d9672d4053c224128a12f40e90615d2831239，RESTORED-FILE.json留存编译后的诊断身份和恢复摘要。本次after_init已经结束；运行中的行情部分与原正文相同。恢复文件后没有再重启运行体，不能把磁盘摘要写成运行体重新加载的证据。没有重启整个QMT。

## 补齐结果进入WT与公开SDK

053使用原外部只读getMarketData重新取得9ETF，原始回复、日期和值保存于build/qmt-daily-backfilled-source-053，实际0.703秒exit0并完整回收。只有589680执行过下载，其他8只的缓存保持；不能把这一次结果宣布为9ETF全部补齐。

| 证券 | 当前条数 | 当前尾部 |
|---|---:|---|
|510300.SH|1205|2026-10-23|
|515080.SH|1149|2026-10-23|
|588000.SH|937|2026-10-26|
|589680.SH|401|2026-10-28|
|159780.SZ|783|2026-10-23|
|510050.SH|763|2026-10-23|
|512100.SH|917|2026-10-23|
|510500.SH|1205|2026-10-23|
|589000.SH|396|2026-10-23|

新manifest及单位证据在build/qmt-daily-backfilled-manifest-054；054使用原Helper重新导入到独立build/qmt-daily-backfilled-native-054/store，完整7756条源值/日期/单位回读一致，5项布局坏例仍拒绝，1.907秒exit0并完整回收。原035、051数据根保持。

055的公开SDK验收因QA把结束日期固定为20261027而失败：返回400条589680日线，原始已补数据为401条。已修正正式验收入口tests/integration/source_market_process/run.py，按本批RESULT.json的requested_from/requested_to构造日期窗口，并将实际query写入逐证券证据；完整条数与逐字段断言继续保留。失败作业10.594秒自然结束，树/EOF/join/资源均正常回收。

056从039 ZIP搬迁并核147运行文件，使用042固定SDK0.14 wheel，受管启动正式SMP服务，注册335分钟根及新的054日线根：5个真实分钟样本、全部9ETF7756条日线、同证券跨周期重查及原Reader完整值/日期/来源/单位对照全部通过。589680的公开SDK结果明确401条、尾20261028；原分钟结果保持。实际20.437秒exit0，非强制、树0、EOF/join、资源关闭且监听端口已关闭。结果位于build/daily-backfilled-wheel-main-056/VERIFIED.json；这是独立安装组件/SDK的开发验证，未切换活动App配置。

本轮生产实现无新增变化，复用039/042已验源码；改动限于来源资料、profile/数据修订、模块说明及两处验收输入逻辑。单位事实沿独立来源审查，源码验证复用原固定候选，QA变更按055原失败与056完整链核实。自动补齐控制链仍须独立完整审查。

## 后继工作

正式补齐沿内置全局函数，由现有认证SHM和原策略线程接收显式请求；不采用外部SDK无效果路径，也不依赖用户临时进入下载界面。按任务范围/额度限制证券、周期、日期、队列和总截止；原生调用不可强制中断时保留未知结果，并以回读核查数据。共享内存接线按[HPR](../specs/qmt-history-preparation.md)继续开发，本次单ETF诊断不替代完整功能。

058另外只读核实已安装xtdata的沪深市场get_trading_dates，两市场均为空，0.453秒exit0并正常回收；这表示该外部通道没有提供可用日历，不表示区间没有交易日。未调用get_trading_calendar的工作日合成分支，未根据周一至周五补造完整覆盖。

9ETF其余尾部及早期缺口、全市场ETF分钟覆盖、真实盘中分钟连续性、分钟边界/来源时钟与闭合知晓仍未完成。源码和数据版本修订不授实盘资格。
