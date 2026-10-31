# V1保留历史版本及共同安装

类型：开发验证。状态：done（后继002纯链及固定普通安装、双轴full/delta）；完整C保持in-progress。

## 根因与实现

此前完整保留范围尚缺V1 1.0.0/1.1.0/1.1.1的独立完整链。本轮新增`guanheng-strategy-v1 a1`，按[LVH规格](../specs/legacy-v1-history.md)连接全部冻结日线→core a6原特征/八状态机/分配→完整八目标和模型状态，分别保留589680信号、589000 direct信号及1.1.1首次regime起点。原unit0.125/cap0.25/capacity1及原raw权重保持，不改名为configured1.2.0。实际周期/分析窗口版1.1.2继续独立接线。

共享signals a4新增公共`prepare_signal_history`，在原唯一准入owner内生成独占不可变历史快照；原a3默认trace身份、数学及JSON保持。V2 a3/risk a2将精确依赖及运行guard同步到a4，pipeline源码去唯一guard版本字面量后与既有批准wheel逐字节相同。Appa18元数据统一依赖V1/V2/risk/AI/ETF等已交纯包，uv.lock离线重解；本轮尚未构建/运行新App，A继续消费固定Appa17/SPA011原制品。前端/B/WT修改0。

## 固定来源及主链

仅读旧QMT固定提交`6cf508a070392ff976b6b4d6b31b0e6219001e71`的V1目录/registry，通过原native隐藏Job执行git archive保存45个Git对象原字节，共482892字节，未导入/运行旧工程。四数学源raw CRLF SHA与LF归一化SHA分别记录；归一化身份与core a6已有来源逐一匹配，见`build/v1-history-versions-001/SOURCE-IDENTITY-INSPECTION.json`。原runtime/configuration/backtest起点和证券选择仅静态核对。

三个明确合成240日/八证券/1920行输入各产生19个信号决定、19个分配事件与完整八目标。每个direct case分别产生589000价量及来源身份，未重标589680行情；前110日灰灯，随后合成份额/概率/百分位声明其知晓和内容来源。先跑源码主链，再普通非editable新环境执行公开JSON样例、`-I`、hash seed1/7/42及4成员ZIP实际解包。完整TARGET JSON SHA为`ccd71f1e90fe2f6665fe04b74b971b5868581ae5c3aedc79a08618b466ceb713`。

原22项SST安装回归和61项V1/V2/risk业务安装回归全部通过。新增人工CSI oracle核0.25×(1/3,2/3,1)×0.8及反向三步退到dated零，原无事件初始零保持source_date=None；原早期无regime分配失败、1.1.1真实gate与BT先算全特征后切范围分别验证。错证券/执行映射、实际周期/其他版本拒绝、未来/重复/缺证券/来源/数值/OHLC、联合预算/总D与不可变结果/共享快照同时覆盖。

旧a3普通App安装与新a4普通安装对同一完整样本的SST规范JSON逐字节相同，SHA为`1d01ab217cba9e342b72d3439f447a53a069248909825bad518a9ba77bb851cb`。兼容输出及V2/risk依赖唯一差分原件见`COMPATIBILITY-001.json`。

## 安装及身份（首送审001）

普通`runtime-venv-003`为7发行/702带摘要RECORD；独立`test-runtime-001`为13发行/1216带摘要RECORD。两环境全部记录/大小/路径，以及六产品wheel全部非RECORD成员逐字节核对；tzdata沿固定已锁发行记录核验。所有实际产品包来自对应site-packages。

| 制品 | SHA256 |
|---|---|
| signals a4 wheel-002 | `8d10d210a9bf327afbb175b3ba9b1a5e2345a15e5d3019520de01b2b444047b7` |
| V1 a1 wheel-002 | `151b79119f9706654bbeceea75f4bcf237e4516a32e31876bfd8738e1fb2e36c` |
| V2 a3 wheel-002 | `594d874a501496564783375c362e71971ee6e595215a765811b706c774e570d7` |
| risk a2 wheel-002 | `9370c2ac93c0a4f7f2b2b7b5040c1703279ac1e0b49d58c3e3ed801ef24f2b95` |
| 样本ZIP003 | `642efe0bd02e98749ba89cb468d13765725d0e7cd50a271edc3b00798ce7bf52` |
| Appa18新uv.lock | `4b7357d9a0e90e233f854ef33349bb1da95d9c6a04332882b31abbcaad594477` |

58源码/12 QA/128原件和对应review镜像已冻结，SOURCE/QA/EVIDENCE清单SHA分别为`7d2e9fc740bdd444470ba912c25ece8ba06f464cd635fbf14256b8b1d97a03d5`、`f7a94c072aa5c855d669d0fbc0a2fb4be7a5f4c693cff6970550e332190e3320`、`c8c42fc948aa7b38f430a973aad26d680094693d0f44862ea8359b25e860f3ac`。普通安装收据SHA为`df606f4f146987a0e965f3880138e0bb9cd08a6cf42a5b0a31cdc72d0077697f`；安装测试收据SHA为`a143d6c5f687f99798bbbbfd550cdadeca8ef73a3e2c60d06cc3c90308093a5d`。当前独立规格/规范full按这些输入审查。

