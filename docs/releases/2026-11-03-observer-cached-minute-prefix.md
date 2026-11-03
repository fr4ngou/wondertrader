# 已缓存ETF分钟历史补齐及独立查询接收

类型：本机数据接收与独立读取部署。日期：2026-11-03 19:20（北京时间）。状态：603,372根更早分钟已导入并通过实际页面接口读取；策略执行故障及自动交易接线独立继续。

## 已完成范围

当前观衡仍为 `0.1.0a104+chartlabel.1`，入口 <http://127.0.0.1:18143/market>。默认60日日线、分时2000根、三项个人自选、原报告和账户读取保持。历史连接现为独立WT18149；该实例仅持有history组件，全部输入为原本地DAT导入及既有WT归档，无QMT终端SDK或网络下载。

沿当前源配置核对338份完整导入收据SHA，匹配全部5338项基础分钟证券及57项日线登记。三个股票的2021-11-01分钟窗口已通过现有App实际HTTP读取。510300在该窗口为空；本机当前510300和588170的DAT实际均从2025-10-28 14:31开始，不能宣称ETF已覆盖2021年。

先将两只ETF当前缓存117,736根转为WT原生格式，并按完整旧store成员闭包准备32项2,562,677根候选，实际Native Reader全量回读确认原分钟标签未丢失。重叠比较发现旧版本与当前缓存存在原值修订；完整替换候选在原采集合并契约下触发冲突，未接到观衡。该独立候选已正常关闭、OS退出0，原缓存、旧DSB和原18148保持。

最终接线复用现有 `source-collected.supplements`，仅导入严格早于各基础源首日的区间，共六个成功store、13项证券、603,372根。完整新缓存版本保留为离线核查材料；本次不覆盖原分钟、不改原冲突规则、不改WT框架。最终选择仍按原来源分段、同值去重及异值报告，coverage和未知单位保持。

| 当前新增的早期区间截止 | 证券 | 导入根数 |
|---|---|---:|
| 2026-10-15 | 510050.SH | 56,183 |
| 2026-09-08 | 510500.SH、563680.SH、588170.SH | 153,366 |
| 2026-06-22 | 515080.SH、588010.SH、515310.SH | 112,878 |
| 2026-08-23 | 589000.SH、589680.SH、512100.SH、588000.SH | 192,920 |
| 2026-07-30 | 399006.SZ | 44,374 |
| 2026-07-27 | 510300.SH | 43,651 |

上述窗口实际起点均为2025-10-28来源标签，截止按各证券原首日之前一天选取；日期上界不代表该日必有交易。12只ETF与创业板指的实际新增早期窗口均经原App公开HTTP返回2根有效分钟。两只ETF原2000根查询仍至11月3日15:00；五类指数及原股票/ETF共七项日线60根读取通过。指数参考日仍至11月2日，未用配置切换改写数据末日。

## 当前维护定位

- Web：PID58492，控制 `09fe8198-b033-478f-bf46-4d190c3ddf77`，Profile SHA256 `5565bb3270e7bd180486243abc9c66296c3668437376c784a0c5eefe7214ce4c`。稳定维护指针仍为本机 `E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`；源Profile为 `observer-web-a104-prefix-20261103-001/web-profile.json`。
- WT历史：`E:/workspace/wondertrader-data/wt-cached-prefix-20261103-001/DEPLOYMENT.json`，地址18149，PID41220、启动器39348。控制 `95347937-723b-4f1d-8a20-7aa38b684be5`，实例 `d019ee61-c498-4a2c-b3ed-a2a4294bf9ff`，运行配置SHA256 `efe4194e6622adf3b531563bd9d3b5989bb34b49c3437770d95c5542b7e52567`。
- 数据：新增六根位于 `E:/workspace/wondertrader-data/etf-cached-prefix-20261103-001/`；新来源配置SHA256为 `a73ab183c06a2f52782e466721af3c448a2734b26195fa32b39363d41c8d3991`。原基础库、采集目录、日线归档及两份原supplement保持，仅追加六项本地补齐来源。

正常启停分别沿[Web维护手册](../runbooks/observer-runtime.md#隐藏-web-的启动查询正常停止与重启)和[独立WT手册](../runbooks/wt-independent-runtime.md#正常停止及故障)。WT启动使用上述DEPLOYMENT中的固定解释器、runtime配置及私有环境；重启分配新control目录和ID，旧记录保留。停止只向本代控制目录原子发布匹配的stop.json并等待closed与退出，不按进程名停止其它实例。

本次Web先正常关闭前代、再启动同版本新Profile；账户Full34的四项定位与其他三个额外WT定位保持，仅改变行情URL/凭据及统一历史实例定位。Web停止不停止WT历史、交易或公开更新。回退读取时正常停止当前Web，沿保存的 `DEPLOYMENT-BEFORE-A104-PREFIX.json` 和旧Profile启动原a104/18148；旧18148及原数据仍在。新增数据与独立18149保留，可按自己的控制身份正常关闭。本轮未执行回退。

## 当前限制与原件

页面实际验收为默认日线60根、分时2000根、13项新增早期HTTP窗口和分实例状态，pageerror=0；账户Full34故障及可用待更新继续如实显示。资金、持仓、交易生命周期和独立公开更新均未改变；原行情owner29056及采集69884创建时间保持。交易404修正及同账自动执行资格沿原交易模块推进，本记录不授其上线结论。

股票、ETF与指数的缓存范围分别记录，尚缺的2021—2025 ETF分钟不能由本批生成。价格/量额历史修订不静默覆盖；完整缓存候选和原差异保留，后续核查应沿原来源机制。分钟标签沿source_label，价量额未知单位继续unknown。

本机固定证据位于 `E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001/`：CURRENT-HISTORY-CATALOG-RECEIVED.json、CURRENT-HISTORY-CATALOG-MEMBERS.json、CURRENT-HISTORY-2021-HTTP.json、ETF-CACHED-MINUTE-NATIVE-COMPARE.json、ETF-CLOSURE-NATIVE-ALL-MEMBERS.json、CACHED-MINUTE-CANDIDATE-CLOSED.json、ETF-CACHED-PREFIX-CONVERTED.json、CACHED-PREFIX-APP-PREFLIGHT.json、A104-PREFIX-WEB-DEPLOYED.json及a104-prefix-actual-browser/RESULT.json与截图。初次完整替换消费失败保持为失败，不记入最终补齐主链成功。
