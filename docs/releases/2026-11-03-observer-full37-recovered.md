# 观衡a104接收Full37与查询容量恢复

类型：本机独立交付后继。核实时点：2026-11-03 21:08（北京时间）。状态：只读页面主链已恢复，自动交易保持关闭。本记录接续[Full34故障记录](2026-11-03-observer-full34-current.md)和[缓存分钟补齐](2026-11-03-observer-cached-minute-prefix.md)，两份历史记录保留当时事实。

## 用户入口和独立归属

用户入口为 <http://127.0.0.1:18143/>。观衡使用既有 `0.1.0a104+chartlabel.1` 安装，本轮只更新四项正式WT读取定位。行情仍连接独立WT18149，三项自选、观察数据根、报告目录及其他实例定位保持。

| 角色 | 当前身份 | 职责 |
|---|---|---|
| 观衡Web | PID12204，控制`dc0092bc-7b58-47a1-8ca0-75abe8f81257` | 只读展示；独立启动、停止和升级 |
| 正式WT Full37 | 启动器PID66544，控制`86a43963-34b5-4bf6-a796-51b0fa67671c` | 管理账户通信、账户发布、交易通信、历史及执行组件 |
| WT历史18149 | PID41220，控制`95347937-723b-4f1d-8a20-7aa38b684be5` | 纯文件历史查询，包含六份新增早期分钟来源 |
| 公开资料更新a103 | 监督者PID42932、子进程44840 | 独立31来源更新；09:00、17:30、21:00北京时间窗口 |
| 原采集 | owner29056、采集69884 | 原分钟采集；创建时间保持11月2日23:11，本轮未重启 |

21:06实际OS进程仍存在；21:07再次核对Full37五个组件均为ready。执行组件已初始化，业务状态为等待有效策略行情输入；运行ready与自动执行资格分别登记。观衡关闭不会关闭上述WT或更新角色。

稳定Web定位为 `E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`。当前源Profile为 `observer-web-a104-full37-20261103-001/web-profile.json`，SHA256为 `c5d468b23f58ff1b636464d7280f1a85e6b3fb402e62ea3ce63a6b8c3fe7790d`。

Full37配置为 `E:/workspace/wondertrader-data/strategy-capital-real-20261102-001/private-039/runtime-full37.json`，SHA256为 `69f0254afe1708e2b71e116ff3dde262e5d3ba18a7b7697548ca9b8c4282d904`；实例ID为 `a309716d-1288-4328-ac57-abd6ef0bb2e9`。原QMT正文SHA256保持 `7769651b16510e8cb975774591df1ef9fb23ca394291672a4bb5fcf524ce2142`。

## 根因及已接收实现

原通信库3586条已完成读请求实际正文与结果合计8,063,115字节，仍按请求最大预留量占用999,964,639字节，接近原1,000,000,000字节上限。新查询在登记前被拒绝，后续按原请求查结果得到404，最终阻断执行读取。容量问题属于通信宿主的读结果保留与计费。

接收的自有接入修正为 `d7a6639` 和 `1719da9`：

- 提交结果未知时沿原请求ID、原正文及原绝对截止接续；明确符合条件的未知404只重试同一读取身份，普通结果恢复继续查询原ID。
- Host显式持有HTTP读结果的消费与回收责任；在途请求保留最大预留，终态请求按正文、结果及16,384字节元数据余量计费。沿用既有读取、消费确认和回收契约。
- 原旧行、请求身份、正文、结果和绑定保持；原`reserved_bytes`列保持，实际计费使用新逻辑。旧版默认路径及Source配置保持，原1GB预算保持。

本批12份源码/规格按开发者2最终CAS接收，两个独立审查无P1/P2；安装态Host与两代SDK替身证据已接收。Host为 `0.1.0a22+host.httpretention.2`，安装于 `E:/workspace/wondertrader-data/host-http-retention-20261103-002/venv/`。本批全部为自有Host/Common接入与文档，WT框架文件未改动。

21:07真实原库复核：3586条旧记录不可变字段SHA256仍为 `7d3e9c16e78157cf141336e73c36c978a8c0a08dc7a25887d919971c07ab0d7a`；有效占用66,853,431字节。20:45至21:07，新查询最大序号由3653推进到3737，保留的新读记录仍为2条。真实连续查询及消费回收已发生，容量保持有界；正式`trade_commands=0`。

## 实际页面和资金

| 页面主链 | 本次真实结果 |
|---|---|
| 搜索与自选 | 输入`68817`即出现德龙激光、纬德信息等9项下拉候选，无需点击搜索；名称和类型保持 |
| 行情 | 默认最近60个交易日日线；原分钟2000根可读，实际尾部至11月3日15:00；390px策略页无横向溢出 |
| 策略与账户 | 现金及可用633,075.20元，五项持仓、市值364,971.30元、净值998,046.50元；账户发布完整返回5持仓、2委托、1成交、1资金 |
| 系统状态 | 正式WT五组件及额外独立历史/行情实例就绪，真实页面无失败或停止提示 |
| 市场观察 | 上证背景、RANA/MSI、T2108、Breadth Thrust和TRIN实值可见，广度资料准确标至11月2日 |
| 回测报告 | 可选`31ae0805c4b9468d8240f7af1d75bdcd`，403条日末记录，截至11月2日；切换旧报告比较可用 |

