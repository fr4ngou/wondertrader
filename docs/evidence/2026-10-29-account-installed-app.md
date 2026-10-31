# 账户、交易记录及总览的独立安装主链

类型：开发验证记录。状态：done（本轮合成账户安装组合）。范围：NAC/QAR公开账户展示及ATI适用双角色安装；模块C整体in-progress，未发布。

## 根因与正确装配

原真实账户证据已覆盖[源码App公开ASGI入口](2026-10-28-qmt-account-public-main.md)，原记录确认该轮只读探针随后停止；本轮尚未取得新的真实来源运行证明。当前缺少同类组件在新安装App、真实TCP和生产SPA的组合证据。App和Host依赖不同精确pydantic版本，双角色普通安装解决其装配冲突。本轮复用唯一account_runtime_install.prepare、runtime_identity的原admit/check_current和account_scan_artifact.record_validation_sources，没有改锁、拼装site或修改产品算法。

两角色分别从完整hash锁及wheelhouse离线安装，经标准pip check及所属解释器`-I -B`实测。App为21发行、pydantic2.13.4；Host为15发行、Hosta4/Agenta3及pydantic2.12.5。原始下载缺少pydantic-core2.46.4的首轮保留；从Appa9原uv.lock确切URL取得14份原wheel，逐项核原hash及METADATA后，唯一安装owner在fresh installation-002完成。依赖版本保持原声明。

独立安装HostFixture运行原Host/Agent、真实共享内存和原线程三参数合成SDK；App沿原AccountScanOwner/ManagedAccountScan调用普通GuanhengAccountScan.exe、原TraderAdapter/TraderQMTReadOnly、IPC2和公开DTO2.0。产品源码、插件和原QAR测试源码均保持原件。C测试控制HTTP使用独立回环端口，只负责测试轮次启停，产品端点不接该控制；产品浏览器请求全部GET。

原HostFixture每轮最多四个SDK查询。每次刷新前正常关闭上一代Host，再以同端口、同明确合成账户启动下一代；原fixture计数、准入及关闭算法全部保留。父端原60秒总截止不重置，原ManagedTranscript拥有Host Job、管道和readers；App管理自己的原生AccountScan树。此组合不更改45项runner登记或声称完整QAR矩阵通过。

## 固定输入与实际结果

工作根为`build/account-app-001`，runtime-paths.json只指向已通过双角色收据的installation-002；fixture-paths.json绑定原owner生成的validation/test-sources.json及由唯一App thread_owner.py派生的QA helper。安装、重建私包及逐文件身份见installation.json/approved-inputs.json；私包按冻结源重建，其ZIP SHA与旧wheel分别登记，本轮不沿旧纯包SHA授予回测profile资格。

普通EXE SHA256为`12946b1167dab339b597b69d507dd5448e0aa1b4fbe70889818ed6af6f91960c`，普通插件为`1b63d667f132a9b1418733af955f1eadc0b47b370601ca85512fbd04d2333f81`。仅向专用native目录逐字节复制这两份原件，原件保持；基础资料沿原fixture_values.base_data。13文件生产SPA复用BPC已验原字节，未改变页面源码。

`latest-main.json`绑定`main-4e6d7d9f`，原始RESULT.json/browser.json和main-result.json记录54.313秒、exit0及外层root/tree/EOF/join完成。实际HTTP七轮如下，条数按持仓/委托/成交/资金排列：

| 轮次 | 实际结果 | 原SDK调用与页面 |
|---|---|---|
| normal | complete，2/1/1/1 | 原线程四查询；账户700总量/420可卖、委托00000017、成交00000031与100000元资产逐项核对 |
| empty | complete，0/0/0/1 | 四查询完整空；页面清楚说明0条，资金事实仍保留 |
| partial | partial，2/0/0/0 | position及失败order共两调用；委托未取得批次保持不可用，未冒充空记录 |
| offline | unavailable，0/0/0/0 | Host已停止，页面隐藏原观察 |
| recovery | complete，2/1/1/1 | 同一App显式刷新，新Host绑定和新scan_id恢复 |
| orders | complete，2/1/1/1 | 交易记录页委托/成交切换，仅消费本轮内存观察，未显示资金卡 |
| overview | complete，2/1/1/1 | 总览显示同类账户资金与持仓；策略金融投影仍沿原未接通说明 |

每个完整批的Host实例、运输代际、路由与能力摘要，均与原Host独立capture原件逐字段一致；账户掩码、模拟来源与券商登录未知语义保持。七个scan_id不同，六代Host全部原线程且SDK调用分别4/4/2/4/4/4。桌面1440×1000及390×844通过身份/非空/无覆盖、交互及横向溢出检查，控制台错误0。截图位于本次visualizations的account-app-001目录，已查看账户和手机交易记录截图。Browser plugin not available，使用现有Playwright/Edge。

App shutdown_complete=true，账户受管owner pending=false，全部读取线程0；HTTP及测试控制线程join、监听关闭。六代Host均exit0、root/tree回收、双EOF及reader真实join；原控制marker不替代这些事实。真实QMT操作、真实下撤单均为0。

## 验证范围和后继

本轮不修改产品代码，原已验Appa9、账户准入/映射与生命周期单元证据按原输入复用；新增证据为双角色完整安装及上述实际native/IPC/HTTP/SPA组合。

两名独立审查者分别完成规格和规范的full integration，本轮组合complete，无P级发现。14项审查输入清单SHA256为`9945f0dd8dca9ab1726d2eace000b11fd0f7837256ac1a36d832f30d688abf44`，两者核完整实际运行及安装原件；App1245文件/21wheel、Host577文件/15wheel均无漂移。7份重建App私包的每个ZIP成员（包括METADATA/RECORD）与原批准wheel逐字节相同，容器SHA分别保留。

原安装owner的installation.json SHA256为`69816582a0c413a5ff0e6bd7a07fa78bb416a59a581414d41d9452e1219ad2a1`；App收据`59d979fd875b05887c79c9ebd5af93ab38a9eaecc705d39a011c26935f82dc6c`，Host收据`23a697da550bd6c52c5a676f2fbd6382cb53ae2133bc520d80f3aff934589362`。普通Appa9 wheel在本轮重建后的SHA为`70c899695e078c09b5b482ad5ed534a6e773f4bf93d72b3ce2ea8b929f831e33`；原BPC wheel及其资格保持原摘要。完整制品/源码/运行证据与限制沿`build/account-app-001/DELIVERY.json`交A唯一集成，未暂存、提交或发布。

本轮SDK是合成来源。真实账户新安装TCP/浏览器验收、完整QAR45、正式策略金融投影、真实历史→BT→RT→隔离下撤单→页面主链，以及完整模块C和生产资格继续单列；本轮通过不替代这些要求。原记录确认该轮真实探针已停止，本轮没有新的真实来源运行证明；C未操作QMT界面或恢复探针，后继按A/B实际来源候选继续。
