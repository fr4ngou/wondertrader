# 独立安装Host与完整内存策略两代读取

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：主路径开发验收。日期：2026-10-28。状态：跨进程合成SDK组合passed；真实QMT两代运行仍pending-verification。

## 调用链与结果

实际观衡create_app/lifespan→QmtHostProcess/Windows Job→独立已安装Host的run-pair→真实builtin-shm/HMAC→国信配套CPython3.6.8完整生成正文→原线程SDK替身→原Host终态→签名HTTP读取。App父进程未导入Host包，策略读账户/行情，交易权限关闭。每代按1秒推进原agent_tick；首次源连接晚于夹具原1秒单连接窗口（Host ready后等待1.5秒）。此前真实QMT425秒首次等待证据独立保留，此测试不把短窗口等价外推为当前真实终端。

同一个Host PID3192完成两代，各5次：position/account/order/deal/market.full_tick。持仓100、可用金额900与价格3.25均为明确合成值并按响应核对；委托/成交成功空集。SDK总计10次，全部在各源进程的原创建线程执行。两代binding不同，第二代重取第一代终态逐字段完全相同，旧binding提交返回409；每代调用数仍5，证明此组合未自动重发旧SDK工作。

源进程均实际3.6.8，close返回及原I/O退出确认，禁止访问入口计数0。该计数覆盖正文受限入口，不代表整个券商平台的系统级文件审计。源脚本的文件协调发生在终端外夹具，生成正文继续沿原内存运行方式。

App shutdown_complete=true，Host state=closed/pending=false/forced=false/error=null。控制器qmt-resident-installed-two-gen-main-001实际exit0，约18.256秒；子流程17.109秒。原120秒总预算保持，未强杀；整树归零、stdout/stderr EOF、reader join和资源关闭由原控制器收据确认。

## 入口和输入

可重复入口run_installed_memory.py（外部历史/待归仓路径：`../../tests/integration/qmt_shm_reconnect/run_installed_memory.py`），准备器prepare_installed_memory.py（外部历史/待归仓路径：`../../tests/integration/qmt_shm_reconnect/prepare_installed_memory.py`），目标源source_memory_peer.py（外部历史/待归仓路径：`../../tests/integration/qmt_shm_reconnect/source_memory_peer.py`）。它们只承担隔离验收，产品模块本轮保持。准备器使用已安装Host/Agent生成并verify私有v3配对，Host和完整策略共享冻结的配置身份。Journal显式64条/1MiB，遵循原records×单记录额度联合约束；不删除旧请求或更改容量计费合同。

原始结果build/qmt-resident-installed-two-gen-verify-001/run/RESULT.json，私有配对在同根private下受控。Host安装仍为qmt-resident-host-install-003/runtime-001/host/venv，App用当前项目依赖及源码包。验收入口SHA分别589203f3ade0122d2527a27073fbb1d14121d5e77b033ed351004568aa8dd4a9、c29827984c6fe768a4acc18c8e4aba502efab3d86b5f3d0317d647fdc14cfe67、abde900ddad80fc1fe80a59dc688056623d7af76f974668cfdc7535568e0f28f。SDK标准库元数据/许可证从既有已核资料在终端外输入；当前运行源闭包由配对manifest核验。

先前临时组合qmt-resident-memory-app-two-gen-main-002也通过（约15.855秒），Host PID61824、各5次、旧结果和关闭一致。更早一次夹具误读不存在的closed_complete属性，在五查询完成后失败；按实际close返回/owner清空/I/O退出契约修正，原失败日志与同Journal旧终态均保留。首次准备配置的Journal额度大于records×unit，被原联合准入拒绝；新隔离配对按合法显式额度创建，未绕过原校验。两项均属于夹具配置/投影错误，本轮产品代码未改。

## 原生收盘与现场边界

另一次实际原版Writer两证券实验完成transHisData、2DSB和marker；约0.25秒archive/close返回时，操作系统真实checker线程句柄仍WAIT_TIMEOUT(258)，约10.109秒才退出。qmt-datakit-archive-stop-main-001实际exit0约10.322秒。该观察证明原生归档完成与全部后台线程结束不同，不能用marker或固定延时替代join。线程方案独立复核见build/qmt-writer-checker-design-001/REVIEW.md；框架差异尚未实施或获本次批准。

本轮通过Computer Use只读刷新并激活QMT窗口；首次激活失败，经刷新引用后一次恢复。截图确认GH_WT_MEMORY_VERIFY仍停止中，未点击运行/停止、未改正文或重启终端。今天原Formula日志只读分类仍见01:34:36停止成功/订阅实例未找到，未据此证明自有I/O退出。当前真实QMT两代账户、持续全推及终端停止恢复仍待验证，合成组合不替代它们。

整体目标active：历史5338证券最终目录/抽样读取已完成；真实持续采集、完整交易恢复、观衡独立发行继续。本轮真实下单/撤单0、未生产切换、未修改WT核心。

## 入口格式整理后的身份

实际运行后仅对三份夹具做Ruff格式整理。qmt-resident-installed-fixture-style-main-001实际exit0；三份AST逐一相同，目标3.6.8另确认源端语法，行为证据按同一AST复用。当前SHA依次e305287cfbed1e7b315b1b02cae08eb145dba6cc06081cd3a75eeff859aba344、4be25880d0bf9b376b00fc8d741caf3c1ec2b3d11727090aceb25c1949926ade、7170d59eb11228159fd0bdf4d1aedffb113ec840b7a81c98454b0bb645f977c2；上文旧SHA继续指向实际执行字节，未改写其身份。