资金基准沿用户确认的当前总资本100万元，包含现有库存。全账户可用199,529,589.27元与策略现金分开。五项库存及理论资金账沿原`financial-state-006`、`initial-inventory-006`恢复，价格来源时间保持11月3日14:59:22.629。旧交易历史、原开仓日期及历史收益率保持未迁移。

新报告末净值1,027,489.80元、收益2.74898%、日末最大回撤22.92086642%；费用29,299元仍为原模拟数量费率，实际券商费率尚未校准。页面浏览器异常为0；本轮是读取接收验收，图形化回测重设计由开发者1独立按设计流程推进。

## 历史覆盖与更新边界

沿[缓存补齐记录](2026-11-03-observer-cached-minute-prefix.md)保留5338项基础分钟、57项日线登记及新增603,372根早期分钟。新增为12只ETF和创业板指，实际起点2025-10-28；三个股票的2021-11-01窗口可读。ETF缺失的2021—2025区间及重叠版本原值修订仍分别登记，完整缓存候选保留离线，当前只追加原首日之前的六份来源。

统一历史实例仍使用 `E:/workspace/wondertrader-data/wt-cached-prefix-20261103-001/DEPLOYMENT.json`，配置SHA256 `efe4194e6622adf3b531563bd9d3b5989bb34b49c3437770d95c5542b7e52567`。历史文件及当前查询服务独立于观衡和正式交易实例。

独立21:00公开更新已自然完成，页面记录完成时间21:03:48、部分来源待补；21:07当前观察快照为 `1cafd0b9ed1a9e6fef8b7da0d99e05ab283e44cd7bcc471e0644846e7214a61a`。广度及T2108本次页面仍至11月2日，按实际观察日展示；不能以更新完成时间替代数值日期。逐指标较长覆盖继续沿原件和已有72组覆盖表核对。

## 启动、停止及回退

当前实例已启动，重复验收直接访问上述地址。Web维护使用稳定部署指针里的解释器、工具和Profile；以下命令用于本机维护，当前轮未再次执行启停：

```powershell
$observerDeployment = Get-Content -Raw 'E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json' | ConvertFrom-Json
& $observerDeployment.python -I -B $observerDeployment.tool status --profile $observerDeployment.profile
# 需要正常停止或重启时，使用同一组参数，将status换成stop或start。
```

Web启停完整语义沿[独立Web手册](../runbooks/observer-runtime.md#隐藏-web-的启动查询正常停止与重启)。回退Web时先正常停止当前代，保留关闭回执，再以目标发行、新控制目录及经核实的当前WT读取定位启动；`DEPLOYMENT-BEFORE-A104-FULL37.json`保留前代Profile。前代绑定Full34故障实例，直接采用旧定位会重新显示旧故障。个人自选、观察目录及报告不随Web回退替换。

正式WT启动使用 `PREPARED-full37.json` 中的固定pythonw、configuration、configuration_sha256与环境，按[WT独立运行手册](../runbooks/wt-independent-runtime.md)分配新的control目录和UUID；禁止并行启动同一金融实例。正常停止向当前控制目录原子写入以下内容，再核closed和OS退出；停止由运行owner执行，本轮Root没有停止WT：

```json
{
  "schema": "guanheng.wt-runtime-stop.v1",
  "control_id": "86a43963-34b5-4bf6-a796-51b0fa67671c",
  "instance_id": "a309716d-1288-4328-ac57-abd6ef0bb2e9",
  "configuration_sha256": "69f0254afe1708e2b71e116ff3dde262e5d3ba18a7b7697548ca9b8c4282d904"
}
```

历史18149与更新a103各沿自己的部署定位及控制身份维护。通信修正回退前保留原库与保留结果，核目标版本能否识别当前保留状态；旧Host仍存在原预留容量问题，不能将版本回退视为容量恢复。未知结果沿原ID查询，金融账本保持原件，不因程序回退重置。

## 剩余主线和证据

正式策略当前等待有效策略输入，全部金融写开关保持关闭。离线同账只读到enabled的两代SDK主链已通过；最终现场模拟自动执行、最新策略输入与页面同事实组合仍须交易owner完成。当前OAR只读交付和这项自动执行资格分别核算，Root本轮未操作QMT、调用终端SDK或发送订单/撤单。

本机原件集中在 `E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001/`：`HTTP-RETENTION-SOURCE-RECEIVED.json`、`RETENTION-CAPACITY-COPY-RECEIVED.json`、`FULL37-LIVE-RETENTION-001.json`、`FULL37-LIVE-RETENTION-002.json`、`A104-FULL37-PREFLIGHT.json`、`A104-FULL37-WEB-DEPLOYED.json`及`a104-full37-actual-browser/RESULT.json`和页面截图。运行材料位于 `strategy-capital-handoff-20261102-001/PREPARED-full37.json`、`STARTED-full37.json`及`retention-038/`的最终CAS、Host交付与两份独立审查。
