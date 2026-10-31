# 原生回测绩效与比较验证

类型：开发验证记录。状态：done（BPC切片，2026-10-29收束）；模块C整体in-progress，未发布。

## 根因与实现

原已完成归档具备逐日观察和完整原件核验，操作员缺少汇总绩效及两份报告对照入口。沿[BPC规格](../specs/backtest-performance-comparison.md)复用BacktestArchive、唯一ValidatedSessionReport/project_session_record及App原有backtest_reader，单次绝对截止内核验并读取；原生资金事实继续由WT提供，读取不重跑回测。

收益以末个合格模型净值和显式初始本金计算，最大回撤仅覆盖初始本金及已观察日末峰值；费用取末个原生累计值。缺失观察保留null，精确金额保留字符串。V1/V2报告、策略/算法、配置、来源与文件/规范会话摘要分别显示。两份条件差异明确列出，刷新/错误隐藏整对旧结果，日期表分页且曲线断开未知点。策略目录保持用户要求的名称、简介和版本。

## 已取得证据

候选目录为`build/backtest-performance-001`。Python3.12.14、新安装Appa9及21包闭包；SDK0.14和最终纯包002身份沿dependency-artifacts.json。生产SPA通过已有Playwright/Edge检查，Browser plugin not available。仅GET，无新增回测、真实账户读取或交易操作。

实际输入为旧configured、旧V2及新profile V2三份原生完成归档；验证先逐字节复制至专用根，原件SHA前后不变。HTTP所得每个日期/净值、收益/日末回撤/末累计费用，与原报告压缩payload直接独立复算一致。V2样本120987.31元→124587.31元，收益2.975518672164874%，回撤0、原生费用0；该样本属于隔离合成回放。

生产SPA验过单份→选择第二份→条件差异→日期表→切回单份；1440×1000与390×844，窄屏横向溢出0。比较GET注入503时两份指标全部隐藏，手动重读恢复；意外运行错误0。已核截图，路径为本日visualizations的`backtest-performance-001/{desktop,mobile,failure}.png`。App关闭、读池线程0、HTTP线程join、监听关闭及外层Job/EOF/join均通过。原生输出副本篡改后比较拒绝，恢复原字节后同身份再次成功。

原件：`http.json`、`browser.json`、`NATIVE-ARCHIVES.json`、`native-result.json`；126项后端及31项前端回归、TypeScript、生产构建、分块检查及project.py check均通过，边界数学及归档原回归另见`build/backtest-performance-delivery-001/files.json`。

## 最终身份与独立审查

Appa9 wheel SHA256为`ab579059dad225645007a7ea80c2e075adb2df5e424a1e1ad15b12e1f10cf7cb`；50个构建输入与当前源码一致，48个安装运行文件逐字节一致，见installation-identity.json。13文件生产SPA从本轮实际浏览器所读manifest和资源原字节封装，独立ZIP SHA256为`fc58c10c5bf75d3194949f7b025c21f9e8d7bfd71ff14984c5bffa80d659f5bb`；ZIP成员逐项回读匹配，未打入前轮遗留分块。制品身份、检查入口及精确源码交接见本轮DELIVERY.json和files.json。

两名独立审查者分别按最终规格与规范进行full，BPC-R1至R4全部complete，无未解决P级问题。20文件清单SHA256为`91fa5867e5d396b83603baef6f95670a0c6c67c9028ba6403f6f1ffb350d3a80`，两者均核对当前源码/副本/安装及实际行为原件。最后Path身份前置准入及曲线范围说明已进入该清单，最终同安装主链9.29秒exit0、外层Job/EOF/join通过。浏览器唯一503为主动故障注入，意外错误0。

## 验证限制

本轮不重跑历史原生策略，不把隔离合成输入提升为真实来源。真实保留策略的完整历史→BT→RT→隔离交易→页面主链、B正式业务桥/金融投影、独立市场观察、全策略与整体升级回滚继续原目标；本切片未发布，旧QMT保持只读。
