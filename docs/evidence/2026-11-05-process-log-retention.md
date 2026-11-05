# 自有受管进程退出后的日志留存

类型：开发增量验证。日期：2026-11-05。状态：候选主路径、原反例回归及独立复查已通过；正式制品和线上采用待完成。范围为[SDO-R5](../specs/strategy-data-and-observability.md)，不涉及WT上游或交易算法。

## 根因和实现

原ManagedLocalProcess只将stdout/stderr有限前缀放入私有内存，reap完成后清空。部分启动失败只能留下unexpected_exit等外部阶段，首个异常类型和原输出已无法核实。复用原reader消费同一批字节，在runtime_diagnostics内保存固定类别、已知模块行位置、生命周期及流计数/摘要；进程原状态、输出容量故障、Job及关闭语义继续保持。

新日志使用稳定控制根的process-events.jsonl系列，默认当前加三份轮转合计不超过4MiB。每流残片最多8192字节；不保存原始正文、参数、完整路径、凭据或自定义异常类名。日志失败计数与原业务失败分开，后续采用必须检查实际落盘。

## 实际验证

现场独立QA根为`E:/workspace/wondertrader-qa/current-day-20261105-001/process-log-main001`。使用运行解释器017启动一个真实隐藏Python子进程，通过实际ManagedLocalProcess._start_readers/_reader消费其stdout/stderr；子进程抛PermissionError(errno=5)、退出1。原内存清空后仍有五条事件：启动、异常、两个流摘要、关闭；私有测试字符串未落入日志，写失败0。该进程没有Host/QMT或委托能力。

新增`tests/integration/wt_runtime/test_process_event_log.py`五项通过：真实子进程首错留存、任意分块及已知模块行位置、跨运行代轮转总量、超长行/自定义异常的脱敏、日志I/O失败不替换原业务结果。原`test_failure_diagnostics.py`七项通过，原正常收据/首错/清理异常/Windows文件拒绝与泄密防护保持。

命令：使用017的python.exe，依次执行`-B -m unittest discover -s tests/integration/wt_runtime -p test_process_event_log.py -v`与同目录的`test_failure_diagnostics.py`。当前输入共12项窄验证；不扩展为全部受管角色或生产资格。

## 审查反例与根因修正

独立规范/SDO审查复验原12项，并新增两个反例：同步fsync阻塞时，原failure尚未发布停止事件和首截止；两个实例共享日志系列时，8192B声明预算实际达到8369B，当前文件4273B超过4096B。分别为P1日志I/O影响原生命周期、P2跨实例轮转所有权缺失。

20:53追加修正：原失败先发布stop/ready及首截止；所有磁盘日志移到全进程唯一daemon写线程，256条有界队列、每条最多4096B，锁外做磁盘I/O。队满计records_dropped，慢盘保留records_pending；原关闭不等待日志。OS非阻塞文件锁覆盖同系列容量检查、轮转、追加和fsync，跨进程竞争计write_failures，固定锁文件仅1字节。

新增两项原反例回归已通过：人为阻塞真实fsync时，实际ManagedLocalProcess._failure立即设置stop/ready及首截止，实际_reader完成EOF，后续failure未延长首截止；300条事件提交时最多257条含在写的pending并明确drop，释放磁盘后排空。两个真实隐藏Python进程各提交120条，共享4096B当前文件及1份备份，每文件不超4096、合计不超8192、JSON均完整、写成功与失败合计对应提交数。上述运行使用017解释器，当前源七项+原CLI七项均通过；现场QMT和WT进程未启停。

## 剩余

修正后独立delta复查通过，范围为最终SDO、规范及两份源码和新增回归，不给审查者读取任务/历史报告；复查重跑14项，并额外以output_limit作首错阻塞真实fsync、及独立解释器不调用drain直接自然退出验证。停止/EOF继续、四条自然退出事件留存且私有正文未出现，未发现新可复现缺陷。审查不授整个系统完备或线上资格。

固定完整Runtime候选及线上采用继续；逐角色核新日志实际路径、内容、启动失败与正常停止/恢复。组合包必须保留当前Runtime13原封存overlay能力，不能直接把开发目录全量构建误作现有全部线上行为。磁盘持久阻塞/异常退出可能丢尾部事件，诊断计数与实际文件分别检查；当前线上未切换，不宣称历史首错已追回或全系统日志覆盖完成。
