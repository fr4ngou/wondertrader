# QMT普通查询、待确认委托与事件链混合容量

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-26。状态：C03/C04各1/1及默认十二案12/12实际通过；独立静态及动态审查通过。完整容量矩阵、首次/重连交接及生产继续待验。

## 真实调用链与测试边界

沿[标准实时事件规格](../specs/native-qmt-standard-events.md)，以专用同源测试DLL及原Factory、固定原版WT TraderAdapter、真实Host/HMAC/Windows命名共享内存运行，源SDK为显式替身。真实四查询和首空链退休后，响应门A暂留普通账户Query终态，原Adapter.buy建立真实Pending；门B在源SDK返回后暂留原委托POST响应，使普通Query完成值、活动Insert、Pending与排队EventChain同时存在。门只延迟原文响应。随后pump(1)沿原getBaseDataMgr两次观察旧Query借用和Pair/Resolve预留转交。

专用DLL输出到resident-test-traders，正常TraderQMT.dll保持原61c9f81e2094dedae1c05bddbf364af1888f3a424faa779985afefb21f4d1980。bridge只在DLL内沿原owner/锁读取固定POD计数与长度，EXE通过版本/size固定C ABI取值，不跨模块读取私有STL、mutex或持有权。活动槽只读已稳定字段；ready槽在commit后读取。产品Standard.cpp摘要db13dc15a03a30db861d0e2c7d416370a9f598d4e24e2b419556647f99b844c6及26份框架保护摘要保持。

旧候选001的final继承及非虚基类析构两项测试阻断在新002闭合：专用复用模式允许派生并保证虚析构，默认公开十二案的final定义保持。旧冻结包保留。其余四候选字节不变；没有修改WT基类。

## 构建与实际运行

固定原上游08b230dd05facf6d650d949bfe51054115a2ecb1，170自有输入、323上游输入摘要逐份核验。三个目标NqpResidentTrader/NqpResidentProbe/NqpStandardEventQueryProbe共179步，81.062秒通过；21项所选对象最大绝对路径214字符。制品摘要：专用DLL591dc6fc81f2c5048dd927ab30852832dfb040c613c563758c8e866b7ad7bba0，resident EXE72b08f0955c1e2174b257fe8472e423899644c8783c16e7103048b5753bbe029，默认probe0e62e77aa74d0b21a5ebd9e6eb7a237a5cd68e1821f81a819b86e6e0f075c8e2。

| 输入 | 额度 | unittest | 控制器 | 结果 |
| --- | --- | --- | --- | --- |
| C03 | 256 MiB | 1方法，4.300秒 | 9.094秒 | 通过 |
| C04 | 512 MiB | 1方法，3.659秒 | 5.406秒 | 通过 |
| 默认正常DLL S01–S12 | 原功能配置 | 12方法，36.638秒 | 38.578秒 | 全过 |

两容量案除容量、case身份及每次运行自然生成UUID/期限外保持同一配置：q16/p16/H262144、rows4096、I4MiB、L/V各1MiB、index4MiB、request8000/timeout2000/close4000/eventpoll150。冻结170份Python输入，继承旧169份仅替换fixture默认可扩展hook并新增resident测试；原冻结驱动的截止、来源前后核验、实际模块追踪、主异常及关闭逻辑保持。

## 独立费用与业务结果

两案均实际得到：before=100168047、旧Query借用首观察=100168047、Pair/Resolve预留后=100218899、旧Query退役后=99582867字节。独立账单逐点相等。Pair=50340，新增加Pair+512=50852；旧Query费用635520+512=636032在真实析构后退款。该窗口同时保持三份任务名额及原Query id/D向Resolve转交；固定HTTP128预留42487744字节。这里是逻辑额度，不表示进程RSS上界。

真实原生持仓/可用/未完成量为100/100/100，账户回调2、委托推送1、成交推送0；源SDK替身insert恰1、cancel0，实际补查1、源事件seq1与后续after_seq1得到确认。释放后pending0、payload0，原worker正常drain/join、实例删除。父/子原总D、创建期Job、无强杀、tree0、双EOF、reader join、Host/Source资源关闭分别核验；源回报与Host原通信事实没有由测试伪造关闭状态代替。

默认新probe与正常DLL十二案全过，保留默认fixture和CAdapter兼容证据。前轮纯状态33例378断言的代码及其入口保持原样，本轮未重复运行。所有真实SDK调用为0。

## 独立复核与剩余范围

静态full/002 delta/构建及驱动复核（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/resident-six-source-full-001/REVIEW.md`）新增已确认P1/P2为0；根核216份审查原件及正式8项测试/接线绑定。见实施收据（外部历史/待归仓路径：`../../build/qmt-c-resident-implementation-001/INDEPENDENT-STATIC-ROOT-VERIFIED.json`）、构建（外部历史/待归仓路径：`../../build/qmt-c-resident-implementation-001/BUILD-ROOT-VERIFIED.json`）、C03（外部历史/待归仓路径：`../../build/qmt-c-resident-implementation-001/C03-ROOT-VERIFIED.json`）、C04（外部历史/待归仓路径：`../../build/qmt-c-resident-implementation-001/C04-ROOT-VERIFIED.json`）及默认十二案（外部历史/待归仓路径：`../../build/qmt-c-resident-implementation-001/PUBLIC12-ROOT-VERIFIED.json`）。动态独立复核（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/resident-mixed-dynamic-001/REPORT.md`）82项检查通过、新增已确认P1/P2为0；根逐份核178项新raw，见动态根核收据（外部历史/待归仓路径：`../../build/qmt-c-resident-implementation-001/INDEPENDENT-DYNAMIC-ROOT-VERIFIED.json`）。实际Ninja图同时核唯一snapshot TU及真实Factory、DLL/EXE宏隔离与统一MD；递归原文fact的2529次长度/SHA核验含嵌套层，不等于唯一物理raw数量。

本片只证明这两项混合输入，未独立重证整个Static/Owner/Worker银行最大值。Audit与unknown Pending收据转交、need/need−1、实际HTTP满128槽、完整OOM/父死亡矩阵、券商查询与实时回报覆盖及正式用户入口仍待验。未做生产切换、终端重启或真实交易。
