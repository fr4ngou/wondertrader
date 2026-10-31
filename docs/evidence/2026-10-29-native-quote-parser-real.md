# QMT真实报价进入原生v6插件

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：运行证据。日期：2026-10-29。状态：三证券实际只读主链通过；原double逐位保真存在下述两项末位差异，完整CTA与长期时效另验。

## 输入与实际调用链

采用[NPV6最终插件](../specs/qmt-native-parser-v6.md)，固定输入为build/native-quote-parser-v6-001/final-install，DLL SHA256为2d422159b21647fa18feed0e3020c735033502e8bbf40bd346b9c53c7bf6c059。根已核该模块8份源码/文档、20份公开证据及11份安装成员摘要一致；其完整替身、搬迁与独审资格沿[模块证据](2026-10-29-native-quote-parser-v6.md)。

根258/265从普通安装HPR e启动原受管Host，连接已运行QMT来源，经认证WinSHM、BoundCore、QmtHostReadClient/Endpoint和原PollingParser到标准createParser/IParserSpi。基础资料读取137/private的sessions/commodities/contracts；本次仅订阅510300、600000和000001。凭据在私有配置和环境中注入，不进入参数或公开结果。

运行沿实际目标工厂接收三报价后，确认stopParser、deleteParser，再关闭Host。265耗时3.500秒exit0，无强制、Job树0、双EOF、reader join及资源关闭；原采集69928与App54752在前后均经系统句柄核实存活，原策略文件SHA保持6be3b6e5d9b41fc6861b40972192e31d7aae72bc73933ca65bddad7ed0a9b89b。未操作QMT界面或启停策略。

## 真实结果与时效

实际Journal仅1项market.full_tick，terminal/ok；三只证券各一次SPI，errors=0。日期、时间、最新价、累计量、累计额逐值一致。对open/high/low/pre_close等全部七个数值字段继续核对，21项中19项double相同，另两项见下一节。

| 证券 | 源时间到SPI接收的样本间隔 |
|---|---:|
| SSE.510300 | 599ms |
| SSE.600000 | 647ms |
| SZSE.000001 | 2127ms |

本次源时间为13:18:09至13:18:10，SPI接收13:18:11.127，使用每只证券的原time与本次回调系统epoch_ms计算。该数值包含来源更新时间、请求调度和运输，不单独解释为网络延迟；一次三证券样本不授全市场或长期时效。原终态queue_wait_ms=375，execution_ms=0，保留厂商/源端原统计精度。

## 两项价格末位差异的原因

600000最高价源JSON为9.950000000000001，原生为9.95；000001最低价源JSON为11.290000000000001，原生为11.29。两者均相差一个double相邻值，绝对差为1.7763568394002505e-15。源原文、原生数值和ULP差均保存，不授逐位保真。

根266/267使用当前同版RapidJSON，复现原parse_bounded_qmt_json所选Parse<kParseValidateEncodingFlag>的数值转换：两个输入均得到上述原生值；加入kParseFullPrecisionFlag后与strtod参考完全相同，两个差值均1 ULP。原解析器源码与251冻结输入摘要一致。因此该差异来自当前自有JSON解析选项，源数据时间/价格关系异常及WT框架改动没有作为解释。本轮生产代码未因此更改，保留独立精度缺口，继续完整产品主链。

## 原件与范围

build/qmt-parser-v6-real-258的INPUTS、PROBE、RESULT、AUDIT、DELIVERY绑定实际插件/探针、三份基础资料、私有配置摘要、终态结果投影及原受管外层。259配对准备2.203秒exit0；256/257原探针构建保留，263/264为加入字段与SPI接收时间的最终探针，6.328秒exit0。价格解析复现266/267为5.875秒exit0，全部正常回收。

验证入口（外部历史/待归仓路径：`../../tests/integration/qmt_host_parser/README.md`）说明参数、生命周期及输出范围。源量额倍率沿当前raw observation配置1:1，不将volume_to_shares字段名或成功读取视为份/元标准化资格；现金ETF准入另核。本轮历史下载0、真实下单0、撤单0、生产切换false、WT框架修改0。完整B CTA、自然分钟驱动、全部证券/长期时效及最终系统安装继续。
