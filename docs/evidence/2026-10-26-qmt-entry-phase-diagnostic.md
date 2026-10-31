# 2026-10-26 QMT 同策略启动阶段诊断

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：现场定位证据。结果：QMT 界面实际运行和停止已确认；共享内存绑定仍未恢复，实际装载正文及初始化阶段仍待核实。

## 诊断范围与验证

用户明确关闭 GH_WT_MEMORY_VERIFY 编辑器后，根重新选取唯一国信 QMT 主窗口，确认专用策略红色停止、执行计数 0。原磁盘正文与受保护逐字备份均为 e105005f871e63de6f35590b308335b47c1f6120cae32c312e7d65ac510c80ec。仅在同一策略加入固定 GHWT_DIAG_V1 阶段日志，原调用顺序、动态回调导出、返回及异常处理保持；终端内没有新增文件读取、网络或券商调用。日志只包含固定阶段名和异常类型枚举。

公共转换器 候选（外部历史/待归仓路径：`../../build/qmt-memory-entry-diagnostic-candidate-001/DESIGN.md`）经独立静审（外部历史/待归仓路径：`../../build/qmt-memory-entry-diagnostic-independent-001/static001/REPORT.md`）。10 项合成回归在现代独立解释器与国信附带 Python 3.6.8 均通过；后者单独核版本、isolated/no_site。见现代回执（外部历史/待归仓路径：`../../build/qmt-memory-entry-diagnostic-runtime-001/ROOT-VERIFIED.json`）和3.6.8 回执（外部历史/待归仓路径：`../../build/qmt-memory-entry-diagnostic-runtime-001/PYTHON36-ROOT-VERIFIED.json`）。独立解释器测试证明转换语义与版本兼容，实际 QMT 策略装载仍需现场证据。

只读运行候选（外部历史/待归仓路径：`../../build/qmt-memory-diagnostic-run-candidate-001/CONTRACT.md`）固定原配对、原保存备份、已审转换器及唯一诊断 SHA 8ea8243aa4657cf35d2eded5cb554d643410fb65e60c5ca852e5c887cab413e0。helper 只执行公共转换定义、核策略字节，不执行策略正文；最多两次原 health 方法的封闭内存投影。原只读能力、一次 full_tick 上限、240 秒原双时钟截止、10 秒关闭预留保持。helper 与固定控制器分别经过full（外部历史/待归仓路径：`../../build/qmt-memory-diagnostic-run-independent-001/static001/REPORT.md`）及delta（外部历史/待归仓路径：`../../build/qmt-memory-diagnostic-run-independent-001/delta002/REPORT.md`）审查。

## 实际运行与恢复

根临时写入上述诊断字节并逐字核摘要；原配对正文保持 b4e7b8446074907af3aa4416bd98a1e54974d9dd246c694687db11b48d956fd4。独立 Host 就绪后在同一动作调用内点击既有专用策略：点击完成 03:54:44.375Z，距根启动约 2.000 秒；界面绿色运行中、执行策略 1。18 秒及约 76 秒观察时，输出区没有可见 GHWT_DIAG_V1 标记，helper 尚未取得 binding。标记缺失只描述可见输出，不能证明模块或回调绝对未执行。

03:56:15.963Z 至 03:56:16.096Z 根点击同一控件停止；刷新后红色停止、执行策略 0。随后创建本 attempt 的 stop.request，并在核目标仍是本次诊断字节后，恢复受保护原字节；重读摘要与原 e105 完全一致，编辑器保持关闭。部署/启动/停止/恢复原件（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-source-diagnostic-20261026-001/DEPLOYMENT-PLAN.json`）分列保存，其他策略未操作。

文件元数据检查在明确范围内未找到 .py_000030 落盘副本；检查原件（外部历史/待归仓路径：`../../build/qmt-memory-run-copy-inspection-001/RESULT.json`）记录恢复前的观察。该后缀是否仅为内存运行实例标识仍未知。当前需要定位运行列表项实际正文 owner 与 QMT 初始化路径；继续保留协议失败、缓存或其他装载原因的证据空缺，不据现有现象修改 WT 框架或新增持仓账本。

## Host 终态与证据边界

根实际 PID 24164 在 230.3782486 秒退出 2，原 250 秒 guard 未触发。控制器自身 parent_pid=24164、受控 child_pid=24452；原 245 秒内 230.282 秒退出 2，forced=false、errors 为空，创建期 Job 成员、树 0、双 EOF、线程 join 与资源关闭均通过。helper 终态 binding=false、观察 tick=0、full_tick POST=0，唯一错误 TimeoutError；health 两次有限投影从 unavailable/null 到 unavailable/TimeoutError，last_tick 均缺。host_closed 与 observer_joined 为 true，账户/历史/下单/撤单请求均 0。实际根终态（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-source-diagnostic-20261026-001/ROOT-RESULT.json`）保留失败；资源收束通过不能提升连接资格。

stop.request 已在 UI 停止后创建，但 helper 的等待仍位于 binding 失败路径，因此 stop_seen=false；该字段不用于否定另行保存的实际 UI 停止。原策略逐字恢复 e105，原 pair 保持 b4e7。当前还需核运行列表实际正文归属与初始化链；仅发现候选位置不等于已定位根因。

独立动态复核（外部历史/待归仓路径：`../../build/qmt-memory-diagnostic-run-independent-001/dynamic003/REPORT.md`）核对上述身份、实际失败与资源关闭，当前目标与保护备份逐字相等。运行实际正文和源端首因保持 unknown；只读元数据候选 configFormula 的内容读取返回 EBUSY，未解除锁、未停终端，见受阻记录（外部历史/待归仓路径：`../../build/qmt-memory-configformula-projection-001/RESULT.json`）。
