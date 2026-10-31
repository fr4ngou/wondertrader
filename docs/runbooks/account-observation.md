# 账户只读观察运行手册

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：操作手册。状态：独立只读接入实施及验收中。适用范围：WT发布的账户业务观察、观衡读取及原生独立扫描工具。当前装配以[COP](../specs/guanheng-operator-platform.md#独立wt状态消费)、[WRI](../specs/independent-wt-runtime.md)和[NRT-R20](../specs/native-realtime-strategy.md#nrt-r20-独立运行结果的只读定位交接)为准。

## 安装与读取连接

WT运行环境与观衡App/SPA分别安装。WT拥有原生执行、券商查询及业务结果发布，观衡拥有HTTP读池和个人展示偏好。WT运行环境使用其发行中已固定的依赖；完整执行使用B声明的六发行闭包，基础两发行数据运行包仅授其数据范围。安装、实际发布、正常关闭与生产资格分别核实。

安装人员为观衡配置下列四项只读身份：GUANHENG_WT_STATUS_FILE、GUANHENG_WT_CONTROL_ID、GUANHENG_WT_INSTANCE_ID、GUANHENG_WT_CONFIGURATION_SHA256。字段与单次读取语义见COP；status文件由WT原子发布。`GUANHENG_ACCOUNT_SOURCE=wt_account_publication`显式读取account_observation的[NAP-v1](../migration/native-account-publication-proposal.md#nap-v1冻结合同)完整四组；默认wt_strategy继续从执行组件公开定位读取R20的P/资金子集。来源选择只影响账户接口，策略运行结果始终读取原R20。读取参数不包含运行descriptor、金融状态写目录或执行凭据。行情连接继续使用独立SDK地址及其读取认证，秘密留在受控环境。

旧GUANHENG_ACCOUNT_SCAN_EXECUTABLE/CONFIG只保留为历史环境项；当前应用使用上述读取配置，继承旧值时其他只读工作区照常启动。App入口只创建自有读池及个人自选owner。以下静态路径为占位示例：

```powershell
python -m guanheng_app --port 18120 --static-directory <已安装SPA的绝对路径>
```

先核/health与/v1/ui/capabilities，再访问/account、/orders、/dashboard或GET /v1/ui/account/overview。capability表示读取连接已配置，实际取得哪些组以响应为准；WT状态文件存在和当前进程存活分别核实。账户/策略业务读取共用原App有界读池及单次2秒绝对截止，额外参数或正文422、身份/缺文件/原截止失败503；读取动作不发起原生扫描或新券商查询。

## 页面解释与恢复

NAP来源返回DTO4，复用原validator/projector和DTO2四组字段，保留原查询起止、掩码账户及实际环境。页面说明等待首轮、更新中、成功、失败保留旧值和停止；最近发布时间与最后成功时间分别显示，成功空批立即清除旧行。WT根/发布owner或来源身份变化会清除跨来源回退。临时原子换名或共享冲突沿原2秒截止等待；格式和身份错误返回固定503。完整成功需要原completion、exit0和六项资源证明，页面刷新保持Host/Scan和券商查询新增0。普通WT/App安装与SDK替身浏览器整链见[本轮证据](../evidence/2026-10-30-native-account-publication-ui.md)，真实QMT和生产资格单列。

默认R20来源返回DTO3，从原broker_observation读取P/资金；原P/A各自的接收时间、修订和副本发布时间保留。账号及环境尚未提供时保持未知。原查询起止、请求ID和结果摘要保持null，接收时间按其实际含义显示。DTO1/2原扫描资格保留为历史/独立工具范围。

- 已知持仓和资金分别显示，委托/成交明细未发布时各自标缺失。已知空仓是完整空观察，资金零值按原值显示；未知金额保持未知。
- “刷新账户”重读WT已发布副本，各类数据时间按来源标注；本次读取时间与原数据时点分别拥有。刷新失败保留同观察作用域的成功值及原时间，作用域变化后清除原组回退。
- WT原发布明确提示持仓过期时，页面显示过期说明并保留旧持仓/原接收时间；观衡沿生产者判定，不自设交易时效阈值。WT停止或失败后，最后完整结果带原时间和运行状态提示。
- 可卖与总持仓分别复制券商事实。成本、均价、冻结、成交归属和交易日等未提供项保持未知，数量差额不作为其他账户事实。
- 账户与策略展示分开。原broker_position_qualified=false属于交易资格，已知P/资金仍可只读展示；委托、撤单和执行权限归WT入口及授权边界。

业务文件缺失、身份变化或格式无效时先核WT公开发布和原实例，再重新读取。页面不接管执行owner或修改金融文件。真实B v2发布/六发行组合、完整股票关闭与实际账户资格沿B原证据分别验收；C文件fixture通过和行情真实组合不替代这些结果。

## 验证、关闭与升级

观衡正常关闭只停止Web准入及自有读取线程，WT、Host、采集及策略保持原实例。异常退出和升级回退也按此边界验收，记录实际PID/控制身份、来源连接和采集/策略推进，按[验证规范](../development/verification.md)保存原件。已验范围见[独立只读观衡](../evidence/2026-10-30-independent-observer.md)。完整安装/生产切换沿[发布规范](release.md)。

当前API/分组/身份/失败恢复回归在tests/integration/wt_observer，普通安装HTTP/浏览器与运行连续性在本轮冻结QA；固定制品、实际命令、版本、源码和结果绑定后再交付。历史App托管扫描的证据按原候选保留，退出当前Web装配。

## 原生独立扫描工具及历史资格

GuanhengAccountScan.exe、TraderQMTReadOnly.dll及原binding仍属于独立原生只读工具能力，采用[NAC](../specs/native-account-console.md)和[模块说明](../modules/account-observation.md)的schema/预算/装载约束，由WT侧或明确独立工具owner运行。QMT连接按[国信操作手册](guosen-qmt-operations.md)及[共享内存说明](../../connectors/qmt_shm/README.md)核验。binding仅保存凭据环境变量名，原始秘密留运行环境。

原schema2/inspection3/IPC2、父单次总预算和原body摘要、原生查询/关闭协议保持；当前观衡不装配ManagedAccountScan。schema1/HTTP旧profile的历史范围及退役边界沿NAC/原证据。独立原生测试按[ATI](../specs/native-account-test-runtime.md)和测试契约（外部历史/待归仓路径：`../../tests/integration/qmt_shm_account/scan/RUNNER-SPEC.md`），已验证的[旧App组合](../evidence/2026-10-29-account-installed-app.md)保留当时输入，不提升为新只读装配资格。完整四查询/终端恢复、原生45场景及新独立安装继续按原规格验收。
