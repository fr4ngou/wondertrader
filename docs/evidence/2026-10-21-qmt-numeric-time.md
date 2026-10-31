# 2026-10-21 QMT 整值浮点时间戳适配

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：修复及真实来源验证记录。范围：HTTP-R2 的自有 QmtHttpEndpoint 数值解析。状态：真实回归、独立delta及59项启用CTest通过；最终制品身份见本记录后续验收段。关联[真实历史导入](2026-10-21-real-qmt-native-history.md)。

## 根因与修正

用户恢复18010后，自有行情接口的capabilities和quotes.query成功。首次历史准备诊断没有提供日历网格，队列按现有规则保持不可执行；补充明确命名为 `diagnostic-grid-not-authoritative-v1` 的240标签诊断网格后，真实history.work返回InvalidInput。

直连保存的 market.market_data_ex 结果共428条，与此前Bridge读取的正式样本逐值一致。所有历史time均以JSON浮点数表示，例如整值毫秒数的 `.0` 形式；full_tick.time为JSON整数。QmtHttpEndpoint原epoch_of仅接受IsUint64，拒绝了数值有效的历史时间。该问题位于自有适配层。

修正后先检查JSON数值类型，再检查有限、非负、整毫秒和既有最大日期范围，随后转换为uint64并沿用原日期校验。允许范围远小于2^53，整毫秒转换无损。字符串、布尔、可表示的分数、非有限值和越界值均拒绝；历史分钟格点、顺序、范围、左右标签和同源时钟闭合检查保持。校验对象是已解析JSON数值，未声称恢复解析前任意精度十进制词法。

源码为 `src/GuanhengData/QmtHttpEndpoint.cpp`，测试为 `tests/integration/market/qmt_http_endpoint.cpp` 与 `tests/integration/http/test_qmt_http.py`，规格为[HTTP-R2](../specs/qmt-http-market.md)。本次没有修改WT框架源码；12个冻结文件摘要核对一致。

## 红绿与来源证据

- 原始直连类型、前后同源身份和逐值比较保存在 ignored 的 `build/native/live-source-probe/direct-diagnosis/wire-73abf143dd4e44a797ece27958e712c6/`；带诊断网格的旧DLL失败保存在 `grid-945940ce04f44cae89f954434bdcc8b0/`。
- 完整隔离HTTP服务链只把wire time改为整值float，旧DLL失败、新DLL通过。脚本为 `build/native/live-source-probe/semantics/time_numeric_red.py`，旧DLL SHA256为 `ab3ef3b9ab078ffcf10dc8b90eff13831430e6d0e445f45380e9ea36e3ab8156`，新DLL为 `eefbdda044080b739f0e004e7164c7d3a4de014d65805d7a5c76efe74d1dcbff`。
- 新增原协议用例验证 `.0` 经既有协议序列化和原生HTTP客户端后保持数值；端点回归验证整数、整值浮点及指数表示等价，tick毫秒精度保持，14类非法值和历史非分钟格点拒绝。

独立审查范围为delta：来源时间戳数值准入的局部修正；既有身份、权限、队列及存储职责保持。独立报告（外部历史/待归仓路径：`qmt-numeric-time-2026-10-21/delta-review.json`）结论passed，无发现，另行运行8项原生端点及3项原协议测试通过。根任务核对报告的11项源码/规格输入摘要均与最终文件一致。

## 资格边界

诊断网格只验证取数、归一化和缺口返回；它不替代日历事实所有者及证券例外。当前真实样本的源单位/金额精度资格仍为DevelopmentVerified，全天权威覆盖unknown。接口中的NativeVerified代表原生适配契约验证，不能提升源精度或交易许可。真实原始数据与身份只保留本机ignored目录，未部署或操作账户。

## 真实直连回归

新版DLL经真实18010读取→归一化→NativeHistoryStore写入DSB→history.query回读通过。运行前后DLL摘要相同；`direct-diagnosis/grid-b64aa0eabda14667be9ce6fdd1c70002/observations.json`保存完整结果。

| 证券 | 实际根数 | 与正式raw逐字段比较 | 诊断网格缺口 | 同实例再次query |
|---|---:|---|---:|---|
| 300308.SZ | 239 | 时间/OHLC/volume×100/amount×1全部一致 | 1 | 完整结果一致 |
| 688076.SH | 189 | 时间/OHLC/volume×100/amount×1全部一致 | 51 | 完整结果一致 |

两证券coverage均为Gaps，work保留Pending，正确反映当前参考网格下仍有缺口。再次query只读本地缓存，未额外访问来源。本项同实例重复读取证明缓存稳定；外部修改后同实例重新可见性由专门reader插件任务验收。

## 完整开发制品验收

执行 `python -B scripts/native.py all --offline --qmt-source D:/workspace/qmt --calendar-owner-source E:/workspace/qmt-worktrees/wondertrader-service-adapters`，退出0，20阶段全部passed。59项启用CTest全部通过，另1项既有全天用例Disabled；32项构建流水线测试通过。包级wheel-only统一策略→HTTP/native/DSB→原分钟消费者、原生回测、日历及worker恢复验证通过。

新包为 `build/native/packages/dev-20261021T094332Z-ae735c61.zip`，SHA256 `4840c83263e016aeae4c057cf9ccd620783b9c74732b3c3b86ebc0b1af277523`；SDK仍为0.6.0，六源码wheel摘要未变。冻结完整收据（外部历史/待归仓路径：`qmt-numeric-time-2026-10-21/receipt.json`）、CTest结果（外部历史/待归仓路径：`qmt-numeric-time-2026-10-21/ctest.xml`）与实机脱敏摘要（外部历史/待归仓路径：`qmt-numeric-time-2026-10-21/live-summary.json`）。

新包包含原有冻结待审框架差异，资格为开发验证；其余框架差异的审批边界保持，未发布生产。文档治理检查通过，整个移植目标仍active。
