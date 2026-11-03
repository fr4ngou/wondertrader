# 观衡a106策略选择与精简页面上线

类型：独立观衡正式发布记录。日期：2026-11-04（北京时间）。状态：已独立安装、切换18143并完成实际主链验收。

## 当前入口与身份

入口：<http://127.0.0.1:18143/backtests>；策略页：<http://127.0.0.1:18143/strategies>。版本`0.1.0a106+strategypages.1`，源码`1de69df67e543bfb1a356e11a1d84b3df46e9c87`，注释标签`observer/0.1.0a106+strategypages.1`。业务源码由Root按42份CAS接收为`a5865e3`，后继仅修改App的pyproject和uv.lock版本。

程序安装在`E:/workspace/wondertrader-data/observer-programs/0.1.0a106+strategypages.1/`，解释器为其`runtime/app/venv/Scripts/python.exe`，维护工具为`payload/observer-web.py`。全部本轮构建、安装、控制、日志及导出输出位于E盘。旧a105安装与专用配置保留用于回退。

稳定指针：`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`。最终源profile：`E:/workspace/wondertrader-data/observer-web-a106-strategypages-20261103-001/formal-002/web-profile.json`，SHA256 `542eba1ed01042a4cc1743f60c19e7102ece1c552ea3217cc4ee2bc0a1660084`。Web PID12316、启动器23024、控制ID`6cc0f307-c4b4-42ba-b93f-12950451e540`，当前原维护入口status为ready。

## 本次可用行为

策略页明确选择实际登记策略，运行详情校验所选ID和版本；“查看该策略回测”进入该策略报告列表。同策略报告可选择主报告和对比报告，进一步进入曲线、日期持仓盈亏和成交明细。未知策略与无效比较链接要求重新选择。全部日常页面移除来源/口径说明及同类折叠入口，日期净值表、单位、数据时间及错误/缺口状态保留。

正式页已核3份实际归档、403期主报告、12万元比较报告、2026-06-09三项日末持仓及原浮盈、101笔成交的3页分页（末页1笔）。策略页实际展示5项持仓、原100万元运行基准、现金及可用633,075.20元；状态为“运行中·等待新行情”。这组事实取自Root恢复后的原策略发布，当前Root策略尚待首轮自然行情计算。

总览、账户、交易记录、系统状态、行情、观察看板、指标说明、更新缺口及导出入口已按实际数据检查。日线60根、分钟2000根至2026-11-03 15:00、68817即时搜索9项候选、原3项自选、上证/RANA/MSI/T2108/推力/TRIN组图及72项观察资料继续可读。手机390像素无页面横向溢出，日期明细位于曲线下方；最终页面控制台错误/警告为0。

T2108导出页面参数及按钮可用，按同一接口和日期范围实际导出44行22列CSV并保存E盘，响应快照与请求一致。浏览器工具不支持指定下载目录，本轮保留已验前端下载合同与回归，浏览器文件保存动作未另行触发；实际文件使用同一导出API写入E盘。

## 构建、安装与审查

从上述固定提交的独立干净源码构建，486项永久输入及249项前端/共享输入保持身份。沿固定CPython3.12.13、Node24.18.0、Flit及原第三方/离线npm锁生成6个私有wheel和SPA；构建与安装均exit0，pip check通过。原业务回归和边界证据按输入复用，后端App的134份模块/资料与a105逐字节相同。

| 制品 | SHA256 |
|---|---|
| 独立ZIP | `d291b94cb199e8570b900ea8d75dfdcd24f2c4d4d24cd763b39e21ab1ab320b1` |
| OBSERVER-RUNTIME.json | `7b936797ac777b7b0a73f58318f452900bbd57d0678dbded370ca874b6f310dd` |
| 角色制品清单 | `2fe7382d91336d6b13cef4bb70d481298a4ff55f837af8be60a47a3338b2db56` |
| 安装收据 | `89d93198999ea5b5318744bf7deef22afa88fa07840cd977c117232d776efaf6` |

实际HTML加载`assets/index-Dt188D5K.js`，HTTP字节与已安装SPA一致。独立需求及规范评审核对注释标签、源输入、包、安装文件、profile、读取配置及回退边界，开放P1/P2为0；正式账户绑定后继另有delta复核。原560项扩大回归中的30个既有失败及文档检查的基线缺失引用沿[模块证据](../evidence/2026-11-03-strategy-selection-source-cleanup.md)登记，本次未重复无变化测试。

## 实际读取绑定与独立性

先从a105沿用原读取配置并更新额外日线实例目录。行情与历史WT采用运行侧`wt-retained-quote-prepared-20261102-001/ACTUAL-DEPLOYMENT.json`的当前data角色，控制ID`92ef0edb-8d96-4e18-ab47-24233ea2bcc1`；其他3个额外实例逐值保留。

随后接收Root的`daily-mainline-20261103-001/FORMAL-CURRENT.json`，在新profile中更新主账户四身份引用。正式WT control为`43a02121-cf9c-4104-ac24-fc5baabeebc3`，instance仍为`a309716d-1288-4328-ac57-abd6ef0bb2e9`，配置SHA为`311c5b356540530cea332be1cb4d100a781835b60a40abc9fc9f40ce4d5d7e80`。其余环境值、行情凭据、观察数据、个人自选与归档根保持。

a105及首代a106均沿原维护入口正常关闭：shutdown_complete=true，两读取池线程为0，Web解释器与启动器OS exit均0。a106正式绑定后正常启动。独立停止期间，数据owner16440、历史41220、更新监督42932及子44840保持原PID和创建时间；同版重启时Root Native68356同样保持。观衡生命周期没有启动、关闭或重置WT及市场更新。

## 启停与回退

沿[独立Web维护手册](../runbooks/observer-runtime.md#隐藏-web-的启动查询正常停止与重启)，从当前DEPLOYMENT读取`python`、`tool`、`source_profile`，通过对应`status/start/stop/restart --profile`维护本版。正常停止保持WT和公开更新运行。运行中的源profile与环境文件保持原摘要，绑定变化采用新profile和新控制目录。

回退配置：`E:/workspace/wondertrader-data/observer-web-a106-strategypages-20261103-001/formal-002/rollback-a105-profile.json`。先沿当前源profile正常停止a106，再使用保留的a105解释器和工具启动这个回退profile；它采用当前正式账户与日线读取绑定，保留同一个人目录及原数据根。旧版继续原报告展示，其前端包含此前来源说明；新策略列表需重新采用a106。当前未实际切回a105，后端逐文件一致及原维护合同证明本次没有数据格式迁移。

## 交付与后继

本轮独立观衡发布与页面接收已完成。开发阶段18484、18485、18489三个自有预览已退出，正式18143保留。旧工作树及构建原件作为接收证据保留，后续清理由Root按引用核对。

Root继续唯一正式策略的自然输入、自动执行与交易结果验收。WT日常重启后自动跟随当前实例的只读接线，按[服务控制契约](../specs/wt-service-control.md)作为下一独立功能增量开发；a106使用本次明确核验的固定绑定。

本轮原件根：`E:/workspace/wondertrader-qa/observer-a106-live-20261103-001/`。包含SOURCE-BUILD、ZIP、安装日志、两代Web closed/ready、稳定部署指针、FORMAL-BINDING-002、LIFECYCLE-RESULT、独立评审、实际页面记录、桌面/手机截图及EXPORT-RESULT。启停、回退和日常操作维护于[操作员手册](../runbooks/guanheng-operator.md)。
