# 2026-10-24 QMT源端下单撤单内核开发验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发证据。状态：QST-R9源端切片已实现、纯替身和目标解释器验证通过；正式交易整链与真实写入继续关闭。

## 实现与范围

用户选择进度最快的已实测嵌入加载/builtin-shm方案；可读正文转换未实施。新[trading_kernel.py](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/trading_kernel.py)沿[QST-R9](../specs/qmt-shm-trading.md#qst-r9-第一源端切片的冻结接口)接收显式固定账户/合约规则、SDK callable、ContextInfo与源端原截止；默认writes_enabled=false。它只在原线程live_drain执行现金普通限价的11参数passorder及4参数cancel，公开stock显式映射官方STOCK。

价格格用有界整数分数计算，数量按受信min/step，不依赖调用者Decimal上下文。SDK前占有限命令身份，同ID同文取原结果副本，异文拒绝，不自动逐出/重发；调用进入后异常、错误返回或晚于原D返回，保留unknown并关闭新写。None仅SDK调用返回，cancel bool仅取消信号事实。快照保留缺失/null/0与原备注，不猜orderError关联。模块不创建线程、文件、网络或外部DLL，也不维护金融账本。

产品源码SHA256为ac9e243040e839e2ec4bf87d0a7c2df2e6f04544524d133ec39f5a95192b34ef；测试源码（外部历史/待归仓路径：`../../tests/integration/qmt_shm_trading/test_trading_kernel.py`）SHA为5ffb9b1000fd9af6197badcdb8c0e9bb2ee18023ad14a6a6138ab17fd912a5a8。固定WT原件确认entrustID/userTag的char[64]容量，拒绝超63 UTF-8 bytes与截断；账户上限沿QAR。

## 实际验证

21项unittest分别在开发CPython3.12.14和目标券商CPython3.6.8解释器通过。覆盖精确参数与调用线程、默认禁写、账户/形状/类型、价量格、Decimal恶意上下文、重复/冲突/结果副本、容量、原截止、异常与晚回、同步重入、其他线程调用及stop竞争、源字段单次getter和错误不猜身份。SDK都是独立记录参数/次数的替身，真实委托调用数0。

目标3.6.8的私有内存探针另冻结82模块，正文1,452,431字节；使用现有生成器和私有importer加载新kernel。受限验证区内禁止普通文件入口及非内建模块导入，完成两次SDK替身调用（一次下单、一次撤单）、原ID重复取结果和停止后拒绝新调用。实测文件/外部导入尝试0、私有加载器文件尝试0。探针准备和结果文件由终端外验证工具读写；它不是QMT策略部署，也没有建立SHM连接或访问实际券商SDK。

原件：内存探针身份（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-trading-memory-probe-001/runtime-identity.json`）、实际结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-trading-memory-probe-001/result.json`）。三次运行的受控回执均exit0、非forced、tree0、双EOF、reader join及资源关闭；见account-runtime-install-001的build-qmt-trading-kernel-unit-001、build-qmt-trading-kernel-sdk-unit-001及build-qmt-trading-memory-target-001。目标解释器实际运行不授券商写权限。

Astra独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-trading-kernel-review-001/REVIEW.md`）已静态complete，无确认P1/P2；来源SHA表另存。审查自身执行0，运行证据由上述回执独立承担。

## 尚未交付的完整交易链

现有pair/RestrictedReadAgent与Host没有注册交易kernel，部署仍order_ready=false；本轮未修改其已测加载器，也未操作QMT终端、原策略或Host。Host写协议/持久受理与unknown核查、SHM写方法与回报队列、同一策略注册、普通TraderQMT标准入口和SPI、初始化查询/推送交接、完整交易宿主停止及正式安装均待继续实现。实际备注长度/回显、回调线程与重启查询连续性仍需来源证明。

真实下单/撤单测试另按明确账户、环境、标的、数量、动作和停止条件授权。整个观衡迁入目标保持active；本源端切片不替代完整交付。
