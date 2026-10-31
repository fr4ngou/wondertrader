# 独立WT实际接管历史Host与数据服务

类型：开发实例交接及真实只读调用证据。范围：[WRI](../specs/independent-wt-runtime.md)的数据和通信组合。结果：三组件实际常驻、原请求恢复及历史读取通过；完整交易组合继续开发，未发布生产。

## 实际行为与身份

前置[装配准备](2026-10-30-wt-host-data-preparation.md)完成后，下载所有者提供`build/qmt-etf-history-001/HPR-HANDOFF-001.json`：本批240请求均终态，原Journal的743条记录均终态，无在途或未知请求，并暂停新prepare。沿原owner停止标记关闭原HPR，核原closed及控制器exit0/完整回收；沿原WT停止契约关闭旧数据实例，核components_closed及真实进程退出后，启动新三组件实例。

准备记录中的61052是原外部owner，实际HPR子进程为42648。二者及原控制器均已退出；原数据WT74964、history27980、collector30588及其启动器8540也已退出。原件分别见新根`OLD-HPR-CLOSED-001.json`、`OLD-DATA-CLOSED-001.json`和`PROCESS-OBSERVATION-001.json`。

| 项目 | 本次实际值 |
|---|---|
| 准备及运行根 | `build/wt-live-host-data-composition-001` |
| 普通安装WT入口 | `build/wt-runtime-installation-001/final002/installed001/roles/wt/venv/Scripts/pythonw.exe` |
| 配置SHA256 | `a16094bf7df3f985757f5f515b8778edd0916958f4d871df77e01aa4a7c409fa` |
| instance_id / control_id | `d836f5f5-6c83-41d5-a93d-0c8cbdf343ec` / `12b10e4e-43ef-404a-a24b-dfb1f042d828` |
| 实际WT / HPR / history / collection PID | `72824 / 38432 / 4408 / 56840` |
| 活动只读连接资料 | 新根`ACTIVE-READ-CONNECTION.json`，准备时的`READ-CONNECTION.json`原件保留 |
| 统一原生存储 | `E:/workspace/wondertrader-data/wt-live-20261030-001/storage` |
| 历史只读地址 | `http://127.0.0.1:18130` |

原QMT策略、正文、共享内存名称、pair、客户端、凭据及通信SQLite均沿原值。Journal继续由原Host按协议写入；没有复制或清空Journal、换ID重发旧下载或添加第二套业务事实。WT独立入口拥有HPR、历史和采集owner，观衡继续只读独立部署。

## 真实调用及持续状态

新HPR认证后，按原请求`bc731c77-0f5f-4918-b322-1588ce1bffe8`执行GET，确认原cohort003的159560.SZ准备结果仍为terminal，原请求摘要和结果字节均保持。新建一次只读`market.history_1m`请求`3086f30e-9780-4846-8b03-b0918bd8d9e6`，其后只按原ID GET恢复，未创建替代请求。

请求510300.SH的2026-10-29 14:56–15:00、最多5根，QMT实际返回4根，`fill_data=false`。时间有序且唯一；14:59未返回，本次保留源端实际记录，不由该读取结果判断缺数原因。原验收脚本把上限误作精确行数，后继脚本已修正。`POST-READ-001.json`还证明WT原生查询返回5根，与此前实际SDK基准逐字段一致；来源接口与原生存储两个读取口径分别记录，不宣称它们的成交量定义或行数相同。

control415实际0.656秒exit0，Job树0、stdout/stderr EOF、reader join和句柄回收全部通过。期间QMT正文修改、下载新请求、下单和撤单均为0。原件为`post_read002.py`、`READ-REQUEST-001.json`、`SOURCE-READ-001.json`、`NATIVE-READ-001.json`、`POST-READ-001.json`及`build/guanheng-workspace/wt-data-live-read-control-415/build-wt-data-live-read-control-415/result.json`。

后继现场核四个实际PID均存在，旧八个PID均缺席；collector仍connected、generation=1，已接收/投递6929报价，心跳由415继续到526。当前闭市，writer_processed=0；本观察证明连接持续，不授予本次实例开市新增分钟或自然收盘归档资格。`QUOTE-OBSERVATION-001.json`固定后一次观察。

验证完成后，已向下载所有者交接活动连接资料并解除新prepare暂停，沿原请求身份恢复ETF及50指数剩余批次。

## 启动失败与边界

首个启动入口误将随机QST密钥按UTF-8解码，创建任何WT组件之前失败。修正后的入口直接按原`secret_encoding=base64`约定传入原环境值；凭据原件和产品代码保持。首轮失败、后继入口及准备快照全部保留。Windows启动包装器14168的exit0只代表包装器结束，实际WT72824仍常驻；本次没有停止新WT或把包装器退出当成完整关闭证明。

独立交易Host产品、同一正文下交易/QST/HPR共存、真实只读账户及原生执行整链仍待完成；本证据不覆盖真实下撤单、完整策略连续性、生产切换或新WT关闭资格。此次新增WT框架修改为0。审查及最终输入摘要沿本根DELIVERY与后继review收据登记。

