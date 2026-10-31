# 2026-10-23 自有内存策略真实账户四查询

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：本次实机验证记录。状态：账户、持仓、委托和成交四类读取及同ID终态恢复通过；完整迁入目标继续active。

## 实现与受限终端边界

专用GH_WT_MEMORY_VERIFY使用本仓独立安装生成的完整正文内存加载器，传输为builtin-shm/qmt.builtin-shm.v1。终端外维护工具读取源码、核验并生成策略；QMT加载完整正文后，私有importer从正文的源码表编译到内存。生成代码的open/FileIO等文件入口被拒绝，白名单之外的模块无法导入；builtin_shm使用mmap(-1, …, tagname=…)建立系统内存支撑的命名映射，不打开磁盘数据文件。QMT原策略线程调用只读SDK，I/O owner负责共享内存收发。终端内不建立HTTP/TCP连接；外部Host的网络、Journal和包文件属于独立进程。

源码依据：[加载器](../../connectors/qmt_shm/host/guanheng_qmt_shm/memory_runtime.py)及[内建共享内存](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/builtin_shm.py)。既有禁文件/网络隔离回归保持其范围；本次实机没有对整个QMT进程设置系统级文件访问监视。平台加载策略、券商SDK自身的缓存行为另属平台职责。

## 真实失败、根因及修正

实机002的持仓/委托/成交返回成功，资金读取失败。实机003的一次有限脱敏诊断确认：SDK返回账户匹配，资金数值有限，m_strMoneyType精确为空字符串；本仓Agent将其误判为币种冲突。诊断正文已移除，最终实机004使用完整干净正文。

按更新后的[QAR规格](../specs/qmt-shm-account-read.md)修正自有两层：Agent保留SDK空串，并继续拒绝错误账户、非空错误币种及错误类型；自有C++ AccountMapping将缺省或空币种映射为原有facts.m_strMoneyType的unknown，金额与可用余额保持原值。WTS要求的币种来自显式配置，来源事实与配置声明分别表达。WT框架源码未新增修改。

两份产品源码SHA256：account_query.py为b5133ac48da25a4f42e3ceb2c0a5669d2d3d927fdbcc4b8f56bd69c0e57137ce；AccountMapping.cpp为4a14ca2eeeed6ebdd3d66403d254a5418227b779ebc1c48fbe94263ba07ef5ed。普通fact映射保持，金额、可卖数量与账户约束保持。

## 验证证据

相同合成触发输入在旧独立安装复现source_value_invalid，新源码通过，原SDK仅调用一次；五类错误账户/币种输入继续拒绝。首次错误测试预算配置保留失败记录，不充当根因复现。28项Agent单元、57项投影回归通过；投影使用开发环境测试当前App源码，首次独立App环境缺pytest的失败保留。独立安装已重新离线构建，Host安装中的Agent匹配修正SHA，没有覆盖旧安装。

固定原上游及已批基线的隔离原生构建完成176步，同时构建普通AccountScan及TraderQMTReadOnly；CTest一组通过、覆盖128项币种与账户映射检查。此项授自有映射与普通原生编译证据，尚未完成真实账户经C++插件到业务页面的整链资格。

原件见原生结果（外部历史/待归仓路径：`../../build/native/account-currency-001/result.json`）、CTest日志（外部历史/待归仓路径：`../../build/native/account-currency-001/cmake/Testing/Temporary/LastTest.log`）、源码审阅（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-currency-review-001/REVIEW.md`）、实机独立核证（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-currency-review-001/LIVE-EVIDENCE.md`）与注释后继（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-currency-review-001/comment-delta.json`）。两处测试首段的旧执行状态已改为稳定说明，其余字节不变，沿用上述行为测试。

## 实机004结果

使用新独立安装Host、专用18018、最新完整策略正文和新私有配对。策略生成正文1,430,852字节，SHA256为b4e7b8446074907af3aa4416bd98a1e54974d9dd246c694687db11b48d956fd4；QMT编辑器保存SHA为e105005f871e63de6f35590b308335b47c1f6120cae32c312e7d65ac510c80ec，规范换行及末尾换行后逐字相等，临时诊断不存在。

认证绑定与两次新鲜递增agent_tick后，各类只POST一次、按原request_id GET终态，并另存相同ID恢复原件。四类结果来源绑定、原bytes摘要与恢复终态核同：

| 查询 | 返回行数 | 端到端秒 | 结果边界 |
| --- | ---: | ---: | --- |
| 持仓 | 4 | 4.125 | 包含可卖数量字段；币种字段缺省 |
| 委托 | 0 | 4.984 | 空表读取成功，非空字段待验 |
| 成交 | 0 | 5.016 | 空表读取成功，非空字段待验 |
| 账户资金 | 1 | 4.968 | 余额和可用资金为有限数值；来源币种为空串 |

脱敏摘要见四查询结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-terminal-20261023-004/account-read-summary.json`），金额、账户标识及持仓证券原件仅保留受保护private目录。配置environment=live是受信配置声明，本次不以该字段证明券商实际登录环境。

外层受控回执exit0、forced=false、tree_zero=true、双EOF、readers_joined及resources_closed=true。Host于15:18:53.311Z按有限运行期限正常关闭，stop-host文件15:19:03.093Z随后产生；这次关闭不能归因于stop-host，也不授完整维护顺序资格。当前专用QMT策略已停止，原QMT_METRIC_GATEWAY文件SHA前后保持d9c51b8150fbd9f511e1cfab9b24b532991276c6b5f6056e185a730fc2741824，原策略及Host未替换。

## 后续边界

本次order_ready=false，没有调用下单或撤单。正式交付仍须实现并验收这些能力；SDK写命令、WT原生Trader委托身份/回报接线、未知结果恢复与真实交易授权分别处理。原只读Adapter的拒绝写入行为保持。账户四次读取拥有各自来源时点，不声明跨查询原子快照。C++真实账户整链、实时策略、历史覆盖与量纲、完整关闭矩阵及独立正式发行继续。整体目标保持active。
