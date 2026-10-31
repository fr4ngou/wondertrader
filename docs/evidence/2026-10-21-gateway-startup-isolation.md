# QMT Gateway 启动隔离对照

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发诊断续接。日期：2026-10-21。状态：partial。前序现场记录见[来源诊断](2026-10-21-live-qmt-source-diagnosis.md)。本轮用户仅批准 WT CORE-004 一行保留；QMT 现场未变更。

## 观察与输入

本轮再次运行 `build/native/live-source-probe/capture_gateway_diagnosis.py`：18010 两次连接超时，Gateway 两次线程采样仍位于 `ssl.SSLContext.__new__` / Tornado HTTP 导入；Bridge 仍为上海 08:50 的旧账户快照。进程 PID 2824 仍为 08:50 启动的 XtItClient。没有启动策略、重启终端或改变下载。

QMT 当前只读源码 HEAD 为 `81faeec6a2907dadfaa4941de66bef0f96318e9b`。其他会话的任务登记变化保留。安装端与源码端分别识别，本轮隔离生命周期使用该源码版本，现场采样使用安装端。

构造私有 C++ launcher，在独立进程中加载原 `D:/software/guoxin/bin.x64/python36.dll`，设置该进程的 Python home，执行 `-B` 禁止字节码写入。只使用 Python/Tornado 运行库，不加载 QMT 客户端或账户 SDK。输出和临时文件均在 E 盘。

## 实际对照

命令：`D:/workspace/qmt/.venv/Scripts/python.exe -B build/native/gateway-startup-audit/run_probes.py`，工作目录为 WT 仓库。

| 场景 | 结果 |
|---|---|
| 新进程主线程 SSL context + Tornado HTTP 导入 | Python 3.6.8 / Tornado 6.0.2；约 0.453 秒；exit 0 |
| 新进程后台线程完成相同导入，主线程 join | 约 0.375 秒；worker 已结束；exit 0 |
| 原 GatewayServer 生命周期 + 合成 loopback HTTP surface | 随机本地端口启动，GET 合成 health 正常，stop 后线程结束；约 0.594 秒；exit 0 |

第三项仅替换 `make_application` 为无账户的测试页面，实际 import/bind/start/stop 使用原 GatewayServer。它证明当前运行库和生命周期在普通嵌入宿主中可运行，未验证 QMT ContextInfo、认证业务入口或客户端原生线程调度。隔离子进程均设 20 秒外部超时。

## 结论与后续

现场卡住与独立进程可运行同时成立。当前证据不支持直接归因为 Python/Tornado 文件普遍损坏、所有后台导入都会失败或默认 5 秒必然不足。前序已采到宿主主线程持有解释器锁、Gateway 在等待重新取得锁；最初启动为何进入这一状态仍待追踪。

后续沿嵌入宿主锁释放、启动超时与后续状态收敛、QMT 回调调度三个边界建立确定性交错实验。暂未形成已验证修复，因此不部署候选、不盲目延长超时，也不申请宽泛重启授权。已经下载的分钟样本仍可在读取通道恢复后先验完整交易日，不等待全市场下载。

附件：机器结果（外部历史/待归仓路径：`gateway-startup-2026-10-21/results.json`）、启动探针（外部历史/待归仓路径：`gateway-startup-2026-10-21/probe_startup.py`）、launcher（外部历史/待归仓路径：`gateway-startup-2026-10-21/python36_host.cpp`）。原驱动脚本和完整日志保留于本机 `build/native/gateway-startup-audit`；这些附件属于隔离实验，不作为生产配置。

## 追加：确定性启动取消故障

同日使用原 `GatewayServer`、同一 Python 3.6.8 运行库及合成 HTTP 应用，在后台线程进入 `tornado.httpserver` 导入时设置测试栅栏。主线程调用 `start(timeout=0.05)`，收到启动超时；随后调用 `stop(timeout=0.05)`，最后释放栅栏。只对隔离进程做导入延迟注入，现场 QMT 保持原样。

两次独立子进程均观测到：启动超时后 `_stop_requested=false`，`stop` 返回 false，后台线程仍存活；释放导入栅栏后线程绑定随机本地端口，合成 `/health` 可访问。探针按“启动失败且已要求停止后仍继续监听”的断言退出 11；每次最后正常清理线程。外部记录器确认两次均稳定触发，因此自身 exit 0 表示成功捕获红测试，不能解释为原实现通过。

根因边界：`start` 超时仅抛出异常，未表达取消；`stop` 遇到尚未创建 IOLoop 提前返回；`_run` 后续阶段未检查启动取消。这证明启动失败后的生命周期缺口。现场首次 SSL/GIL 等待的触发原因仍待验证，修复该取消语义的资格独立登记。

命令：`D:/workspace/qmt/.venv/Scripts/python.exe -B build/native/gateway-startup-audit/run_lifecycle.py`。输入源码及 DLL 摘要、两次观察见生命周期机器结果（外部历史/待归仓路径：`gateway-startup-2026-10-21/lifecycle-results.json`）；复现代码见探针（外部历史/待归仓路径：`gateway-startup-2026-10-21/probe_lifecycle.py`）与有界记录器（外部历史/待归仓路径：`gateway-startup-2026-10-21/run_lifecycle.py`）。下一步在私有源码副本验证统一取消状态、第三方调用返回后的清理和同实例重启，沿用原 Tornado 网络及排空实现。

## 追加：用户重启策略后端点恢复

2026-10-21 上海17:18复查，同一PID2824仍为08:50启动的客户端进程；18010连续两次可连接，后台采样已无SSL导入等待，Bridge账户快照更新到17:17:53。用户随后明确告知已重启国信QMT的AI ETF策略，签名健康和状态接口正常。因此端点恢复归属于用户这次操作，本任务未部署取消候选或重启终端。

原Bridge→Gateway只读 `market.market_data_ex` 已取得2026-10-20的真实1m：688076.SH为189条、300308.SZ为239条，均09:31至15:00；原始响应与规范化条数一致。请求指定subscribe=false、fill_data=false、dividend_type=none，没有下载或行情订阅。全日完整性、时间/量额语义和WT导入继续单独验收。

恢复摘要见只读现场快照（外部历史/待归仓路径：`gateway-startup-2026-10-21/recovery-observation.json`）。此前故障记录保留；当前“18010无监听”阻塞已解除，启动取消实验仍作为独立恢复缺陷处理，现场首次卡住首因尚未因端点恢复自动确定。
