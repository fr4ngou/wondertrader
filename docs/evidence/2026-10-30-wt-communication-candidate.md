# 独立WT通信、行情与原生账户统一候选

类型：开发候选装配、普通离线安装及完整SDK主链证据。日期：2026-10-30。范围：SRI/WRI/QAC运行侧组合；观衡、策略执行和生产发布分别交付。

## 输入与原能力复用

`build/wt-trade-system-candidate-004`采用原SRI v2接口装配，角色输入为已审QAC `installation003`：Host 0.1.0a4、Agent 0.1.0a3、WT运行0.1.0a2及原市场客户端0.15.0。行情组件保持原候选manifest `228cd7f9021a7396252253f733e03be44106b820cc67235a6cbe9878f0113919`。原独立账户精度包通过已有`additional_components.native_account`接入，其13份材料、许可证和构建来源保持原字节。

安装仅选择Host/WT，不安装观衡或SPA。原Parser/Writer/Reader、只读Trader/Adapter及通信协议继续负责业务；本轮没有新增产品接口、WT框架修改、账户计算或订单账本。独立观衡继续读取WT发布的原业务观察。

## ZIP到新目录运行

`package.py`使用原create→extract→包内install→resolve流程生成1213项受管文件的development候选，在新目录`installed001`从预建wheel离线安装。接收端不构建产品源码、没有registry访问。外层247.617秒exit0，Job、双EOF、读取线程和句柄全部正常回收。固定输入、清单、ZIP及入口见模块根`SYSTEM-INPUTS-001.json`、`SYSTEM-CREATE-001.json`、`SYSTEM-INSTALL-001.json`和`SYSTEM-PATHS-001.json`。

`qa`冻结原QAC验收入口，仅改变工作目录、安装根、行情组件根和账户程序来源；业务顺序保持。账户准备从本次`installed001/payload/components/native_account/app`逐字复制实际EXE/DLL，来源和SHA均核实；没有从编译目录取程序。原生制品为已审`5dae6960…` Scan及`27e92a99…`只读Trader。

## 同安装完整主链

`main001`从公开WT CLI运行HPR、交易、只读账户、历史和采集五个原owner；单个实际Python3.6.8进程运行正式四连接正文。两代只读认证及两轮原生四查询均成功，130项事实、60个ABI槽及浮点位模式与原Journal一致。原代I/O已退休，其他连接及五组件PID保持。

同一次运行完成交易侧账户查询、单笔SDK下单→查单→撤单、原HPR补齐及回读、QST→原Writer的两根分钟DSB，以及原Reader五根真实历史前后同值。内置正文文件/网络守卫调用0，原SDK线程、单timer及单订阅保持。实际QMT及真实下撤单均为0。

外层23.677秒exit0，1253份运行输入前后一致。原生、源进程、WT和五owner均正常关闭，Job整树0、双EOF、线程join和资源关闭成立。`postcheck001`在整链后再次通过包内公开resolve，返回路径及安装身份与原结果一致，37.766秒；额外核实包内原生文件和实际运行副本相同，没有增加来源请求。

## 资格与剩余工作

本候选证明新通信代码、原行情组件和精度修正版账户制品在同一份普通离线安装中完整运行。QAC原`main002`交易Host超时仍按原失败保留，原因unknown；本次通过没有修复该原因，也没有重发原未知命令。

真实QMT四连接正文、唯一策略及账户发布、观衡页面消费、完整恢复和系统发布继续沿各自调用链验收。本轮没有切换数据WT33636、重启QMT或修改正在工作的下载；开发包不表示生产切换完成。

独立组合复核沿模块根`review001`最终输入及报告登记；整系统目标继续active。参照[QAC整模块](2026-10-30-qmt-account-composed-source.md)、[精度新制品真实读取](2026-10-30-wt-native-account-fixed-diagnostic.md)及[系统安装规格](../specs/system-runtime-installation.md)。
