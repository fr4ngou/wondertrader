# 2026-10-27 股票及 ETF 长区间批量导入

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：两证券的真实长区间传输、WT 原生存储和全部行回读通过；完整市场历史和策略消费继续。前序为[真实月窗](2026-10-27-qmt-bulk-real-month.md)。

## 真实结果

两次请求都明确指定 2021-11-01 00:00 至 2026-10-26 23:59、max_rows=400000。实际供应商返回范围如下，范围来自首末 CSV 行：

| 证券 | 实际行数/页数 | 首条 | 末条 | 读取 / 导入并全量回读 |
|---|---:|---|---|---|
| 000001.SZ | 287966 / 288 | 2021-11-01 09:31 +08:00 | 2026-10-21 15:00 +08:00 | 83.72秒 / 31.28秒 |
| 510300.SH | 13980 / 14 | 2026-07-28 09:31 +08:00 | 2026-10-26 11:30 +08:00 | 6.39秒 / 1.82秒 |

已实际贯通 QMT 策略原线程只读 API → 命名 SHM → Host 分页 CSV/QMI → 自有原生 C++ bulk CLI → 原 Importer/WtDtHelper → DSB → 原生 source Reader。共301946行的时间与 OHLC/volume/amount 六字段逐行完全相等，元数据保留来源值与 unknown 单位/分钟边界，coverage=unknown。ETF 当前返回范围短于请求范围；本结果证明当前返回内容的传输与存储一致性，完整日历与历史库存继续定位。未用通达信作对照。

## 可核实材料

- 实际句柄、CLI、原生回读及范围摘要（外部历史/待归仓路径：`../../build/qmt-bulk-live-main-001/FULL-RESULT.json`）。
- 配对摘要（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-full-001/PREPARED.json`），profile SHA256 3830338c48bc62e93ab279c4f71f4965f760d0670a83931dbd6f57f42e47561d。
- 股票 WT 原生存储（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-full-001/private/wt-stock-full-001/store`）及回读结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-full-001/private/wt-stock-full-001/RESULT.json`）。
- ETF WT 原生存储（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-full-001/private/wt-etf-full-001/store`）及回读结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-full-001/private/wt-etf-full-001/RESULT.json`）。

两次 CLI 和两次导入回读均 exit0/callbacks或reader正常收口；Host root57816/child由控制器记录，350.54秒正常exit0，stop_seen与observer_joined均true。五个受控进程的原Job、整树退出、双EOF、读线程join与资源关闭均通过，未使用强制终止，无控制台窗口。根自行操作原 GH_WT_MEMORY_VERIFY 行，最后已点击停止；原有其他策略与 TRIN 编辑器保持。安装正文 SHA256 5112d5391d5b776c28f0fc0f041b82f7e96de6721dd4d1b060743261dfc4258b；其前版逐字备份保存在本轮 private 目录。

全历史 CLI 私有配置输出额度已按实际 C++ 准入上限修正为256MiB，前后摘要与说明（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-full-001/CLI-BUDGET-REVISION-001.json`）保留；配对/profile不受影响。本轮没有新增 WT 框架修改、旧 QMT 工程执行依赖、真实委托或生产切换。

## 后续主路径

继续完成多证券作业与历史库存识别、接入策略/观衡读取和系统统一发行入口；核实际源范围缺口，保留请求范围与实际观察范围的区别。常驻跨实际断连、账户四类查询、查询优先完整交易恢复与全部保留业务仍未完成。按[开发顺序](../development/workflow.md#主路径优先)，整体模块主路径完成后集中处理边界、恢复测试和代码评审；本记录不授生产资格。

## 缓存位置后续定位

根已只读找到本机实际分钟缓存：D:/software/guoxin/datadir/SZ/60/000001.DAT 为18429832字节（2026-10-22更新），D:/software/guoxin/datadir/SH/60/510300.DAT 为894728字节（2026-10-26更新）。SZ/60与SH/60目录分别观察到2950与2392项。文件元数据（外部历史/待归仓路径：`../../build/qmt-bulk-live-main-001/CACHE-INVENTORY-001.json`）只记录文件大小和时间，未解析供应商私有格式，不据此授完整市场覆盖。源端实际调用明确使用两端日期、count=max_rows+1、none/fill_data=False/subscribe=False；ETF更早库存及下载范围继续核实。
