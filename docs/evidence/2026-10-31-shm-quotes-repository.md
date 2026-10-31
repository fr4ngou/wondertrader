# 共享内存报价永久接入与正式构建

类型：验证记录。日期：2026-10-31。状态：永久源码与指定 CMake 产物的隔离 SDK 主路径通过；真实来源和完整系统资格分别保留。

## 输入与职责

已封存 retained 候选的 `INTERFACE-002.json` 摘要为 `88878d393be95c0134f704a7a165caaac8f17de96b1b551b088e8ed6519d955c`。
本轮使用 `build/root-shm-quotes-retained-001/PERMANENT-MERGE-002.json` 的26目标清单，逐个复核原SHA，保存七个已有文件的原字节副本；新增19文件。四个Common和两处Python入口按指定hunk合入，新桥/backend及QA归档按固定原字节复制。原WT框架、B/C其它模块、旧候选和现场保持。

长期正文、ADR和索引另外同步；源码规格见[唯一正文](../specs/qmt-shm-quotes.md)，职责见[模块](../modules/qmt-shm-quotes.md)，操作见[手册](../runbooks/qmt-shm-quotes.md)。任务结果留在本记录；两项P3继续登记在原独审和维护清单。

## 永久构建入口

`cmake/native/adapters.cmake`注册[报价目标](../../cmake/native/qmt_shm_quotes.cmake)，实际目标名为`GuanhengShmQuotes`。
从仓库永久源码，沿MSVC x64、C++17、锁定依赖配置正式`cmake/native`工程，再仅构建该目标。配置/构建命令、工具、输入和创建期Job记录在：

- `build/root-shm-quotes-repository-001/BUILD-001.json`
- `build/root-shm-quotes-repository-001/build001/{INPUTS-BEFORE,INPUTS-AFTER}.json`
- `build/root-shm-quotes-repository-001/control-build001/RESULT.json`

配置及实际编译链接成功，外层54.204秒exit0，树零、EOF、join、句柄全部正常关闭。使用永久桥、原QmtTickMapping和八个Common编译单元，同批生成DLL；必要静态依赖由正式CMake目标解析。生成物为`build001/cmake/bin/GuanhengShmQuotes.dll`，SHA：

```text
99a93cb642ea0469bab8bc6f0c1784c6d93d33de644d8736722c9e3056429b8f
```

该产物和旧手工构建DLL身份分别保存。源码/配置输入前后相同，Ninja真实依赖另留构建后观察；系统SDK头完整构建前库存未取得。

## 同产物 SDK 短主链

复用固定普通23发行和正式pair/verify接口，只替换新DLL及独占组件/输出身份，执行WT受管Host/市场服务 → 新C++报价DLL → 原Host15/Agent11 → 实际CPython3.6.8正式单正文和WinSHM → 外部计数SDK → MarketClient。报价和服务入口从本仓永久源码逐字取用；历史依然经原Import/Helper/Reader。

同次12个原市场POST、12次实际SDK full_tick、12个consumed，均为8证券；672个浮点逐位一致。容量保持8，实际回收6，尾部6条均终态/consumed，held_unknown0。状态采样峰6、串行准入上界7，精确绝对峰未授。原历史2根逐值和来源保持。原内容UUID、原请求/结果/确认SHA均核实。

SDK外层12.547秒exit0；WT/来源及全部资源按原关闭路径完成，金融写0、策略文件/网络违规0、原SDK线程及单timer保持。3001输入前后/当前一致，关闭Journal用immutable读取且SHA不变。原件：

- `build/root-shm-quotes-repository-001/main001/{RESULT,AUDIT,INPUTS-BEFORE,INPUTS-AFTER}.json`
- `build/root-shm-quotes-repository-001/control-sdk001/RESULT.json`
- `build/root-shm-quotes-repository-001/SDK-DERIVATION-001.json`

旧80次持续回收、两种丢回执和legacy默认证据按原固定源范围复用；本轮没有重复这些矩阵，也没有把旧DLL的全部运行资格自动转授新产物。

## 合入、回滚与边界

`MERGED-001.json`记录26文件前后SHA和回滚目录；`DOCUMENTS-001.json`记录长期文档/索引增量。首次Git hunk预检拒绝、一次缺失QA脚本的控制失败均保留；成功后继按目标原SHA和逐行上下文检查hunk，最终产品字节与固定候选一致。

原审查保留两项非阻断P3：`QmtBoundReadCore.cpp:960–962/1131–1133`的确定失败分类重复；`QmtHostReadClient.h:14–18/32`公开注释未覆盖retained字段与原ID lookup。根明确保持固定行为，完整主路径后统一维护。

本轮未提交Git、未替换任何运行包、未操作QMT/Host现场/原采集、未请求真实行情、未下撤单。真实retained报价/时效、跨进程未知恢复、完整SRI交易与生产继续单独验收。永久CMake指定产物的上述SDK主路径已取得资格；整仓全部目标构建和完整回归没有在本轮重跑。
