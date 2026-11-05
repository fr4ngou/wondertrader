# 形成中日K、日线小批补齐与HPR兼容采用

类型：线上增量记录。时间：2026-11-05北京时间18:40。状态：行情增量已采用，金融运行已恢复，整体目标仍in-progress。授权沿当前模拟账户主线目标；本轮没有新增WT框架差异。

## 实际采用与正确实现

- 采集program018/data-service004复用原Writer和数据根。自有DataKit导出读取原`getCurTick`值副本，在原状态周期原子替换唯一`current-day.json`；没有在App计算日K。实际7582条、1404177字节，检查时本次临时文件0个。原快照时刻保持，不能将18时读取当作18时价格。
- SDK0.18的`view=current`和WT `source-current-day`组合形成中行；默认、归档和策略闭合窗口保持。归档同日优先，`closed=false`明确表示当前值。股票300308、ETF588170、上证000001经真实QMT、隔离原Writer、正式SDK和App日/周/月逐字段回读；线上九组图表均包含上海11月5日。线上原源时刻分别为14:59:06、14:59:15.452、14:57:13，当前值尚不代表完整收盘归档。
- 原分钟读取三类样本分别返回240根；股票及ETF尾部15:00，上证14:58。范围与最后时刻分别记录，全市场连续完整性另核。
- unified.20/program-currentday-20261105-003、daily-service010采用价格先发布及原SDK四worker小批准备，保留原请求、slot、缓存和publication。SDK回执临时名由重复完整SHA改为同目录UUID，实际路径从265降到196字符；目的路径、原身份、fsync和原子替换保持。原逐项通信约1.05项/秒，采用后的实际吞吐与最终覆盖仍需取证，合成3.49倍不作线上速度承诺。
- HPR兼容Host `0.1.0a22+mdphttp.2.hprreject.1`普通安装到hpr-runtime003，hpr-service002受管运行。保持原Agent `marketdaily.4`、配置、权限、额度、Journal和QMT正文，正文SHA `0657ae143dab867d8c99224e99b6166ea3f01a2b6f9c76113eca38cc3a26d22f`。合法控制拒绝持久收束原请求后继续后继请求，协议损坏仍按原故障处理。来源/安装/关闭依据见[兼容闭包验证](../evidence/2026-11-05-hpr-compatible-closure.md)和[拒绝回归](../evidence/2026-11-05-hpr-control-rejection.md)。
- 独立观衡a113+currentday.2、只读Runtime read9已上线18143。新版实际行情页页脚显示简短原快照时刻；WT关闭、更新和下载继续由WT管理。旧a112正常关闭，两个读池0线程、解释器及launcher退出码0。新观衡PID2772，控制代32164b1d；WT六角色清单、日常快捷方式和当前部署记录采用group017。行情、策略、系统状态页刷新及九组图表实际检查无控制台错误；资金资格问题另列，未授整个系统完成。

## 输入和验证依据

私有证据根为`E:/workspace/wondertrader-qa/current-day-20261105-001`。形成中整链见`actual003/RESULT.json`、`LIVE-CURRENT-DAY-SDK.json`；线上分钟见`LIVE-MINUTES.json`。最新页面见`CURRENTDAY113-RECOVERED-UI.json`及同名三页截图，字段中的真实资金资格比该脚本当时的宽泛passed标记更严格，不能由passed推定资金可用。

采集自有DLL SHA `6a0f8ce04618e6aa8a3f47f6482968e8374eb5c3bc972f9eeb3ff221a1a77f37`；该导出为已核原库上的自有增量构建，原Writer/Reader二进制保持，没有将增量描述成全新框架构建。unified.20制品manifest SHA `53f46ed994cdc22ce14c6e9dc9d27f7e0d8ca7757d3ffd56e923a57fe0f81c3f`；App制品manifest SHA `0020afe7a01d9965686abca16d62a53ba8eab9877eac5884ba2c1b33b188160d`，安装SHA `94cec6907a3c3b866f41d2921ea4555d7a80ccfc15f76325be22c8cae5318c6b`。构建源和逐文件身份分别在对应BUILD、SOURCE-BUILD及INSTALLATION记录。

