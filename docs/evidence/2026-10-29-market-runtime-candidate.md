# 统一行情运行候选独立安装验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证证据。日期：2026-10-29。范围：[MRC最终规格](../specs/market-runtime-candidate.md)的A-07/M3组件装配切片；全系统M3与发布继续独立验收。

最终候选为`build/market-runtime-candidate-001/candidate-005`，实际搬迁根为`relocated-005`。MARKET-RUNTIME.json SHA256为`1a7c8bc72a30e06353c97f68b2a608df50b769dd0e8561c6a52798a6e3793578`，ZIP SHA256为`fa758240c43b1a5e8c4ee4f4bfe75e72d2374c26705163192b4ccf8dd7813e3c`。1161个总成员，清单登记载荷32345462字节（另有总manifest），ZIP13206673字节；六原组件及许可证独立保留，同名DLL没有平面覆盖。完整输入锁、文件SHA与交接见HANDOFF（外部历史/待归仓路径：`../../build/market-runtime-candidate-001/HANDOFF.md`）及DELIVERY（外部历史/待归仓路径：`../../build/market-runtime-candidate-001/DELIVERY.json`）。

## 实际主链

`main-003/RESULT.json`固定同一搬迁根的四阶段；每阶段沿原隐藏Windows Job执行，完成后重新核全部候选文件集合与SHA，保持原字节。

| 阶段 | 实际观察 |
|---|---|
| 普通安装SDK/历史服务 | 新venv以pip --no-index安装包内0.15 wheel，实际App原SourceMarketProcess创建包内服务；510300的1m/d1各2根对原Reader逐字段/标签/单位/来源一致，同证券跨周期重读一致，监听及owner正常关闭 |
| 受管NMR | 同候选DLL读取上午三证券稳定副本及活动137只读根，各120根/119后继回调、重复0；原CTA/WtDtMgr require_stop装配及stop/delete后持有切片通过，22组原边界及HTTP/d1兼容复验通过 |
| 显式Parser v6 | 同候选HPR e正式Host→认证WinSHM→实际Python3.6.8完整内存正文SDK替身→同候选Parser三证券SPI；3回调、去重、stop/delete通过，源forbidden_attempts=0，Host Job/tree/EOF/join/句柄与源资源全部确认关闭 |
| 采集组合 | 原App QuoteCollectionProcess创建同候选采集service/HPR解释器，真实SHM两证券8笔SDK替身行情进入原native005 Writer；关闭归档后原Helper各回读2根，六字段/分钟一致，owner closed/forced=false/pending=false |

采集组合新增验证的原因是history组件所带collection_status与旧collection005 Python集合字节不同；原服务、DataKit绑定及native005复用，实际验证覆盖新目录/解释器/状态解释的组合。源SDK订阅由明确替身提供，没有真实QMT请求、下载、账户或交易。活动137/140及真实采集保持未操作；NMR只读取已声明上午窗口，不授下午自然调度资格。

历史服务的14份内置SDK Python源码与独立0.15 wheel逐字一致；实际调用者SDK从普通安装venv导入，模块身份及发行版本有断言。两个App owner的只读外部源码及依赖SHA在调用前后核一致，具体值登记各RESULT，未修改C的代码或配置。

## 边界与独立审查

`boundary-004/RESULT.json`通过30项坏例：来源/成员/消费字段/损坏、路径别名、真实hardlink与junction（含父穿越）、首读增长、清单/文件/枚举与共享剩余预算、坏ZIP、已有输出及collection首漂移只读一文件。原候选SHA保持。真实符号链接创建遇Windows权限1314，实际symbolic-link分支保持unknown；静态拒绝与真实junction/reparse路径分别登记。

Standards full发现的聚合读取预算P2已修复为六组件共用Budget，每文件打开前限制剩余量、即时核SHA并共用枚举计数；manifest首读快照复用。最终Standards delta与Spec full/delta均complete，未留实质P1/P2。Reviewer只读最终源码，运行资格unknown；本次实际运行结论由上述原件独立记录。

## 限制

候选装配默认关闭，不自动写App设置或启动进程。数据根、基础资料、配对、凭据、Journal和运行控制目录由App在包外显式装配。HPR原venv继续依赖其原runtime_anchor/pyvenv.cfg声明的本机Python运行时；移动目录资格不等于任意机器的Python安装资格。

原RS14恢复/Unknown/有限回读、HPR e、Parser v6协议异常、NMR及采集较大规模/多代/自动收盘只按精确原输入复用。新候选没有新增分钟算法、来源身份、单位换算、数据库或调度。完整B/C用户链、自然下午/跨日/全市场/真实源启用与全系统M3、实盘、发布资格继续分别验收。


## 根消费者独立安装复核

根消费者以最终candidate-005的manifest `1a7c8bc72a30e06353c97f68b2a608df50b769dd0e8561c6a52798a6e3793578` 和ZIP `fa758240c43b1a5e8c4ee4f4bfe75e72d2374c26705163192b4ccf8dd7813e3c` 执行已搬迁根verify→安装工具extract到新根→新根verify→resolve真实消费路径。`build/qmt-market-root-acceptance-283/RESULT.json` passed=true；外层284 exit_code=0、forced=false、tree_zero/readers_joined/resources_closed=true，耗时87.219秒。原组件代码未改，真实请求/下单/撤单均0。本结果授统一包的独立解包、校验和路径消费资格；完整B/C运行及生产仍单独验收。
