# 本地历史到观衡分钟图表主路径

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-27。状态：开发环境正向整链通过；整体迁移与独立发行继续。

## 实现与输入

调用链为已下载 DAT → 原 QMI/Importer/WT Helper → 原生 DSB → NativeHistory source Reader → source-store HTTP → 独立 MarketClient → 观衡 API → 浏览器分钟图表。首次实际转换输入、301946 行逐值核对及 DSB SHA 见[前序记录](2026-10-27-qmt-local-dat.md)。当前两个证券共用同一导入根和成功收据，不另建数据库或历史索引。

新增 source_market 服务与 SDK source_history_query，既有市场 HTTP 服务按显式 mode 接入。观衡通过显式 source 配置保留来源时间和单位，图表协议为 1.5；默认 canonical 路径保持。源单位、分钟边界与完整覆盖保持 unknown，source 模式仅提供 1m。接口依据 [RS7](../specs/qmt-source-history.md)，运行见[手册](../runbooks/market-service.md)。

实际输入为 `build/guanheng-workspace/qmt-local-dat-real-002/store`；导入收据 SHA 为 `6cae0acd64daf6cde0af1b3336089d004b21034f73c0c8885139181d1778d729`。Reader DLL SHA 为 `4f5e2696559011d755edfac1d58296626fdedb6ba46c6d6a0fafc0203eebe62c`。本次只读该 Store，不启停 QMT、不调用券商 SDK、不修改 WT 框架。

## 实际结果

主查询记录（外部历史/待归仓路径：`../../build/qmt-source-query-main-001/private/MAIN-PROBE.json`）：真实 HTTP→SDK 查询 SZSE.000001 与 SSE.510300，各返回 2000 根；耗时分别约 0.105 秒和 0.079 秒。股票最后标签 202610211500，ETF 最后标签 202610261130。观衡 build_native_chart 返回 available、2000 根和 schema 1.5，成交量单位仍为 unknown。

TypeScript 项目构建退出 0（约 3.88 秒）；Vite 实际构建退出 0（约 12.74 秒），输出在独立 `build/qmt-source-query-main-001/frontend-dist`。浏览器访问临时本机 App，进入行情页输入 `000001.SZ`，点击“读取分钟线”；实际显示 2000 根蜡烛及成交量，末条为 2026-10-21 15:00:00（北京时间），说明明确保留来源标签与未知单位。浏览器控制台 error/warn 均为空，画面已实际观察；浏览器记录（外部历史/待归仓路径：`../../build/qmt-source-query-main-001/BROWSER-MAIN.json`）。

## 运行收尾与限制

实际服务使用原拥有线程创建/查询/关闭 Reader。首次源服务进程 23320 正常退出 0，浏览器源服务 71156 正常退出 0，App 28980 正常退出 0；均沿原验证期限关闭。停止标记写入时进程已终止，不能把标记当作停止原因。首次 App 47732 因开发驱动未加入本仓库独立 strategy 包路径而退出 2；后继驱动显式加入当前仓库路径后通过，失败日志保留。该结果属于源码树开发验证，尚未授予独立安装发行资格。

本次按主路径优先验证正向功能；异常矩阵和独立代码评审后置。未完成全库存转换、三方来源单位/分钟边界核实、策略实时消费与完整交易恢复；未真实下单或撤单、未切生产。

本次实现源码身份见 SOURCE-IDENTITY（外部历史/待归仓路径：`../../build/qmt-source-query-main-001/SOURCE-IDENTITY.json`）。验证后仅修正文档及 native_chart 的语义注释，运行逻辑保持该验证版本。

本轮 `scripts/project.py check` 实际退出0，本地文档导航及技能清单检查通过；该检查不替代上述业务与浏览器验证。
