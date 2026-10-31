# QMT常驻入口真实装载与历史CLI后继

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-27。类型：本轮开发与验证记录。整体active，未生产发布、未真实下单撤单；旧QMT工程只作静态参考。

## 本轮实现与实际装载

沿已验Host-only安装生成显式resident-read只读v3配对，保留原账户、政策和凭证。读能力仅account.trade_detail/market.full_tick。实际终端GH_WT_MEMORY_VERIFY的旧正文已私有备份；新正文已在QMT编辑器打开、保存并逐字核对。编辑器仅转换CRLF并在原pair正文后增加精确两个LF；最后保存SHA74f4bc1604cff343aed66dca580a16cfd9894ca6e36243acba8e5cbb6587f46b。目标3.6.8完整正文的文件/网络入口拦截探针通过，属于单代无Host加载/停止工程验证，SDK调用0。

准备及独立核验见准备复核（外部历史/待归仓路径：`../../build/qmt-resident-live-preparation-review-001/REPORT.md`）和界面记录（外部历史/待归仓路径：`../../build/qmt-resident-live-qualification-001/UI-STOP-AND-SAVE.json`）。前序系统管理的有限动态独审见App动态复核（外部历史/待归仓路径：`../../build/qmt-resident-system-review-001/dynamic-app/REPORT.md`）。本轮开始曾误读历史绿色状态，短暂启动旧只读正文后已停止；该记录保留，与新正文运行验收分别处理。

## 两次真实只读尝试

第一轮自有Host18019就绪，QMT弹出“修改策略后继续运行”确认。sky向主窗口及独立对话框截图输入均报failed to activate captured window，确认未完成，未建立binding、Native未创建、业务请求0。root68888实际exit2/205.882秒；App/Host/外Job树0、EOF/join及资源关闭，无强制终止。结果（外部历史/待归仓路径：`../../build/qmt-resident-live-qualification-001/RUN-001-RESULT.json`）及独立有限复核（外部历史/待归仓路径：`../../build/qmt-resident-live-driver-review-001/dynamic003/REPORT.md`）。

用户随后确认运行，新开第二轮；原超时请求没有续期。新轮实际认证及两次新鲜回调成功，原C++GuanhengAccountScan/TraderQMTReadOnly开始一次扫描。四分组均未交付，报告单项查询截止耗尽（code -6），无transport_error/source_error。原通信Journal在Host关闭后mode=ro检查仅1条POSITION，terminal且ok=true，入队至认领894.091ms，结果execution_ms14。其余ORDER/DEAL/ACCOUNT未开始；来源成功与扫描端未采用分别记录，原因仍待返回链定位。诊断不输出原账户、请求体或金融字段。只读安全时序（外部历史/待归仓路径：`../../build/qmt-resident-account-diagnosis-001/SAFE-002.json`）。

第二轮root38796实际exit2/205.869秒；Native rootexit3且Job树0/双EOF/join/关闭，Host rootexit0且正常closed，App shutdown_complete。原总D内正常回收，没有强杀。用户确认策略已停止时，Host已按原D关闭；后写stop.request未被本轮观察，不能把stop_seen=false改成成功，也不授QMT I/O线程资源证明。结果（外部历史/待归仓路径：`../../build/qmt-resident-live-qualification-001/RUN-002-RESULT.json`）、外层资源（外部历史/待归仓路径：`../../build/qmt-resident-live-qualification-001/RUN-002-OUTER.json`）和停止时序（外部历史/待归仓路径：`../../build/qmt-resident-live-qualification-001/RUN-002-STOP-LATE.json`）。真实委托/撤单0，原18017和其他策略保持。当前GHWT停止由用户确认，独立UI复核仍未成立；只读窗口树另显示GHWT附属编辑器，窗口激活失败的系统原因尚未确定。

补充时点核实：Agent在账户投影结束后生成completed_at，Host按原字节保存。该字段与Host入队差2899.065ms，尚未覆盖SHM回传、Journal提交及HTTP完成；多项结果计时0为协议默认值。原4秒Native任务起点未记录于旧收据，不能据这些数断言成功终态已在该截止前可读。时点投影（外部历史/待归仓路径：`../../build/qmt-resident-account-diagnosis-001/SAFE-003.json`）与反馈loop方案（外部历史/待归仓路径：`../../build/qmt-account-deadline-feedback-plan-001/revision002/REPORT.md`）。

