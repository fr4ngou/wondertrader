# WT账户发布到观衡中文页面

状态：最终普通安装的SDK替身来源主路径已通过；双轴审查及文档补验已完成。真实QMT、完整系统和生产发布分别待验。

## 根因与实现

旧账户页读取R20策略发布中的持仓/资金子集，缺少独立四查询结果定位。按[NAP-v1](../migration/native-account-publication-proposal.md#nap-v1冻结合同)及[NAC-R9](../specs/native-account-console.md#nac-r9-wt持续发布的账户来源)，WT持有Host/Scan和周期查询，观衡只读根status、六字段locator、ready及完整原帧；原validate_observation/project_account保持金融规则唯一实现。

`GUANHENG_ACCOUNT_SOURCE`显式选择默认wt_strategy或wt_account_publication；策略运行接口始终读取原R20。DTO4保持DTO2的原字段、掩码、环境和逐批查询时点，另给发布阶段、最近发布时间及最后成功时间。成功需要四组资格、原completion、exit0和六项资源证明。身份/格式错误固定503；原子替换pending只沿原2秒截止重读。页面成功空批替换旧行，刷新失败保留同来源成功结果及原时间，发布owner/来源或DTO换代清除跨来源回退。

## 普通安装主链

原件根`build/native-account-page-001`。QA冻结根已通过的正式WT CLI组装，使用`build/wt-account-publication-composition-001/installation001`的独立Host及a3 WT六发行环境；WT环境无App/Web。原生Scan/Trader/Adapter、通信Host和SHM均实际运行，SDK查询由明确合成数据提供。C消费使用普通App a42安装与生产SPA；QA没有产品factory替换、安装覆盖或.pth修改。

`main-001/RESULT.json`通过：两轮每轮2持仓/1委托/1成交/1资金，逐轮核50来源事实及6个浮点位值；可用资金82000→82100。HTTP各组与原投影完整相等。观衡正常退出、重启时同WT/Host PID保持，五次HTTP及浏览器读取的额外来源查询0。一次委托SDK失败使发布degraded，旧scan_id、资金、各批查询时间及last_success_at保持；成功恢复返回三类完整空批后，HTTP与实际IAB均清除旧行。WT正常停止后，HTTP/页面显示stopped、closed及原成功时点。

IAB实际操作覆盖账户四组、总览独立策略区域、两轮更新、失败保留、空恢复及停止。截图未另存本地文件，实际工具记录与结构化页面验收单独保留；不把HTTP断言当作浏览器证据。合成来源每批时间/掩码在页面可见，内部运输标识保持DTO语义。

WT CLI exit0，原Job整树、stdout/stderr EOF、reader join和句柄关闭分别成立；两代App原CLI正常退出，原native.run外层关闭成立，SDK来源agent正常关闭。首轮共14个SDK只读查询，真实下单/撤单0，1357固定输入前后相等。原件为RESULT、APP-RESTART、WEB-CLOSURE及各HTTP JSON。

## 当前候选与验证

最终普通29发行App安装`install-004/installation.json` SHA256 `4c465fe52117cb2641d676e45c2505f00a8a1c11150ee230b6d1fc040ea5be33`；源输入由PREPARED-004绑定，pip check通过。生产SPA003共18文件，类型、构建和分块检查通过。最终115项后端通过，新增NAP/R20并存1案通过，见pytest-005.xml及pytest-coexist006.xml；139项前端与类型/构建沿未变前端输入复用tests-003.log。边界覆盖完成证明类型/资格、身份冲突和读取中换代、首轮等待/未配置、pending原D、重复/深层/非有限JSON、超限与硬链接，以及来源/DTO变化清缓存。原native账户纯单轮测试继续保留，三个HTTP测试已按已确认的App只读边界更新。

最终`main-004`同App004/SPA003的正式WT CLI→原Scan/SHM→HTTP→实际IAB整链通过。两数值帧82000→82100、50事实/6浮点位保持；失败保旧、完整空清行、两代App重启同WT/Host及短读取/重启窗口新增查询0、WT正常关闭后stopped/closed保原时间均成立。WT自主周期使总SDK查询18；1357输入前后相同，exit0及树/EOF/join/句柄正常。实际浏览器结构验收记录为BROWSER-WITNESS-004.json，明确人工记录CUA断言及工具返回文字，未保存像素。`main-002`把分批时点误作同步快照、`main-003`把浏览器停留期间WT自主周期误计为App副作用，两次QA失败及原脚本均保留；v2在新完整帧后的短窗口核HTTP/App因果，浏览器等待允许WT独立更新，空恢复等待后续完整空帧。产品逻辑和原总D保持。旧schema1单轮1秒测试在并行安装期间两案超时，未改预算，独立静默复跑115全过；精确负载触发仍保留原失败。

## 范围与下一动作

本轮读取原生SDK替身的完整发布，不授真实QMT页面或生产资格；真实来源统一由根协调。当前18126市场观察预览、现场数据WT及QMT运行保持。C改动只包含只读消费者、DTO/页面、账户组件中文标签及相关测试/正文；A公共WT注册/安装与B发布owner按其各自固定输入复用。完整系统、统一安装升级回退与真实来源继续各自验收。

## 最终审查

full固定86件，两轴共识的后根类型P3及规格轴的阶段/时间P3均已在统一准入层修正。delta固定71件，两个原P3关闭、无新增代码P级项；规范报告REVIEW-STANDARDS-002.md、规格报告REVIEW-SPEC-002.md。delta读取的证据副本仍标旧候选，规格轴新增文档P3；当前正文已同步App004/main004，并将限定原件与最终资格分别保留，文档固定包review-003四件已通过规格补审，文档P3关闭，报告为REVIEW-SPEC-003.md。源码148项与安装payload一致，前端六输入与SPA原件保持。
