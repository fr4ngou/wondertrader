# 2026-10-26 既有QMT共享内存策略重新运行

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：现场恢复验证记录。状态：首次受控尝试失败，未建立绑定，真实读取0；本次Host正常关闭，外部QMT策略停止状态待确认。整体开发继续。

## 纠正此前诊断与范围

用户截图指出策略未运行。根通过computer-use重新选中真实国信QMT主窗口，观察QMT_METRIC_GATEWAY和GH_WT_MEMORY_VERIFY均为待启动控件，底部执行策略计数0。此前只核进程/监听/健康，漏核目标策略实际启动；进程存在不能作为来源已运行的依据。

GH_WT_MEMORY_VERIFY磁盘SHA e105005f871e63de6f35590b308335b47c1f6120cae32c312e7d65ac510c80ec匹配[账户004](2026-10-23-qmt-memory-account-read.md)已验正文；它允许账户读取和full_tick，写能力关闭。本次复用同一正文和配对材料，独立已装Host解释器及20Host/28Agent源经摘要核同；未运行旧QMT工程、未改策略、原Host18017和其他策略保持归属。新attempt采用受保护的新通信Journal，仅变该路径，旧Journal不导入、不修改。

候选003与控制器002经静审（外部历史/待归仓路径：`../../build/qmt-memory-restart-independent-001/static001/REPORT.md`）和窄审（外部历史/待归仓路径：`../../build/qmt-memory-restart-independent-001/delta002/REPORT.md`）核验。候选的固定生成正文SHA与QMT保存版SHA分别校验，随后只允许已确认的CRLF与一个末尾LF差异；结果落盘及stdout flush后继续核原截止。旧001/002候选保留，未执行。

## 实际操作与结果

先启动独立只读Host18018：根原250秒实际保留进程句柄PID25128，创建期Job/2GiB/双首64KiB控制器预算245秒，子helper原双时钟截止约240秒。root-start文件时间02:53:09.379Z；host-ready时间02:53:15.082Z，只证明监听准备。

随后在QMT单次点击第六行GH_WT_MEMORY_VERIFY启动，界面底部执行策略计数由0变1，该行操作控件变为停止；没有启动其他策略。Host未取得read-binding，未观察到策略tick，没有发出full_tick POST。终态为TimeoutError，binding=false、ticks=0、full_tick_posts=0；账户、历史、下单和撤单请求全部0。来源读取与共享内存可用性保持未验证。

尝试查看本次策略运行页时，computer-use报failed to activate captured window；重新枚举窗口、重新选择及激活后再次同错。依工具恢复规则停止所有界面输入，已请求用户仅停止GH_WT_MEMORY_VERIFY。其停止结果尚未取得，不能以Host已关闭替代QMT策略停止确认。

本次Host在原期限内自行正常收束：根实际exit2，230.494594秒，guard=false；控制器parent25128/child66772，childexit2，230.297秒，forced=false，Job树0、双EOF、线程join及资源关闭均true。helper host_closed/observer_joined=true、success=false。失败与资源关闭分别记录；见根原件（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-source-readonly-20261026-001/ROOT-RESULT.json`）。私密配置/凭据和原始日志未进入公开记录，私有结果只封安全字段及摘要。

## 根因范围与后继

原连接等待窗口60秒保持。Host启动、模型轮次、QMT启动和正文装载分别占时间；first_post_click_observation_utc不是精确点击时间。当前证据无法区分连接窗口、模块旧上下文、实际策略初始化失败或其他握手原因，不能把TimeoutError直接归为协议缺陷，也不能宣称窗口超时已被证明。

下一次先取得QMT策略已停止的真实状态及其本次运行错误，再准备完整UI观察。在同一个动作调用中启动自有Host、等host-ready、立即点击此前已观察的专用启动控件并刷新，保存点击前后与Host原期限时点；不延长原60秒，不无界重试。当前一次失败完整保留。历史K线导入范围继续，旧历史交易记录按[GBW-R9](../specs/guanheng-business-workspace.md#gbw-r9-新系统启用与历史数据范围)排除。


## 用户停止确认与第二次立即启动验证

用户随后明确回复已停止GH_WT_MEMORY_VERIFY；根重新选取QMT窗口核红色“停止”和执行策略0。首轮停止缺口已取得人工确认，停止原件（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-source-readonly-20261026-001/HUMAN-STOP-CONFIRMED.json`）保留。

第二次沿同一已审helper003，仅新建独占attempt/Journal和控制器输出目录。在已观察专用启动控件的同一个动作调用内启动Host、等ready并立即点击：根开始后2.681秒，点击03:08:25.695Z至03:08:25.831Z，QMT明确显示该策略绿色“运行中”。仍未建立绑定，78秒时Host健康为unavailable/TimeoutError，last_tick为空。实际观察保存在第二次启动（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-source-readonly-20261026-002/ROOT-START.json`）。该结果排除了根在本轮等待模型轮次后才点击的操作延迟；策略装载/初始化及握手各自仍待取证，不能据此断定某个组件存在bug。

根于03:11:43.291Z至03:11:43.435Z实际点击同策略停止，界面红色“停止”、执行数量0，并出现该策略11:11:43停止记录；旧AI_ETF的10月24日stale-context日志与该策略分别归属。新Host随后在原截止内正常关闭：根实际PID34328 exit2、230.373167秒，guard=false；控制器child9256 exit2，230.266秒，无forced/errors，树0、EOF/join/资源关闭全部true。绑定/观察tick/业务POST均0，真实账户/历史/下撤单请求0，helper host_closed/observer_joined=true；第二次根结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-source-readonly-20261026-002/ROOT-RESULT.json`）及实际UI停止（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-source-readonly-20261026-002/UI-STOP-CONFIRMED.json`）。没有进行第三次同样重试。

当前专用策略与两次自有Host均已停止；当前来源仍未恢复。已打开同一策略编辑器作只读核验，UIA不提供正文/选中文字，无法据此证明编辑器缓冲与磁盘SHA一致，未编辑或保存代码。磁盘正文仍固定e105...。公开模板的builtin分支通过字符串执行后动态导出init/handlebar/timer/stop；init内部依次构造Agent、注册timer、启动通信。实际初始化停在哪一阶段尚无证据，入口静态分析（外部历史/待归仓路径：`../../build/qmt-memory-entry-analysis-001/REPORT.md`）给出下一步限定诊断；必要时仅加入固定公开相位标记，保持源调用和异常语义，先冻结/验证候选及明确恢复原SHA方案，再操作现场。此处ticks=0只表示helper尚未取得可观察tick，不能证明QMT原回调绝对未执行。

## 同策略阶段诊断后继

用户已关闭编辑器，根完成限定一次临时阶段诊断并恢复原 e105 字节。实际 QMT 运行/停止和 Host 正常收束均已验证，绑定仍超时；可见输出未出现阶段标记，实际装载正文与初始化尚未核实。见[独立现场证据](2026-10-26-qmt-entry-phase-diagnostic.md)，不将可见标记缺失推断为回调绝对未执行。