根因回归：形成中K及App日线92项、投影与委托7项、HPR原安装类11项、并发/原回读4项、前端最终输入6项通过。独立审查确认形成中数据职责和价格先发布；小批补齐的取消检查缺口已修并经独立delta关闭，原ID、截止、未知结果和有界worker保持。HPR兼容源码由另一实施者提供，Root核实际旧基线差异及普通安装类主链。文档静态检查通过；构建、隔离与实际来源分别取证。

## 本轮真实金融故障及恢复

18:10:29原Native c8fd1607退出，plugin_error=10/host_fault=3/session_fault=4，原因摘要对应`qmt_host_native_operation_failed`。原交易Journal末条账户只读查询76b46bf1、seq708返回`operation_interrupted`。原账、委托和周期原件保留，未重置100万元基准或补造成交。适配层将只读中断当作硬故障的处理仍在修正。

第一次原服务恢复在analysis_host启动阶段失败，execution尚未启动。单独原配对验证及原受管分析Host正常启动/关闭通过；该次最初启动异常的原stderr已随原owner释放，底层首因缺证。随后从最后实际执行c8代准备原恢复材料，activation005已恢复同一逻辑实例e474deb3及原financial-state008。当前WT e52b4ef9、WRI6680、Native92ef1149/PID21660，账户持续更新，总资产1002101.8元、现金余额452011.1元、原五个实际周期和588030的100份持仓保持。

六角色ready与真实可用资金分列：资金投影仍间歇出现account_observation_qualified=false及spendable_cash=null，正在核查账户事实与策略等待状态的无效耦合。最新策略自然计算/目标执行尚未完成验收；此前真实模拟成交、撤单证据继续有效。

## 剩余、回退与清理

后继候选`0.1.0a13+resonance122.recovery.1`已从[永久45模块闭包](../../apps/wt_runtime/source_closures/0.1.0a13+resonance122.recovery.1/README.md)普通重建，wheel SHA `6f3526ca26f93a904fae78f004fbec069936d367a14477022d5550aa1251053d`。三项行为为只读中断的Standard分类、执行前置失败的Controller接续、账户约束与行情等待解耦。新017环境保留016的1156个依赖文件原字节，并按原Host精确依赖补齐FastAPI/Starlette/Uvicorn三个wheel；旧016保持，依赖检查通过。该安装实际类资金5项及Controller14项通过。

Standard自有DLL已增量编译，SHA `3f885321859e65fa9324bafbe209a080c81347839e2d227afe66f09a858b2ed1`，复用ef3已编库的事实保留。`StandardReadFailure.h`属于原execution构建声明的`src/TraderQMT`自有目录，正常完整源码收集自动包含。新DLL暂存在独立目录，当前运行007尚未替换；新Python/原生组合需要原Native正常停止后生成绑定新身份的同账transition，再正式采用。此段为候选事实，后继线上结果单独记录。

继续完成只读中断恢复、启动前依赖失败后接续、资金资格修正、最新1.2.2自然计算/后继目标、11月5日全范围收盘数据与既有分钟余缺。当前没有新增用户决策项。新增WT框架行为仍需原审批。

程序和数据分离。旧data-service003、daily-service007/008/009、HPR001及观衡a111/a112的原关闭和配置保留。回退先正常停止当前对应非金融角色，再使用旧受管配置；日线publication/原请求沿原恢复协议核查。金融回退继续原账恢复，版本切换不会撤销已成交。

本轮工作树核查见`WORKTREE-AUDIT.json`，列出的其他树均存在改动或未被主干包含的成果，继续保留。当前运行引用、回退、原金融状态和凭据事件原件保留；失败准备目录及重复依赖仅在核清引用后清理。凭据事件沿[故障原件](../incidents/2026-11-05-source-body-tool-output.md)，当前轮换状态保持原记录。
