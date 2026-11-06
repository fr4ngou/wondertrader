# 最新目标接续：观衡已发布，WT采用受阻

状态：部分完成。授权：用户要求合入并发布本轮代码。观衡独立发布成功；WT新包已安装，原生交易恢复未成功，策略当前没有运行。

## 已交付与实际入口

- 主干提交`2cc17df91de9f03cd3db64f7988fbc50ba9b663a`：移除阶段配额、统一已结清阶段的新目标接续、报告数量模型与旧报告兼容。
- `5a2cc755c95f2ee0fb6a256515b7bfc15093a7e7`：分析组件的Runtime精确依赖接线。
- `89cf0068e790716e26dcddf8c699c4fd07b8bbfc`：显式同业务transition支持NSQ实现升级，普通比较及单独角色换代保持严格；独立delta审查及4项回归通过。
- 观衡`0.1.0a119+targethandoff.1`已在原18143端口运行，Web10160，启动器64536；标签`deploy/observer-a119-targethandoff-20261106`。
- 新回测`2f7cd88fd807432b8d817ae40faa74a4`加入原正式报告目录，旧报告文件保持。实际Edge验收曲线、买卖标记、298笔交易明细与旧报告对比通过，无页面错误或失败业务响应。

[打开新回测](http://127.0.0.1:18143/backtests?strategy=resonance-regime-v1%401.2.2&run=2f7cd88fd807432b8d817ae40faa74a4)。404日回测收益28.16855%、日末观察最大回撤20.90451%，冻结模型费用110680元；历史研究模型资格及数据边界沿[原证据](../evidence/2026-11-06-quantity-target-handoff.md)，不作为真实账户收益。

观衡ZIP SHA256：`706b0e5e30b288e6768588da5052afe018428ec9590c00786e5d5efb1c766a0a`，manifest：`bcdd632dbf096405cd91c4a26ec085b8236c37fdf2fde078c41ec8ba9f444209`。

## WT安装与实际阻塞

Runtime`0.1.0a17+targethandoff.2`、NSQ`0.1.0a2`、AWP`0.1.0a14+targethandoff.2`已安装到`runtime-service-20261106-023`，标签`deploy/wt-targethandoff-20261106-r3`；pip check通过，1292份其他依赖文件逐字节保持。与完整404日候选相比，Runtime仅增加版本及execution_recovery发行身份接线，数量数学不变；实际前后105成员绑定预检通过。Runtime wheel SHA256：`4d2888b48c0c899d8d0a4f505683692bcd4b6b5b6ceb771915b7f678385e7f14`。

停止旧WT时，自有宿主停在`recovery_drain`并超时退出。原进程及子进程退出后，沿已有record_execution_process_loss记录真实故障，保留缺少正常关闭证明的事实。旧Runtime恢复父进程曾ready，实际Native随后在`reconcile_orders`失败，不能把父进程ready表述为策略恢复。

原完整查询和QMT界面均有两笔自有已报单：588000、588030各1000份。SDK撤单仅确认signal_sent/sdk_returned，完整后继查询仍为status50、未成交；界面另确认一次撤单后也未观察到终态。自有恢复流程要求先撤清活动单，当前条件未满足。市场已收盘，但尚未单独证明券商不回终态的具体原因，记录为撤单终态未取得。

金融WT当前faulted、原生策略未运行；新Runtime23尚未实际采用。DEPLOYMENT已据实更新ready=false及待采用安装，原五个独立数据/报价/资料服务继续ready。原financial-state-008、100万元基准、持仓、原现金依据、订单、通信journal及两笔原身份保留；不重置金融文件，不伪造关闭/成交/撤单证明。本轮WT框架源码及DLL改动0。

## 下一步与恢复边界

先由完整券商查询取得这两笔原委托的真实终态，再沿原同账transition采用Runtime23，核Native ready、当前持仓资金、未决身份、策略状态、日志及18143页面。结果未明时保持原命令，不重复买入。完整主线发布仍待这一步。

直接保留已知挂单恢复需要补齐自有接线：当前configured恢复会重置NSQ计划，NSQ pending仅取CTA信号，旧角色替换配置仍要求相关证券无挂单；因此不能只跳过撤空判断。本轮未实施该扩展，也未改WT核心来绕过当前条件。

原件：`E:/workspace/wondertrader-qa/quantity-target-release-20261106-001`及`...-002`，包含构建/安装、正式归档、浏览器截图与结果、退出失败、原进程丢失记录、前后身份预检及RELEASE-STATUS。发布与回滚资格分开：观衡旧a118安装保留；WT原账未回档，旧Runtime21完整运行同样受当前挂单核查影响。
