# 固定业务配置的安装CTA入口

类型：隔离开发证据。日期：2026-10-29。状态：NRT-R11首个configured现金ETF profile主链通过，完整模块B为in-progress。关联：[R11规格](../specs/native-realtime-strategy.md#nrt-r11-固定业务配置的受管python入口)、[模块B](../migration/module-b-delivery.md)及[此前原生交易/回测核验](2026-10-29-module-b-native-validation.md)。

## 最终候选与实际运行

`build/ms-configured-001/BUILD-003.json`绑定实际安装的Appa10 wheel，SHA256为`7d96c6686c1f5852c999973987d75d7bc3aba6e9f8e3e6e1474e885a9c6f8f77`。wheel从本轮独占app-source-003构建；公共App及唯一算法源码保持原owner内容。新runtime-venv独立安装22个依赖，实际corea6、NSQa1、SDK0.14、V2a2、signals/variants a3，`uv pip check`通过；完整版本在versions-003.log。该组合记录实际解析的starlette1.10.0，统一候选仍须按集成时固定依赖重新核身份。

父端使用安装中的ManagedPythonExecutionProcess/原ProcessJob；子端仅从固定bootstrap进入安装中的execution_configured，`-I -S -B`、绑定site和私有pycache跳过隐式安装启动代码。解释器exe、base Python运行DLL、venv配置及七包完整源码集合逐项重验，关键实际导入路径/摘要与绑定一致。产品Python子端不导入测试脚本。

原生部分复用`build/ms-business-001/install`的固定GuanhengCtaRuntime、标准Factory、原CTA ticker/Local/MinImpact/Adapter/WinSHM；日线沿已冻结原Helper/Reader装配。新入口只读取`parameters.python_strategy`固定profile及原NSB冻结输入，调用唯一configured核与NSQ.advance。实际WT基础资料同安装SHA复核后复用原NSB现金ETF准入，现金多头模型、100份单位、原沪深两段session及显式费用文件分别核验。新增WT核心修改、金融账本和真实券商调用均为0。

## 主链与异常结果

| 验收 | 实际结果与原件 |
|---|---|
| R11配置→真实业务核→原执行 | business-004：双策略各700，唯一SDK替身净额买1400；来源完整查询返回1400并确认回报。下一次原主m1调度两策略sequence=2、NSQ均converged，原本策略actual/sellable各700、pending为空，原PnL0，派生理论现金42993；共8查询、1次insert、0次cancel，完整正常关闭 |
| R11隐式site代码 | site-probe-001：安装site中受控.pth探针在父Python已经启动后创建；实际子端跳过该文件，标记文件始终不存在，主链与上述相同。探针随原owner清理；该案覆盖最终runner身份 |
| R11模型/配置拒绝 | reject-native-model-002将实际commodity.volscale改为2；reject-profile-002选未知profile；reject-input-sha-002改输入摘要。三案均由实际安装子端在进入原CTA前拒绝，查询/SDK调用0、未发布ready/closed，无forced/pending；原Job、管道及fixture资源完整回收。最终收据的runtime_dll运行标志、下单数量和native_stdout标志分别为false/0/false；001旧收据的计划模式误标已通过002更正，旧原件保留 |
| F2完整投影预检 | boundaries-001以真实安装配置/输入及唯一核/NSQ运行直接回调，设定容量为缺少readback的正文长度加1；含完整double读回字段的投影在任何setter前拒绝，setter数0。此案只证明Python容量准入，不授原生运行资格 |
| F3源码集合拒绝 | 同一boundaries-001在配置绑定后加入额外core源码，实际父准入拒绝，Job尚未创建；探针原样清理 |
| 原入口兼容 | native-baseline-001使用同版安装App的原ManagedExecutionProcess→原exe，A600+B400仅买1000、4查询、正常完整关闭。其余原五组合按上一轮固定制品证据及本轮delta范围复用 |

实际正例RESULT与POSTFLIGHT、完整fixture、configured-business-proof、原stradata/portfolio、控制目录python-binding/ready/closed/strategies均保留在各案目录。两正例业务投影SHA均为`3c80195be7c88a55d932874434460d1ba4e87c9d3393089acf272ac95c8d1243`。business-004的RESULT/POSTFLIGHT分别为`a38df3b989f0e77d4ac090697e1ce0f101940f9857c01d78747758b0fb0878c9`、`69a0d98e6486a1ce069a9a0c4d0683449f584205138787f7ca225a94b8f75634`；site-probe-001分别为`5834c94b4d4ce1c12ae657b4cd9f366c80a97e2a1ecd6f20fa6a69cb91c8ef29`、`880e62c32556006c82888a69422680158615adbd350af85292226eac237d093a`。

## 审查与交接

独立full/delta审查定位并修正：实际原生模型准入缺口、完整readback投影容量、Python实际加载身份。最终报告和源码/安装/原件摘要见`build/ms-configured-001/REVIEW.json`及DELIVERY.json；早期失败/弱模型轮次保持原件，未授最终模型资格。

C可显式使用PythonExecutionProcessConfig.load(native_install, config, control_root)及ManagedPythonExecutionProcess(config)，生命周期接口与原ManagedExecutionProcess相同。CLI为安装Python的`-m guanheng_app.execution_process --python-strategies --installation … --config … --control-root … --seconds …`。每策略参数结构以R11为正文；输入复用原FrozenSessionInput及decode_session，不接动态模块或脚本。`strategies.json`只为当前原值/决策投影，持仓/费用/绩效仍由WT原文件拥有。

本轮只覆盖初始flat、T+0现金ETF、有限冻结合成历史和零费用样本。原公开position的UNKNOWN标志保持，R11观察解释限定本profile；真实账户资金、T+1、非零费用、原生恢复、其他保留策略、当前a6的BT/RT比较、实际来源单位/时间/覆盖及统一发行/页面整合继续待验。未操作QMT界面、执行真实下撤单或发布。原保存接口必要性待验证，事件串行方案保持撤回。
