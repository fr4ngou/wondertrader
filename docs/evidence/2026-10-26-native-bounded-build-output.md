# 原生构建工具第一层输出与截止验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。状态：自有工具已集成，58项适用回归实际通过并完成独立动态窄复核；主批启动器身份范围保留。本记录不授QMT交易恢复或完整发行资格。

## 根因与实现

原native.run用communicate先收集完整输出，外层只保留尾部无法限制该管道内存；原超时另加15秒等待，Job部分构造异常缺统一清理。新实现直接在第一层binary合流管道按8192字节读取，raw默认8MiB、显式最大64MiB，超额失败。成功保完整UTF8替换和换行语义；raw预算与日志编码大小、进程RSS分别解释。

run入口固定原总截止，预留min(5秒, timeout/5)收尾；成功前核工作截止，wait/join消费同一剩余。首异常保留，次异常有限。Job取得handle后的初始化统一清理，构造失败且关闭未确认时把真实owner沿原异常保留，最终状态明确未关闭；未join的reader保留借用。

正式native.py SHA3fc7175f7499b1b67ac48ab866b36f4b506e8c7af27984eb9a22d8b6492b2442；process_job.py SHAa6236e03ac1b284ac02e03df796cd9e74601d59b3d80430f6137c932344526f5。新增两份回归共28方法；原test_execution仅日志超时兼容例调整为2秒，真实50ms负向另保留。显示与窗口创建规则保持。

## 实际验证

三组均核冻结29项输入前后SHA、13个实际模块来源；真实Ninja路径及摘要入清单。

| 批次 | 方法 | 结果 | 控制器耗时 | 场景 |
|---|---:|---|---:|---|
| main | 53 | 全过，无skip | 31.141秒 | 隐藏控制台供普通后代继承 |
| short | 1 | 预期Timeout，无skip | 0.734秒 | 真实50ms，native本次0.047秒 |
| background | 4 | 全过，无skip | 1.438秒 | 无控制台和隐藏继承分案，含真实Ninja |

覆盖N/N+1、默认8MiB、无限无换行、合流、UTF8/换行、首因/日志失败、reader启动未知、原截止和Job构造故障，真实子进程与假API层级分别记录。50ms本次member已确认、尚未Resume/启动reader，pipe_eof=false；只授该早期拒绝窗口。三控制器记录exit0、tree0、双EOF、join与资源关闭，无强杀。

main的Node venv启动器PID35496退出0，控制器自报11912，两者OS父关系未采。short/background使用已核直接base Pythonw，根采集实际句柄PID23572/72256与控制器PID相等；独审核收据相符，未重采已结束的OS关系。完整父死亡、低内存、真实WinAPI失败及其它直接subprocess路径继续分别验收。

## 原失败与证据

003首轮main执行3方法即失败：新测试在assertRaises退出后查已被标准库清空的traceback。004仅在except内提前保存构造self，保留58条原断言与28方法，两个工具源码不变。原失败及关闭证据保留，新目录53项通过没有覆盖失败。

003集成（外部历史/待归仓路径：`../../build/native-bounded-output-execution-002/INTEGRATION.json`）、原失败（外部历史/待归仓路径：`../../build/native-bounded-output-execution-002/results-main/RESULT.json`）、004修正（外部历史/待归仓路径：`../../build/native-bounded-output-execution-003/INTEGRATION.json`）、冻结输入（外部历史/待归仓路径：`../../build/native-bounded-output-execution-003/INPUTS.json`）及实际结果（外部历史/待归仓路径：`../../build/native-bounded-output-execution-003/ROOT-RESULT.json`）分别登记。独立full（外部历史/待归仓路径：`../../build/native-bounded-output-independent-001/REPORT.md`）、003收口（外部历史/待归仓路径：`../../build/native-bounded-output-independent-001/revision003/REPORT.md`）、004测试delta（外部历史/待归仓路径：`../../build/native-bounded-output-independent-001/revision004/REPORT.md`）与动态复核（外部历史/待归仓路径：`../../build/native-bounded-output-independent-001/dynamic001/REPORT.md`）保留各自范围，动态54原件由根核同。

26项受保护框架摘要保持，真实券商调用0；账户状态算法与生产入口未改变。