## 后继002与最终独审

001双轴full均独立复现一项P2：共享prepare在实际模型校验阶段到期抛出的calculation_timeout，被ValueError总括边界改成invalid_history，完整V1入口也继承了错误分类。原001 full及开发者/两轴独立反例保留。002在唯一history.py先传播自身SignalTraceValidationError，再归类普通模型值错误；公开prepare/V1两入口均新增原阶段到期回归。正常数学、起点、TARGET全部字节保持，22项SST及63项V1/V2/risk安装回归通过。

新wheel-003、普通runtime004和QA test002独占安装通过7发行702/13发行1216 RECORD及全部产品wheel成员；三seed、4成员解包与原SST/a4字节兼容继续通过。样本ZIP004 SHA仍为`642efe0bd02e98749ba89cb468d13765725d0e7cd50a271edc3b00798ce7bf52`，完整TARGET SHA仍ccd71f1e…ceb713。

| 最终新制品 | SHA256 |
|---|---|
| signals a4 wheel-003 | `c190762cdd7bdada8cfc91f56fb4f82337f49a7a1f8f9b3983f1360f5779e5bc` |
| V1 a1 wheel-003 | `eee33408d896c9fe5f27f108efd3b5ba4e6feb2d5c06a5c1af853a9af66865e5` |
| V2 a3 wheel-003 | `d500553e77a5c20651f6610079d179822b1d97a924a86c07f6983b3af4111c35` |
| risk a2 wheel-003 | `91004dd38627031f5d2071953f5b980e594d71a29d0d82ac2bf0e138fa12a560` |

最终60源码/14 QA/188原件及review镜像由SOURCE/QA/EVIDENCE-SHA256-002.json固定，SHA依次为`adc53d6409e1016bd1175f34b4ca9274ca26154c60e7a277c2c5ff1e7d81b4dd`、`9ed82ad9c60260f41711604fa9fe3c764bf71cec190a0d574fff2f92b8a1c926`、`5fb102ad336cff52e3a474d49c90f9e93e025d4fde134d9160e103a2975e738c`。INSTALLATION-004.json SHA为`c537600e3f6fe544a1ce65b9850eb079e911e196f080d7574604a91582e5c68c`，INSTALLED-TESTS-002.json SHA为`c3c42e8c55990d4619236019499ce2baa6d01c17d36ba91313bdb109795438a8`。

A同轮明确交接SDK0.15版本及Appa18市场SDK依赖14→15，新增两份SDK源只静态复用A正式合同。APP-METADATA-A015核App元数据相比001只有该A片段改变，C所有新策略依赖保持，uv lock --check --offline通过；local dynamic SDK锁条目未记录version，根锁SHA保持4b7357d9…594477。SDK source_history.py SHA为`1c870d623eaeb16cf118aec3f883a6fe0931440bc62820572220768576e7ab01`。这只授静态依赖接缝资格，RS13 Partial/source_window/provenance的App投影及实际新App验收继续。

两轴最终delta均complete（LVH-R1至R4纯链及固定普通安装），原P2关闭，新增P级问题0。SPEC-REVIEW.md最终SHA为`bbd009be09c14b5a52151b1e4579811936e8c20535421a84f5d760c6b6cac33f`，STANDARDS-REVIEW.md为`443582469709989e07b21522460a110402f7976f7d1eed80d515e5545b6c087d`。新独占delta探针的SHA和原native实际收尾由报告绑定，不覆盖188份已冻结原件。作者新普通004安装10.500秒、安装回归12.406秒正常关闭，所有本轮作者/独审运行均终态；finalize.py002再次核输入/镜像及报告并执行project.py check，交付结果由DELIVERY与外层成功后的FINALIZATION登记。

## QA故障与运行边界

首次install002已完成7包安装/兼容及隔离三版本主链；seed启动因QA根脚本`inspect.py`遮蔽标准库inspect而失败。原log、初始主链及环境保留。QA脚本改名`source_identity_probe.py`，seed入口使用`-P`且清PYTHONPATH/HOME，新runtime003全部通过，产品未因该故障变更。002缺专门失败cleanup JSON，同次退出码为1，后继成功收据不替代旧同次关闭证据。

当前成功的主链/新安装/安装回归/审计/兼容/冻结均经原native.run隐藏有限Job实际返回，覆盖树/EOF/join；普通003安装实际10.032秒收口，其他耗时沿各CLOSURE原件。当前这些执行均终态，没有据JSON存在推断存活状态。

## 剩余范围

本轮只证明显式合成日线的三版本纯链与共同依赖安装，source_qualified/execution_qualified/historically_produced均false。旧raw分配可能大于1，账户/资金/T+1及执行资格不由该包授予。1.1.2的实际周期/因果分析窗口、A真实来源、原生桥/BT/实时、Appa18实际安装页面和完整M1、统一升级回退继续。按最新TARGET退出WT潜在线程/仓位所有权调查前置，后续实际故障沿现场处理。策略页仍为名称/简介/版本，未发布、真实写、操作QMT或Git集成。
