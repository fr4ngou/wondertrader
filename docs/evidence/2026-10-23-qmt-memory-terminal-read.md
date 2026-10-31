# 2026-10-23 自有内存策略的真实QMT只读验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：本次实机验证记录。状态：该精确配对的一次行情快照读取、同ID结果恢复及外部Host正常关闭通过；整体迁入仍active。

## 根因、范围和身份

前序核对手册、源码及合成CPython3.6.8回归证明各自范围，尚未证明最新自有入口在券商QMT实际运行。为保留既有install-008与AI_ETF运行归属，本次在真实国信QMT编辑器新建专用GH_WT_MEMORY_VERIFY，加载本仓独立安装生成的完整ASCII正文。新入口只允许market.full_tick；未提供账户、passorder或撤单能力。新增策略是本次隔离验收方式，正式产品可由同一受管入口承载已实现并验收的行情、账户和交易能力。

终端版本3.12:1.2.26.150；完整内存加载与builtin-shm；外部Host使用本仓组合002非editable独立安装及解释器，监听本次独占18018。新配对生成正文1,429,853字节，SHA为01ab24dba6e82a093a6777fe3c67ba98f3c59b3ae65c082badf592892da65a7b。QMT编辑器保存CRLF与末尾换行后1,429,863字节，SHA为32e9c3f077b0b7720984c05e99270e2cdabd29fdb6fc75e04f598d626f433ef4；规范换行并比较末尾换行后内容相等。临时GH_SHM_DIAG_003诊断已从专用策略正文移除。

受控原件目录为实机002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-terminal-20261023-002/evidence-identities.json`），包含公开请求/绑定/终态/资源回执的逐文件摘要。私有pair正文和凭据保留受保护目录，不进入公开记录。原QMT_METRIC_GATEWAY保存文件前后SHA均为d9c51b8150fbd9f511e1cfab9b24b532991276c6b5f6056e185a730fc2741824；本次未重启终端、替换原策略或Host，也未执行旧QMT工程。

## 排队失败与修正

前序实机001的多次只读请求返回queue_timeout，原件及静态调查保留在排队调查（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-live-queue-audit-001/REPORT.md`）。验收配置误用了合成夹具的queue2s；现场install-008公开policy为queue20s/native5s/grace1s/total30s。实测一次Host实际发送时仅剩约44ms，QMT原回调随后拒绝过期任务，原生调用尚未执行。Host异步认领与后续循环发送的顺序已有源码依据，各阶段具体耗时仍需单独测量。

新配对采用queue20s/native2s/grace2s/total24s/control max_call30s，保持原生调用2s及仅行情读取范围。队列预算覆盖现场调度等待；原请求截止继续执行，未增加重发。该修正解决本次实机的过短验收预算，不授持续实时性能或一般延迟保证。

## 实际结果

1. 在QMT点击运行本次专用策略，取得真实认证read-binding及两次递增策略线程agent_tick心跳。
2. 只POST一次market.full_tick，参数stocks=[000001.SZ]，request_id=31b3915a-cd85-4dfd-a6c7-f67034c84c38。按同一ID GET终态，HTTP200/ok=true，三份来源B与本次认证绑定一致，结果原bytes摘要相符。
3. 返回lastPrice=11.200000000000001，来源time=1792744614000，即北京时间2026-10-23 16:36:54；完成约22:41:54。盘后快照的来源时间原样保留，不能据此声称新鲜实时行情或连续推送。端到端耗时4.062s；Agent本地排队16ms，执行计时0ms为毫秒量化值。
4. 再GET相同request_id，脚本断言完整终态相等，read-complete保留same_request_terminal_recovered=true。该项只有脚本断言与收据，第二次HTTP原bytes没有另存，证据边界一并保留。
5. 在QMT点击停止本次专用策略，再通过公开Host owner请求正常关闭。Host观察线程join通过；外层隐藏创建绑定Job回执exit0、forced=false、tree_zero=true、双EOF、readers_joined/resources_closed=true。过程未进行账户查询、下单或撤单。

独立静态审阅见实机结果复核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-memory-live-queue-audit-001/LIVE-REVIEW.md`）。程序退出与本次只读成功各有原件；本记录不以按钮状态代替QMT内部I/O线程与映射逐项审计。

## 下一交付与保留边界

用户已明确正式接入必须包含行情、账户/持仓/可用资金、委托/成交查询及下单/撤单。账户读取沿[QAR](../specs/qmt-shm-account-read.md)及原TraderAdapter；交易走WT原生Trader/订单/成交能力，先冻结命令契约并完成无副作用验证，再按具体授权验真实委托。不添加旧平台资本账本、逐单人工审批或独立持仓数据库。

本次只授精确配对的一次真实行情快照读取。真实四查询、下单/撤单、完整历史覆盖和单位、C++插件到策略/业务链、持续性能、MEM-G1共享内存发布排序资格、完整关闭矩阵、新机发行与生产切换均分别继续验收。已有合成零文件回归保持其原范围，本次没有在券商内设置全局文件访问监视或修改其安全设置。
