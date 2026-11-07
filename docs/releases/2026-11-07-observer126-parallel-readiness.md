# 观衡126双策略读侧与原版并行运行准备

日期：2026-11-07。状态：观衡deployed / verified；金融Runtime普通安装与隔离绑定verified，实际金融采用pending。用户已确认现有模拟账户、新策略另100万元、零初始持仓；旧策略和现有持仓保持原归属。

## 根因和正确实现

旧策略详情先用整个绝对截止读取账户，再解析策略，使慢账户接口拖住已有自有策略结果。现在先解析所选策略，已声明独立归属的分支完全跳过全账户读取；旧单策略分支保持原账户口径。同码持仓、成交和现金分别读取唯一ASA归属账，账户聚合继续在账户页查看。金融指纹的原缺省五字段保持逐字节相同。

原版INIT/SCHEDULE与旧策略原回调发布自有原价估值：空仓现金可形成初始点；持仓按原ctx报价和tick校验。任一报价缺失、过期、未来或非法时估值未知。实际手续费未齐时实际净值保持未知，参考值只扣已知费用，页面显示手续费待确认的参考曲线；实际费用补齐后按原发布显示实际点。App只验证并复制，不查价或重算经济账。资本变化率明确为相对配置资本的参考值，连续现金流调整收益率仍未知。新历史按原账/策略/版本/基准隔离，缺价保留最后合格点及原clock。

