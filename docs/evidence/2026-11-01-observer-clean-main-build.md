# 观衡a75干净主干离线重建

类型：后继验证记录。日期：2026-11-01（北京时间）。状态：passed；范围为独立观衡候选的正式源码可重建性，原[独立交付](../releases/2026-11-01-observer-a75-independent.md)及现场服务保持原身份。

## 输入与实际执行

从干净主干提交 `54f564e6247f4699d33e5592f9a2df5cc27cf79f` 的独立工作树执行公开 `scripts/observer_source.py build`。固定CPython3.12.13 x64、Flit3.12.0、Node24.18.0、npm11.16.0、24份锁定第三方wheel和既有完整npm缓存。422项永久声明输入、六个Python项目及前端沿本次收据固定；旧QMT源码、历史安装源码和临时业务源码均未参与。

构建目录为 `E:/workspace/wondertrader-qa/root-observer-a75-clean-build-003`。沿原900秒总预算、各命令预算及隐藏Job执行，耗时74.515秒，公开包verify通过，外层Job、进程树、管道和读线程正常关闭。

首次两个尝试选错缓存，分别因缺少undici-types和zrender离线包失败，现场保留。最终采用原已验构建记录中的 `apps/guanheng/console/build/cache/npm`；源码、锁文件、依赖版本和工具预算保持。该操作修正构建输入选择，不构成应用代码修复。

## 结果与资格

独立生成App30角色、生产SPA及观衡ZIP。Root比较全部30个wheel与原交付，各wheel的完整SHA256相同，5075个解压成员逐字节相同；18个SPA文件的集合和逐文件SHA256全部相同。

新构建ZIP的SHA256为 `b6f761615e4d62d53ddb6a8a570ef0d5f0ebd7802d69794142c2cbce5e65d876`。构建来源路径、清单及包内操作说明属于本次构建，归档整体身份与原交付分别保留。新ZIP只作独立源码重建证明，已交付ZIP和本机安装没有替换。

同字节运行内容继续复用a75已验的实际本地数据读取、API/UI/CSV、浏览器和正常关闭证据；本轮不重跑这些功能链。构建未启动观衡、WT、Host或QMT业务，不进行账户查询、下单、撤单或生产切换。

## 可追溯原件

- 公开构建收据：上述构建目录 `SOURCE-BUILD.json`，记录全部源码、工具、命令、角色及归档身份。
- 外层正常关闭：`build/root-observer-a75-clean-build-job-003/CLOSED.json`。
- Root独立内容核对：`build/root-observer-a75-clean-build-intake-001/INTERFACE-001.json`。
- 构建方法与缓存选择沿[长期手册](../runbooks/observer-source.md)。

市场指标持续来源和交易恢复候选仍由各模块完成后继交付；本次源码重建不扩大真实来源、金融动作或生产资格。
