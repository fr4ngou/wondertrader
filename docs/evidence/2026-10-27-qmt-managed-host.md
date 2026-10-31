# 观衡统一管理QMT只读Host

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-27（北京时间）。状态：工程实现与受控验证通过，真实QMT常驻、正式发行和完整迁移继续。适用[QSW-R20](../specs/qmt-shm-wt-binding.md#qsw-r20-常驻连接与系统统一启动)。

## 实现与根因

原单连接启动要求操作者在有限窗口内启动QMT策略。新增显式resident-read生命周期组合原Runtime/Agent，v3配对绑定两端配置；观衡管理独立Host进程，持续空闲等待与单业务请求预算分别处理。旧v1/v2默认字节保持，WT核心本轮无新增修改。

独立审查定位并修复：启动事件/ready晚观测越过原D、关闭过程中更早D被旧局部变量覆盖、Runtime构造与Journal清理双异常丢首因及owner、超大JSON整数预算绕过单功能配置降级。成功出口核原最早D，Journal在预留单槽登记；资源未确认保持pending，停止自动建代。

## 实际验证

| 范围 | 结果 | 原始材料 |
|---|---|---|
| Host控制/CLI/构造首因/原pair账户核验/v3配对 | 59/59，3.139秒 | build/qmt-resident-system-validation-001/runs/host-final-59 |
| App进程owner及lifespan/CLI | 36/36，2.505秒 | build/qmt-resident-system-validation-001/runs/app-final-36 |
| 原Agent/Host/等待与真实WinSHM签名HTTP | 52/52，4.968秒，含两项真实内核通信、SDK替身 | build/qmt-resident-system-validation-001/runs/default-winshm-52 |
| 真实国信Python3.6.8完整冻结策略 | 86模块生成；两代无Host重连尝试，正常close；open/io.open/FileIO/socket入口计数均0，SDK调用0 | build/qmt-resident-system-validation-001/runs/target-memory |
| Host-only普通离线安装 | 固定Flit/hash requirements/普通venv/pip check与角色receipt通过；仅Host/Agent，未创建App角色 | build/qmt-resident-system-validation-001/runs/host-install |
| 安装包生成v3与verify | 86模块闭包，策略1,481,399字节，qualified_in_qmt=false | build/qmt-resident-system-validation-001/runs/pair-installed |
| App实际管理独立Host | ready后正常closed；App shutdown_complete=true，Host pending=false/forced=false，父未导入Host包 | build/qmt-resident-system-validation-001/runs/app-separate-host |

以上每项均有实际根子进程句柄、原截止、退出码和Job/EOF/join/资源收尾收据；所列最终案均exit0且未强制终止。测试外层Job限制2GiB，产品App ProcessJob沿原实现，没有新增该内存限制。根工作记录记载App进程实跑采用owner002；003仅先范围校验再isfinite并增加极端整数拒绝，合法25/8秒预算控制路径相同，最终36项覆盖003。独立delta仅核该合法路径的有限复用，没有独立模块时点证明。

前序尝试保持：App首轮路由测试夹具误用_IncludedRouter.path、构造失败测试夹具超时预算非法均已改正；原52项首轮有一条旧断言仍期待未收紧的截止，按显式最早D契约修为严格min(original,deadline)，其原生close期限、幂等和单次close断言全部保留，最终52/52。失败原件位于对应001/002受控目录与验证包default-prior-failure，没有隐藏或删除。

源码与公开收据：验证包（外部历史/待归仓路径：`../../build/qmt-resident-system-validation-001/SOURCES.json`）。Host输入固定到测试安装input-root；App/纯测试通过当前源码路径注入。SOURCES记录封存身份，纯runner没有逐模块运行期来源闭包及全源前后SHA，不能扩授完整发行的模块来源资格。运行程序的断言、Job收据与独立复核分别说明，不把收据当额外的系统级监视。

## 独立审查

配对代码由非作者full审查：pair-full（外部历史/待归仓路径：`../../build/qmt-resident-system-review-001/pair-full/REPORT.md`）。Host关闭/构造责任full及delta：Host revision002（外部历史/待归仓路径：`../../build/qmt-resident-system-review-001/host-draft/revision002/REPORT.md`）。App进程owner full及delta：App revision002（外部历史/待归仓路径：`../../build/qmt-resident-system-review-001/app-full001/revision002/REPORT.md`）。入口/安装角色/应用接线full：entry-full（外部历史/待归仓路径：`../../build/qmt-resident-system-review-001/entry-full/REPORT.md`）；目标内存/独立安装动态有限复核：pair-install-dynamic（外部历史/待归仓路径：`../../build/qmt-resident-system-review-001/pair-install-dynamic/REPORT.md`）。最终结论以各自固定源码范围为准。

## 限制与剩余

本轮未操作QMT界面/策略、未查询真实账户、未真实下单撤单、未生产切换、未配置登录任务。目标解释器探针使用合成Context和无Host情形；Python入口拦截计数不等于QMT平台运行或整个进程系统级文件访问证明。真实QMT只读常驻仍须核新正文装载、认证、新鲜tick、业务请求及实际断连恢复。

此前真实只读来源已取得binding/两tick/POSITION，ORDER为operation_interrupted，DEAL/ACCOUNT未齐；本轮不把此状态更新为恢复。全历史一分钟线、查询优先订单提交空窗防重复、完整交易恢复、保留业务和独立发行仍未完成。旧QMT只作静态参考；旧交易历史不导入，QMT 2021-11-01起历史K线继续。

当前没有需要用户立即决策的阻塞。真实QMT装载/四查询属于下一阶段技术验收；需要新增WT核心修改、生产切换或真实委托时另按既定授权边界处理。

文档检查：scripts/project.py check实际exit0，导航与技能清单完整性通过；原件见验证包runs/doccheck。该检查不授应用构建、运行、UI或发布资格。
