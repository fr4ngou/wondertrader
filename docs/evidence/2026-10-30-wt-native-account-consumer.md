# 独立 WT 原生账户消费者的真实四查询

类型：实际运行证据。日期：2026-10-30。范围：QAR 原生只读消费主链，整体系统继续开发。

## 完整入口与复用

本轮沿 `build/wt-native-account-consumer-001/main.py --mode real` 运行：离线候选003的普通 WT 安装通过公开 CLI 管理原 `qmt_read` Host，真实 Windows 共享内存连接原 QMT 策略线程，再由普通 `GuanhengAccountScan.exe`、`TraderQMTReadOnly.dll`、原 TraderAdapter 和既有金融 mapper 完成 position→order→deal→account 查询。观衡 App 未参与进程管理。

原生 EXE 与 DLL 沿冻结安装逐字复制；基础资料沿已核实际证券资料，适配保留 `qmt.read-profile.v3`、`qmt.account-read.v1` policy 1.0 及原账户绑定。没有增加金融投影规则、持仓计算、数据库或 WT 框架修改。实际金融原行和配对凭据留在本轮 `real/private`。

## 实际结果

| 项目 | 本轮事实 |
|---|---|
| 四类原生观察 | 4条持仓、0条委托、0条成交、1条账户资金；四批 delivered |
| 原生完成帧 | `guanheng.account-scan.v2`，closed/joined=true、worker_live=false、queued=0、error_code=ok |
| 原生耗时 | 20,177 ms，退出码0 |
| 内外进程 | Scan27940、实际WT43212、Host48516、WT启动包装32320及外层60848正常退出；控制器29328退出码0 |
| 完整回收 | 内外Job均tree_zero、双EOF、reader joined、resources_closed；forced=false |
| 外层总耗时 | 59.180秒，包含根会话现场启停及恢复；总预算600秒 |
| 输入 | 160份本轮运行输入前后SHA一致；全安装闭包身份沿另行安装收据核实 |
| 副作用 | 真实下单0、撤单0、生产切换0 |

实际启动命令为 `C:/Python314/pythonw.exe -B E:/workspace/wondertrader/build/wt-native-account-consumer-001/control-real-main/control.py build`。控制器创建期加入2 GiB Job，自身无控制台。最终结果位于 `real/RESULT.json`，外层结果位于 `control-real-main/build-trade-product-main009/RESULT.json`。

QMT临时复用已停止的原 `SHM_READ_PROBE`，未增加策略。原正文SHA为 `35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae`；本轮只读正文SHA为 `b44e68e9f5aa2e315d7ea41d619859921792b03f364647bc2721c456fcfd951e`。Formula实际记录04:46:09 doRun、04:46:47 stop success；根随后逐字恢复原正文，并写入 `real/PROBE-STOPPED.json`，之后原WT入口正常关闭Host。源运行事件、实际查询和磁盘正文恢复分别记录。

## 既有数据运行保持

完成后，现有 WT33636、HPR Host46288、历史60964、采集75000仍存活；原采集状态connected=true、generation=1、receiver_heartbeats=1540、overflows=0、queue_depth=0。当前闭市，writer_processed=0保持其原边界；本轮不授开市新增分钟或跨日采集资格。ETF批次继续由《杂役》沿同一控制器处理。

## 资格与剩余

本结果证明实际 QMT→SHM→普通 Host→原生 C++ 只读插件/Adapter→原生 Scan 完成帧可用，并正常退出。原值/身份、请求SHA与Journal只读逐项审计沿[模块交付](2026-10-30-native-account-consumer.md)登记。先行交付 `build/wt-native-account-consumer-001/DELIVERY-001.json` SHA为 `814d95fb231d351eb8c284f44a8132b3a38ed7776c32ee81d8d0984de59bfe8a`。真实67项数值/身份事实中63项精确一致，4个浮点事实差1 ULP，最大绝对差约4.55e-13；19个资金余额/可用、持仓数量/可卖ABI槽精确一致，原4次请求身份、结果SHA、执行区间及绑定一致。严格原值审计明确保持failed，未以容差替代。

冻结RapidJSON头的定向复现已将全部36个数值槽的默认解析/写出结果与实际原生输出对应，4处1 ULP误差可复现；FullPrecision解析往返为0处改变。根因位于自有JSON读取边界，后继统一修正须覆盖Common终态读取、Bootstrap映射读取和Scan复制视图读取三处，不涉及WT框架。后继新制品及精度修正验收继续，旧制品主链及差异均保留。SDK替身与真实来源的原值资格分别记录。

这一次四批查询各有执行时间，未承诺券商事务快照。空委托、空成交未覆盖真实非空订单字段。原生成功仍需交给独立观衡账户消费者和中文页面做实际显示验收，常驻组合、重连恢复、唯一策略执行及系统发布继续。先前真实004/run002恢复异常的根因仍为unknown；本轮成功不构成该故障修复证据。

适用规格：[QMT共享内存账户只读接入](../specs/qmt-shm-account-read.md)、[原生账户展示](../specs/native-account-console.md)。相邻已验入口：[普通独立WT真实五类读取](2026-10-30-wt-real-readonly-main.md)。
