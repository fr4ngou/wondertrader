# 2026-10-26 回测归档失败、页面重试与新进程读取

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：当前制品实际通过，独立动态复核通过。关联 [NBW-R6](../specs/native-backtest-workspace.md#nbw-r6-已完成回测只读归档)。本轮产品源码修改为0；新增可保留的专项验收入口。

## 输入身份与执行边界

后端沿实际普通安装 App、策略核与固定 WtBtPorter DLL，使用合成行情和隔离回测配置。新页面从当前Console源码构建：136份源码/配置前后SHA相同，Vite构建及现有分块检查分别实际exit0。新dist的10项树固定在运行计划（外部历史/待归仓路径：`../../build/qmt-backtest-archive-retry-plan-002/INPUTS.json`），SHA 04cd87dd2dbfef853d86629f3793936a95827dfcf23b19d14fdcbc7703ce293a；输入（外部历史/待归仓路径：`../../build/qmt-backtest-archive-retry-inputs-002/INPUTS.json`）SHA 6d99f45bedd12f4b8e9c41ff9c004e8a7ca0ab7b23e3503aa7d47a1b781862d2。

Node、Edge和Playwright1.62.1使用本机已有安装，未下载依赖。Browser插件/技能未提供，按前端验证技能使用现有Playwright。七张截图及原浏览器结果保留于 C:/Users/frangou/.codex/visualizations/2026/10/26/01a1595c-b0b9-7e83-b363-f98b292c15da/archive-retry-003/results-001；各图SHA见根原件复核（外部历史/待归仓路径：`../../build/qmt-archive-retry-continuation-001/FRESH-RUN-ROOT-VERIFIED.json`）。

## 真实失败与恢复调用链

| 步骤 | 实际观察 | 结论 |
|---|---|---|
| 原生回测正常完成后，在新实验目录创建本fixture空目录占据receipt文件名 | 原Native exit0、已回收/双管道完成；真实publish进入_Read.raw:83，因目标为目录抛ArchiveError，发生在原30秒请求D内 | 执行completed与归档unknown分别保留，失败来自实际文件类型拒绝 |
| 核明dev/ino/空目录/确切父路径后，将本次空目录移动到同fixture obstructions/<runid>.held | 操作前后收据保留，held不删除；移开后归档仍unknown | 未自动重试，未移动用户数据或递归清理 |
| 实际页面点击一次“重试完成报告归档” | 一个POST/200；同request/run转available；首App总POST2（首次运行1+重试1），Host构造/运行各1，publish2/失败1 | 归档重试没有再次执行回测 |
| 关闭首浏览器及App，再启动新App/新浏览器 | 新owner/PID；仅GET及读取页面历史；Host/Native/publish/POST均0 | 跨进程读取同一份已归档实验 |
| 核配置与报告 | 五条逐日HTTP记录及详情完全相同；配置、receipt/report SHA相同；页面抽查首个合格日的模型净值/现金/八项持仓等于原报告 | 记录内容及来源身份保持 |
| 桌面1440和窄屏390 | 六次health逐项合格，document/body宽分别为1440或390；无console warning/error、pageerror、错误overlay或替换字符；七张截图SHA复核 | 当前页面包完整两阶段通过 |

实际run_id为88905fc2585845e9902f6e52f7b3ebea，报告SHA f02eb2e1064f78c1b62cd86ddc8b00ffc2b05954e1dfb828293d77b8c30e4e54，receipt SHA 23fd17b2b0391e9b769fde25582514f980b9ab73266da7fb97676c2bb75cefdd。39项实际原生文件树与记录一致，变化仅为fixture目录移开、真实完成receipt加入，报告和配置原件未改。

根保留的两外层ChildProcess为47608和55064，分别实际exit0，均在同一根240秒D内（36.470秒、从同一起点计36.056秒），guard未触发。控制器child exit0、无console、创建期Job归属、首双pipe各64KiB、2GiB Job、tree0、双EOF、reader join及资源关闭均实际确认；两阶段browser/context关闭后才写对应握手。成功须联合实际退出码、原D及收尾原件，不能单取passed JSON。

## 首次失败与工具修订保留

首轮FAILED（外部历史/待归仓路径：`../../build/qmt-archive-retry-continuation-001/FIRST-RUN-FAILED.json`）使用原spa-release，页面归档已恢复后在390px复合health门失败，第二App尚未进入。原包CSS缺当前源码已有的minmax(0,1fr)单列约束；该轮没有保存细分flags/尺寸，具体失败布尔项和越界节点仍未知。原结果和四张截图保留，不能据后继通过改称首轮成功。新包实际包含现有约束，原严格断言保持，仅增加有限health取证；没有为测试改产品CSS。

首轮浏览器外层Node句柄因块内变量未跨REPL保留，未授该外层实际退出资格；其子controller已证child1/tree0/EOF/join/closed，后端原句柄实际exit2。后继把每个ChildProcess及事实同时保存在顶层注册表，实际新运行两句柄均完整观察。未因观察超时或引用缺口重启。

脚本静审另关闭两项P2：业务fatal不再阻止终态失败证据写入；最后emit后及exit前复核原rootD。两者只改验收工具，原业务断言保持。静态full/delta与新输入联合审查见007（外部历史/待归仓路径：`../../build/qmt-backtest-archive-retry-independent-001/current-spa007/REPORT.md`）。

## 维护入口与证明范围

后端专项入口（外部历史/待归仓路径：`../../tests/integration/backtest_workspace/test_archive_retry_runtime.py`）SHA 6e9bac0afda479edadb0c0600be516be7af139ea421624413b3b48d901630670，真实浏览器入口（外部历史/待归仓路径：`../../tests/integration/backtest_workspace/archive_retry_browser.mjs`）SHA 3cf6ebdba224774cdd826dcf660e5288ce4cb846f1add750271a5347fb4e132b，均与实际执行原件逐字节相同。它们是显式固定安装/工具/输入的专项场景，不由pytest自动启动，也不代表通用CI环境无需准备即可运行；具体编排沿[测试手册](../runbooks/testing.md)。

本次授configured策略族这一真实文件失败→页面唯一重试→正常新进程读取链，继续复用WT原生回测与原实验文件；不增加数据库或持仓账本。不授断电持久性、V2全部异常矩阵、真实QMT行情/交易、全部保留策略、连续实盘或最终发行。真实SDK/下撤单0，旧QMT执行/修改0，生产未切。

## 独立动态复核

动态008（外部历史/待归仓路径：`../../build/qmt-backtest-archive-retry-independent-001/dynamic008/REPORT.md`）SHA 23a72e55cc7c8eb0db87876e7f5a995078f7755ce8da2c63824c26059442d012，28项交叉检查通过，无新增P1/P2。独立重算136份Console源码、1223份实际安装文件、15项关键身份及39项原生树；65份审查原件经根逐份重哈希，与当前文件一致。当前版本测试目录的两个脚本与实际运行原件同字节；此复制不改变运行算法。实际顶层进程句柄事实来自根保留对象和共同原D收据，不由Reviewer重新持有。原压缩payload未另行独立解压；规范化报告SHA、真实HTTP/DOM比较及原件不变的证明范围保持。见65份根复核（外部历史/待归仓路径：`../../build/qmt-archive-retry-continuation-001/INDEPENDENT-DYNAMIC-ROOT-VERIFIED.json`）。