## 工程驱动与历史CLI

只读驱动沿原原生调用块、固定实际安装/源码及隐私捕获，仅换新Host端口和resident生命周期。独审发现结果落盘失败未同步incomplete，已在002统一真实退出接缝修正；5项实际纯故障回归通过，root71536exit0，外Job/EOF/join/资源关闭。静态full与delta（外部历史/待归仓路径：`../../build/qmt-resident-live-driver-review-001/revision002/REPORT.md`）。父同buffer执行范围不等于Host子解释器及第三方/pyc的全部来源证明，正式发行资格保持独立。

历史CLI的显式read_profile_version已在自有两文件实现，缺省/v2保持原路径，v3走既有完整账户加历史profile准入，仅发送历史请求；config原SHA继续绑定resume。产品full（外部历史/待归仓路径：`../../build/qmt-history-cli-profile-review-001/REPORT.md`）无新增必要P1/P2。既有末原子发布/flush后的原D成功复核缺口单列保留，本切片不授其严格故障资格。

固定08b230上游323源的隔离构建001已实际运行，configure14.5秒成功；全依赖逐文件反复检查祖先消耗了主要原预算，编译仅剩13.382秒，在38/95步超时。root61328exit2/235.621秒，原子树已回收；产品未运行，7项CLI回归尚未执行。保留首轮构建收据（外部历史/待归仓路径：`../../build/hc-001/result.json`）。002扫描优化先在真实普通临时文件树误拒跨API的ctime差，原5项中4过1错；最小同触发0.059秒复现，未把该候选用于构建。003将跨API比较限定为size/mtime及双方明确存在的birthtime，同句柄读前后ctime/身份/长度和完整SHA保持。6项实际回归全部通过；同8文件树的Path.lstat包装计数492→93，这个计数不等于总系统调用。工具delta（外部历史/待归仓路径：`../../build/qmt-history-cli-build-review-001/revision003/REPORT.md`）。

最终003以全新hc-002目录在原240秒上限内编译完成，根16408实际exit0/83.705秒；固定上游323源、owned120源、工具/完整离线依赖两轮身份均通过。只编译自有历史CLI，原WT框架、正式CMake及共享native工具保持。最终构建收据（外部历史/待归仓路径：`../../build/hc-002/result.json`），EXE SHA26951df46ec501f8f81d5ff6647b05c87700efa57d425286661cedeb49637199。

随后从同owned冻结快照执行原七项test_cli_profile.py，使用该EXE和显式SHA，7/7、0跳过，3.481秒；实际21个CLI子进程，pending_owners=0，二进制前后SHA相同。根9256实际exit0/3.890秒；外Job/子树、双EOF、join及句柄收尾正常，无强制终止。七项结果（外部历史/待归仓路径：`../../build/hp-001/result.json`）与根进程事实（外部历史/待归仓路径：`../../build/qmt-resident-followup-20261027-001/PROFILE-TEST-ROOT.json`）。全部历史响应为合成数据，未读取真实QMT分钟、未生成真实DSB、未进行全历史导入；已有CLI末出口严格截止缺口继续单列。联合有限动态复核（外部历史/待归仓路径：`../../build/qmt-history-cli-dynamic-review-001/REPORT.md`）已完成，无新增必要P1/P2；固定源、合成读取与真实来源分别授予资格。

## 剩余与决策

下一步以原请求成功/客户端超时反馈构建合成loop并定位C++返回链，避免重复真实SDK请求；再接历史真实小样本、单位/覆盖率及2021-11-01起全历史导入。订单查询空窗的完整方案已研究，首回归及拆单/并发/重启闭包仍待实施，见自有准入设计（外部历史/待归仓路径：`../../build/qmt-order-gap-admission-design-001/REPORT.md`）。完整交易恢复、策略与保留观衡业务、独立发行继续。历史交易记录不导入；通达信、Grafana、新闻及研究保持原范围。

本轮无新增框架修改申请或实盘测试决策。用户已完成本轮运行确认和停止协助，当前无需重复操作。窗口激活、扫描端超时、构建工具性能属于待解决技术问题。整体目标保持active。

文档检查：按规定命令python -B scripts/project.py check通过，root72632实际exit0/3.453秒，外Job正常关闭。此前额外加入-I导致脚本同目录project_support无法导入，失败保留于doc-check-001；改回规定调用后通过，未修改项目工具。该检查只授文档导航与技能清单一致性。
