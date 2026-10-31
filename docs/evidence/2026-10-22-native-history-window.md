# 2026-10-22 原生历史窗口与周期查询

类型：实现与隔离验证记录。状态：限定开发验证及独立full/delta通过，开放缺陷0；图表/研究用户入口和生产未切换。要求见[NQW规格](../specs/native-history-window.md)，前置能力与生命周期见[NHQ记录](2026-10-22-native-history-query.md)。

## 行为与职责

原`history.query`增加显式period_minutes与limit。原IRdm负责m1按范围/条数读取，原WTSDataFactory负责5/15/30/60分钟；适配负责右端区间裁剪、最多N根、来源/预算与严格选择器回显。旧请求保持旧响应形状，其他补齐动作不接收选择器。未配置原生Reader返回NotSupported，查询失败没有旧聚合回退。

基础源仍为同一原生DSB。派生range从首日开始取得桶上下文，tail用截止内已有有界基础历史生成，再裁剪最多N；短历史允许少于N，未完成末桶剔除，内部缺分钟继续Unknown。新路径不写Python聚合算法、不保留派生长期缓存；文件修订沿原Reader代际生效。真实时段在Factory前验证，仅授标准沪深日间时段资格，聚合调用在同模块统一互斥。

独立审查发现并修正显式默认C++ HistoryQuery的覆盖网格准入差异；现与HTTP/SDK一致拒绝，旧MinuteRequest保持原语义。没有修改WonderTrader框架；959项可用已跟踪src与本轮开始摘要一致，其他冻结差异保留。原QMT工作树、数据库、真实终端和生产未修改。

## 输入与正式构建

正式构建目标为GuanhengNativeHistoryWindowProbe、GuanhengNativeHistoryQueryProbe、GuanhengMarketBridge、GuanhengmarketTests和GuanhengDataFixture；MSVC x64 Release/C++17。最终日志：`build/native/native-window/build-final.log`及`build-bridge.log`，均退出0。所有源码、规格、测试及关键二进制固定于`test-inputs.json`；测试后输入漂移0。核心摘要边界及结果见`final-validation.json`。

服务端使用真实编译DLL和隔离签名Gateway替身，不连接实际QMT。源树服务测试与已安装SDK子进程分别证明服务和独立客户端。真实行情数据只在独立原生探针中读取原已导入428条并核原目录前后摘要，不将签名替身等同真实QMT下载。

## 结果

| 范围 | 实际证据 |
|---|---|
| 相关原生/消费者CTest | 33通过、0失败、0跳过，76.27秒；28个原市场用例、NQW、NHQ、旧HTTP消费者、策略市场、历史fixture |
| 服务组 | 独立CTest通过；48个Python测试全部通过，无skip，含4项新增wire/HTTP/安装wheel测试，44.54秒 |
| 新原生主组 | 53通过、0失败：42合成检查、10个真实证券×周期查询及1个真实来源总核对 |
| 原生独立时段子进程 | 1通过，非标准时段明确拒绝 |
| 原生独立并发子进程 | 1通过；两个Store在各自根发布，屏障后同时首次Factory调用，两个结果逐12字段核对，分别正常析构 |
| 原NHQ回归 | 原生21项及30配置/4有效摘要坏帧负向子进程全部通过，来源/覆盖/容量/代际行为保持 |
| 策略市场兼容 | 原60个Python测试通过，精确覆盖tail继续原语义，不被图表最多根数替代 |

窗口独立oracle按两交易日的两段120分钟构造480条，每字段使用可区分数值；独立按固定交易段分桶累加，与原工厂输出逐12字段核对。覆盖5/15/30/60、全部区间、首桶内部起点、午休、跨日、截止和尾部、缺口Unknown、非法源右端、修订/追加及旧副本。oracle没有调用Factory生成预期值。

详细结果：`build/native/cmake/test-work/native-history-window/run-2bb36244be304bdc9e091f7a129f46d0/result.json`。main/session/concurrent-first三进程均退出0且valid=true。两证券合计428原始分钟，在1/5/15/30/60周期分别与Helper输入构造的独立预期一致；`real_source_unchanged=true`。合成基础资料仅授读取/聚合开发资格，原239/189条的覆盖与来源限制保持。

实际观察：快速修订背压出现，重试后新基础/派生可见；本次关闭5010ms。耗时限定样本和机器，未测全市场十年吞吐或RSS硬上限。history.query只有大小限制，无可中断服务端执行截止；客户端HTTP截止不取消原生工作。

## SDK独立发行验证

0.11.0通过已固定Flit backend离线构建，基础runtime_dependencies为空；storage extra保持既有声明。wheel为`build/native/native-window/client-sdk/guanheng_market_client-0.11.0-py3-none-any.whl`，SHA-256：`f17501fad582b4d0886bb22203131151e364f186f52fee86526c257cced74c31`。源码与制品清单见同目录receipt.json。

测试用pip --no-index --no-deps --no-compile将此wheel安装到独立生成目录；子进程以-I -S启动，只显式添加该目录并核distribution版本和模块位置，向实际原生行情HTTP服务查询5m、limit=1。返回09:40、20500股、3175元，与合成10条m1预期一致；没有仓库/QMT/wtpy导入，Gateway已置离线且请求数不增加。没有发布或替换生产SDK。

完整服务输出见`build/native/native-window/service.xml`；本轮使用65536字节阈值，48条用例与OK完整保留。相关CTest及完整原始输出见`final-ctest.xml/log`和`final-last-test.log`。

## 审查及剩余工作

独立full报告为`build/native/native-window/independent-full-review.md`；最终delta报告`build/native/native-window/independent-delta-review.md`开放缺陷0，SHA-256为`2d8da1b6a057c214be8a852fd15897b91a51ceb0f7f8df0b13ee016a352f0314`。原默认选择器差异和首次Factory并发验证缺口均已闭合，源码/二进制/日志/wheel输入独立回读一致。资格限定NQW历史窗口接缝，未授业务页面、生产、通用session、复权、日线、DMB混读、所有框架竞争或交易资格。

观衡图表当前仍为Console→MarketData→旧recent_bars；下一步替换该依赖和Python墙钟5m聚合，沿原MarketChartBundle/Console路由验证真实、短历史、空、异常和预算。研究的日线21根、复权因子与可见时点是独立接缝，继续优先复用原生能力并核等价语义。原CTA实时、QMT真实1m补齐与交易适配继续完整目标，SHM绑定及TDX交易仍暂缓。

本轮仅形成SDK wheel与固定DLL开发输入，未制作新完整原生搬迁包，旧包资格不因本轮代码通过扩大。