显式Source恢复需调用Host/Agent的原部署身份API，原Python隔离绑定只含原七包，遗漏了这两个实际owner。现按固定材料SHA选择九包，并使用Host真实发行名guanheng-qmt-shm-host，清点源码及恰一份真实METADATA；无Source旧五/七包保持。独审发现的按文件缺失放行已改为按完整owner首次补入，既有owner新增文件、半绑定补全、改动和移除均拒绝，Core及原金融边界保持。规范唯一正文见[Runtime规格](../specs/independent-wt-runtime.md#显式source依赖的python源码绑定)。

## 实际采用身份

App源码b6da2a2817baf5c3691ba4ff45979de9d39dd74b，标签deploy/observer126-dualcta-20261107。普通安装App0.1.0a126+dualcta.1、SDK0.21.0、只读Runtime0.1.0a11+read15.dualcta.1及原三读取策略包；Web未安装金融ASA执行模块。程序位于E:/workspace/wondertrader-data/observer-programs/a126-dualcta-20261107-001，ZIP SHA916c7778bf2204e5bc2ef71a52d8f2d5af1ac7a234173a9d834c064111ca6b85。

原App125及隔离候选正常关闭；正式端口保持18143。实际App126 PID40232，控制代678d9cc6-4ce8-4e89-9fa9-f7b1a81d080b。稳定observer-current/web-profile.json SHA02c5bdd50ac1b4975fd12c516810f2d0b5f1f1dbb91a7f93e20238db334350dc；DEPLOYMENT SHA3f1e6ee9e041283d3499e68e2bcabaf9987cffd9d368f756cfad5fc69d277a0f。稳定入口status已核ready。沿原私有读取配置，原账户、历史、个人数据和D盘归档路径保持。旧稳定入口两文件已备份。

候选启动首轮缺控制目录、次轮把TEMP/TMP加入只接受GUANHENG_的读取配置，均在生产采用前失败，原记录保留。最终沿原读取环境启动；CIM子进程的TEMP继承值未直接核实，不声称其继承控制器D环境。App可见临时写入均使用明确数据目录：storage.mkstemp指定目标parent，自选使用原数据根；数据Source18的D盘临时环境沿Data27记录独立证明。正式归档继续使用D，E原件保留，C候选从未采用。

最终金融源码c64377c49f3b3941f0348a7cfe1ae785149c0498，普通安装Runtime0.1.0a24+parallel.1、SDK21、Host0.1.0a24+deploymentidentity.1、原版包0.2.0a2及原策略/Agent八个轮子，程序E:/workspace/wondertrader-data/runtime-original-parallel-a24-20261107-001。Native从D:/wt-build/aa3干净构建，26件通过。上述Runtime与Native未启动金融业务、未采用原生产Journal或初始化新金融账。

## 验证证据

受控根E:/workspace/wondertrader-qa/original-live-readiness-20261107-001。v3完整28源码SHA核同；源码主链、独审最终6项与8组oracle、原金融指纹及只读DB字节验证通过。普通安装App22项通过；实际安装SPA/HTTP消费独立合成ASA/profile事实，100万元初值、未知费参考1000200、实际费后1000196.67、缺价原clock、策略切换、390px及悬停0HTTP通过。此为合成发布者与普通消费者主链，不证明实际账户已产生这些值。

正式18143+D归档真实浏览器：列表3671ms，完整报告2890ms（含350ms人为chunk延迟），打开前图表/绩效请求0，悬停HTTP0、点击18ms，旧策略4份记录切换与窄屏通过，错误及写请求0。首次冷读取仍需数秒；没有宣称跨负载受控A/B。

普通安装金融Runtime独立执行两组实际Native配置加载、原Source owner API、父端源码清点、真实-I-S隔离子核验及Host/Agent源码/META四类篡改拒绝，2组通过；业务模块全部来自新site-packages，额外路径仅提供测试框架。该验证使用合成Source56命令owner，不启动Native金融进程或访问真实Source；不能代替实际账户恢复及自然交易日验收。

主收据：APP126-FINAL-DELIVERY.json、APP126-PROFILES-PREPARED002.json、APP126-FORMAL-SWITCH.json、APP126-STABLE-ENTRY.json、APP126-STABLE-STATUS.json、actual-app126-formal/PREVIEW-BROWSER-RESULT.json、RUNTIME-PARALLEL-A24-INSTALLED001.json、ordinary-r24-source-binding/RESULT.json、source-handoff-python-binding/independent-review/REVIEW-v2.json及相应源码冻结。源码、普通安装、Web采用与金融采用分别登记。

## 自动更新与待完成运行范围

Data27/004/18代沿[Data27记录](2026-11-07-data27-units-environment.md)。09:00自然任务已触发，沿原请求完成缺口计划、140项读回及原价/前复权归档，价格版本已经自动发布，原7200秒总截止保持。当前价格版本仍对应11月6日，周六为最新闭合交易日；外部份额/成交额/融资缺项保持未知，完整补充事实发布另验。

升级后复查发现原证券资料Host31168在09:27保存runtime_failed/incomplete，原Runtime66764随后退出；其余三数据角色保持运行。原配置、pair、Agent和Journal路径保持，经普通原服务入口恢复为Runtime53216/Host4656。同一Source实际10只ETF详情及沪深ETF名册首页通过；原30条已terminal/consumed，原RetainedReadJournal正常读取回收，未手工删除或重置，前后原责任已有证据。原前代仅持久化generic错误，历史触发原因仍未知。恢复证据reference-recovery-post126/FINAL-REVIEW.json SHA2296aedd7575be9ada8ac7c859d33609fc2f6af11096e8b1cbf7802180402135。

自然价格阶段随后确已自动发布，CURRENT SHAd22074fde5b21cae879b4c0d50ce419b3c307636b9a5c8527957871cb0aa5765，snapshot b59b2fd12160517571785a9248b8e54996519695a45c17d7bde477b2eebacdec。完整输入随后在复核历史gap-plan保护身份时抛ValueError，主REQUEST尚未生成。普通Data27的纯诊断已在Source/可变owner边界前复现daily gap plan protected identity invalid，原计划和价格发布保持；合同修正和完整自然发布继续处理，不能称本日补充事实已完成。

实际金融采用尚需所选执行时点/买价与589680处理。该证券已有模拟柜台产品不存在的拒单证据；另三只当前可买资格缺直接柜台证据。既有持仓只证明库存/历史，Source允许及行情存在不授可买证明。新策略初次只处理启用后的新信号。原账户P/A、原在途/未知责任、Source实际采用及初始化需在启用时重新核验；合成或副本回执不能替代原Journal。

R24普通安装及真实编译原WT过滤器QA又确认当前九路默认模型仍有上线阻断：589680正目标被原global ignore移除后，ASA协调器精确核同拒绝该合并，attribution_merged_targets_conflict/armed=false。保护继续生效。后续信号会消费，但589680残留BUY的执行报价依赖仍可阻碍其它新计划。将该目标置0的正控通过仅说明边界，不能称现金策略已实现。现金方案须显式名义槽激活/退出状态、等权分母保留槽位、Native/ASA该码目标0、剥离其执行报价依赖，并完成对应WT模型回测；无第二账本或WT核心绕过。该政策尚待选择，现有全九资产WT报告不能冒充现金方案。证据live-eligibility/cash-slot-readiness-r24/READINESS.json SHA f358430ce3599a68813681ec7389c45492ba187509628f47cd3112fcc29ff2e4。

## 回退与采用结论

本次只采用只读App126，实际金融状态没有变更。回退先用当前新安装observer-web.py及稳定profile正常停止，再用保留App125和原profile启动，恢复已备份稳定两文件并重验18143；无自动回退已发生。新增ASA估值历史另按身份隔离，原单策略历史路径保持兼容。本记录不授后续双金融Runtime启用后独立回退到旧Web的资格，届时应核当时协议与组合。
