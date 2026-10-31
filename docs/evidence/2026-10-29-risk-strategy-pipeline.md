# V3动态风险与迟滞纯业务链

类型：开发验证记录。结果：限定纯算法/独立安装pass，两轴最终full/delta收口。关联[NRH-R1–R4](../specs/native-risk-history-pipeline.md)。完整模块C及M1继续in-progress。

## 根因与实现

此前独立包只有configured V1和V2，V3/迟滞登记项缺少可供原生桥消费的业务计算实现。新增`apps/guanheng/strategy_risk`，公共`evaluate_risk_history`复用core a6、signals a3，迁入固定QMT提交6cf508a070392ff976b6b4d6b31b0e6219001e71的两个纯allocation对象。完整历史先算原特征和八角色信号，再执行动态风险或三日迟滞；追踪退出及无辅助灰灯保持。原生持仓、数量、撮合和交易恢复由B/WT拥有。

数学正文保留原算序与阈值，移植新增显式协作check与本仓模型导入；集合评分按证券排序保证跨hash seed确定性。工具核新正文与预算接缝变换的AST等价。分组/单证券/总量上限、20日总体方差、244日年化、0.05预算台阶、至少0.10偏离连续三日确认保持。旧worker、研究服务、撮合和账户账本没有进入新包。

## 固定身份

本机原件根`build/risk-strategy-001`，最终候选`wheel-005/guanheng_strategy_risk-0.1.0a1-py3-none-any.whl`，SHA256 `2b8ff7a43745229e89dd0ea474e15d5be08893391453260591470a38dff52fb4`。旧004制品/安装及full原件保持。

`SOURCE-SHA256-006.json`冻结最终14源码/规格/样本，摘要`e905c87a71d3b940ee4e32db176ad4c2f16d71bc9f6bd8c42a703ca2689a5920`，review-current-006为同值镜像。最终12 QA/29原件分别由QA-SHA256-006/EVIDENCE-SHA256-006绑定。`DEPENDENCY-SOURCE-SHA256.json`核11个core/signals当前模块与原固定wheel内容相同。原Git对象SHA分别24ac4340…5bf04、bb4f3f6b…21a1d，完整身份随包source_manifest.json发行。

`INSTALLATION-003.json`摘要`434594933bcb81e1e5d30264861d66155b12d3cd840aaad4d302c1df67247bdc`，绑定新普通runtime-venv-003：core a6、signals a3、risk a1、tzdata 2026.3共4发行，670个有摘要RECORD成员；risk wheel非RECORD成员逐字节与安装匹配。require-hashes和uv pip check通过，旧App锁及运行环境保持原身份。

## 实际主链与异常

全部运行沿原`native.run`的隐藏创建期Job、单一有限总截止、输出上限及实际树/EOF/join收尾。

| 原件 | 实际结果与范围 |
|---|---|
| main-003 | 160日八证券1280行→12条原信号；V3 4事件/4风险快照，迟滞3事件/61快照；原追踪退出保留 |
| capacity-001 | 401日3208行合成输入→V3 5事件/5快照、迟滞3事件/302快照；两策略wrapper总2.359秒，非真实数据。后继仅修身份长度入口，数学同SHA复用，不证明4096日全部联合硬限可同时成功 |
| tests-006.log/pytest-006.xml | 23实际安装回归通过；手算预算/总体方差、分组/单证券上限、无信号再平衡、三日确认/重置、直接信号保值/先卖后买、降额缩放/升额保值、初始化/日期目标、来源/因果/乱序、联合预算和不可变 |
| installed-003 | 独立-I普通安装完整公开链与main-003规范bytes一致；实际导入均来自site-packages，无旧QMT模块 |
| 003-seed-1/7/42 | 三个新进程、不同hash seed，均与固定目标JSON逐字节相同 |
| PUBLIC-CONSUMER-002.json | 读取交付INPUT.json，经公开FrozenHistory/SignalTraceInput重建，在普通安装中与两策略交付样本逐字节相同 |
| EDGE-CASES-002.json | 两策略各在进入风险数学后注入截止耗尽，及SST成功后触发最终输出超限；均固定错误退出，无部分结果 |
| IDENTITY-REGRESSION.json | 同一lookup不可达用例，旧004实际触及原pipeline.py:146失败exit1，新005查找前拒绝exit0；短unknown查找一次作对照 |
| IDENTITY-CLEANUP-002.json | 预期旧失败的原native异常确认root/Job树0/创建期归属/管道EOF/join/资源关闭九项全true，无关闭错误或保留owner |

固定输入/目标及公开消费示例在`apps/guanheng/strategy_risk/examples`。null与有日期零目标分开，full-prefix保留既有分配日期。source_qualified/historically_produced/execution_qualified均false。

## 审查与限制

原规格full指出公共strategy_id在准入文本预算前先进入无界字典哈希P2。005在哈希前校验精确str和长度<=64；006补同一原触发的旧失败/新通过回归，规格delta最终complete。规范full、005及006delta均complete，无新增P级。最终SPEC-DELTA-005.md SHA `ccdb4151344e104fef283d8f08890dbe0e8cf25b58bef8d63de8832be01f9d2d`；STANDARDS-DELTA-006.md SHA `838ed1dc458952b40e0a83f8d84c5f208c2c76fa71336afa64991687e09c9551`。原full报告与旧清单/镜像保持；原7 QA副本逐字节匹配原SHA，004/005/006资格分别绑定输入。最终DELIVERY.json绑定全部报告、清单及清单外关闭补件。

原始失败保留：默认venv缺固定包、倒序错误码预期、移植工具两次AST断言、预期旧lookup触发，以及清理QA首次外层GBK展示失败。后者仅展示层，在原native.display路径后002正常关闭，原子日志与实际JSON分别保留。当前候选使用后继成功原件；本轮验证与独审均已终结。

策略页继续名称/简介/版本。本轮尚未把新包接B正式原生桥或App运行选择，未消费A真实历史。原生数量/资金/T+1、AI、全部V1历史版本及ETF/补单、统一安装升级回退、生产与真实交易继续未验。严格逐行可知边界保持，A事后历史首次可知未知不能补造为当日15:00。完整goal active，由A唯一集成提交。
