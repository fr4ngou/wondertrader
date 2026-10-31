# 2026-10-27 全部本地分钟缓存范围清点

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：完整文件库存的首末抽样已完成；全量转换和完整交易日覆盖尚未完成。

## 实际清点

正式产品qmt_local_dat.inspect CLI在QMT外只读D:/software/guoxin/datadir/SH/60和SZ/60。共5342文件、88667127984字节（82.58GiB），5340非空、2空、0不可读取；按64字节布局估计1385423207条。4409份首记录在2021-11-01，其余起始日期分布已保留，不能仅凭晚于该日认定缺失或推断上市日。

最后记录日期：5284份为2026-10-21，17份为10-23，16份为10-26，1份为10-27；其余22份更早。10-27的文件为000300.SH。000001.SZ及三只价格差异证券都止于10-21，510300.SH为2026-07-28..10-26 11:30。清点显示大多数当前文件本身止于10-21，后续分钟尚待来源补齐。

完整库存（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-local-dat-inventory-real-003/inventory/inventory.json`）、逐文件观察（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-local-dat-inventory-real-003/inventory/inventory-items.jsonl`）、源码/结果/收尾（外部历史/待归仓路径：`../../build/qmt-local-dat-001/FULL-INVENTORY-MAIN.json`）。5342条逐文件观察与最终清单逐项核实一致。当前schema qmt.local-dat-inventory.v1，validation固定header-length-first-last-only，coverage仍unknown。

## 入口与验证

新增inspect_cache与inspect CLI，沿原cache-root、symbols/all-cache和新输出根规则。不调用Helper、QMT SDK或网络，不启动终端策略，不生成DSB。保留每文件状态和固定错误分类；长清点可查看inventory-items.jsonl，只有最终inventory.json表示整次完成。首末抽样不验证中间OHLC/排序/缺口，export/convert仍逐行执行原校验。

3项定向验证通过：混合非空/空/未知布局库存与源字节保持；中间OHLC差异在首末抽样后仍被正式export拒绝；清点后原export保持真实间隔及六字段原值。根16052正常exit0。实际全清点根69880正常exit0约39.21秒，整树归零、双EOF、读线程join与资源关闭均确认；本轮没有新增WT框架修改或真实下撤单。

前序45秒、300秒及60秒诊断清点触及各自预算，未发布完整收据，原件保留；每个对应controller/child已用Windows进程查询确认退出后才重新运行。003成功不能将前序超时改写为成功，冷热缓存对耗时的影响仍属于待核假设。补充逐文件进度后具备实际读取进度，未对缓存做修复或内容改写。

## 三条价格关系差异后继

只读原始记录复核（外部历史/待归仓路径：`../../build/qmt-local-dat-001/OPENING-MINUTE-RECHECK.json`）确认600000.SH（2024-03-20）、600015.SH（2023-05-08）、000007.SZ（2022-04-12）的已发现差异都在09:31；前一记录均为上一交易日15:00，后一记录为09:32。本次读取前后同文件身份/长度/mtime稳定，保留邻近192字节的SHA。

这支持优先核实开盘首分钟来源口径，但不能证明集合竞价造成差异；没有修改价格、放宽校验或跳行。仍须通过既有QMT共享内存入口取得相同分钟的原SDK返回，核对六字段后决定处理方式。[供应商行情接口](https://knowledge.thinktrader.net/docs/cloud/data_function.html)列有按分钟区间读取及subscribe=False；当前终端的具体可调用版本仍以本机接线实证为准。三只差异证券尚未纳入成功转换批次，17只4860337根既有转换回读结果保持原范围。

## 剩余交付

全库存转换、差异分钟的SDK同值核实、缓存尾部补齐、策略实时/历史统一接入和独立发行继续。库存存在与完整覆盖分开，QMT主来源、通达信现场暂停、旧工程只读等边界保持。操作见[本地缓存手册](../runbooks/qmt-local-dat.md)。
