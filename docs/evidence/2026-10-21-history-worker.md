# 2026-10-21 独立历史执行与 SDK 0.4.0

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：pass（隔离开发验收）；真实来源/生产部署 pending-verification。对应 [HW-R1–R5](../specs/history-worker.md)，整体移植目标保持 active，范围见[完整验收地图](../migration/acceptance-map.md)。

## 输入与制品

WT 工作区 `E:/workspace/wondertrader`、分支 `codex/qmt-migration-plan`、HEAD `08b230dd05facf6d650d949bfe51054115a2ecb1`，保留既有未提交工作。最终代码输入指纹 `192f011a3786a296ca1d8cf2a57275099206101a7a4ed18902d823463f11bd02`。原 QMT 主树只读、HEAD `3a2f97cbeb0127747f5f8d3cef5f8a3c467420ff` 且 Git 干净；18010 未监听，未启动原服务或连接生产数据库/账户。

最终开发包 `build/native/packages/dev-20261021T041130Z-807f2012.zip`，5,016,314 字节，SHA-256 `b680239e9206a7826df807bf06d8fdf0cc8794948996c893bea0858e578f8553`。包内 `clients/guanheng_market_client-0.4.0-py3-none-any.whl` SHA-256 `c5407657dee866df4cd2811626db005a0181701e9713a6fa6e67470c8fcb812d`；独立重建得到相同字节。基本导入保持标准库，storage extra 的 MinIO/urllib3 版本不变。

## 行为与根因

独立 `history_worker` 按显式 job、可信部署工厂和 OS 进程锁运行；全程以 Operations 为唯一持久作业 owner。本地信号/步数/时间停止后调用 close，有界释放已知任务，不发送业务 stop/resume、不新增任务账本。准备交换结果未知时保留队列 owner 恢复需求；即使后续作业成功，也明确以退出码 4 保留该诊断。

关闭保护贯穿 prepare 发出到有效拒绝或任务身份接管，step finally 与 close 都观察未完成交接标记。独立 trace 复现的回复返回后中断现返回 Unavailable/recovery_required，保留真实待回收任务；已接管身份仍可幂等释放。factory/step/drain 的 KeyboardInterrupt 与 SystemExit 去敏，原始异常文本不进入运行日志。默认关闭窗口 35 秒、上限 60 秒，配置层要求严格大于 runner 的单次预算，避免原默认 30 秒相等窗口永远无法准入 close。

制品验真为 worker 单独安装搬迁包内 wheel 到明确目录，再运行隔离进程；不依赖另一测试内部随机目录。首次路径接线失败已保留在开发工作记录，最终候选完整重验。正常关闭与未知准备恢复分别表达；崩溃遗留仍归队列 owner 的独占实例回收流程。

## 最终执行

| 命令/链路 | 实际结果 |
|---|---|
| `python -B scripts/native.py all --offline --jobs 4 --qmt-source D:/workspace/qmt` | exit 0，17 阶段全部 passed |
| CTest | 51 启用全部通过；另 1 既有全天时段用例 Disabled；133.19 秒 |
| 构建流水线 | 30 项通过，含 6 项实际 SDK 构建/输入/依赖 metadata 负向 |
| runner/关闭 | 25 原回归 + 18 关闭回归，合计 43、无 skip；覆盖真实 loopback、原纯 DTO/reducer、线程/重入、背压/丢回复/交接中断 |
| worker 进程 | 13 项、无 skip；真实子进程→loopback Operations/市场/证据；原 Operations 纯 DTO/内存归约器只在父测试进程 |
| wheel/搬迁包 | 独立离仓安装、`-I -S` 四模块导入；包内 wheel 单独安装后 13 项进程测试再验，16.783 秒 |
| 保留原生链 | WT 回测、工厂、Runtime/分钟/DSB、原业务影子回放及独立 HTTP SDK 消费继续通过 |
| 静态检查 | Ruff、Python 3.10 四模块语法、本地文档检查与差异空白检查通过 |

worker 覆盖完整成功、原 stop_requested/只读终态、错 family 零业务变更、步数/时间/信号暂停、同身份释放回复未知后的下一进程认领 DSB、关闭背压、未知 prepare 的遗留诊断、锁竞争先于工厂/远端、工厂崩溃后 OS 锁自动释放、异常与 argv 去敏。默认 runner/关闭窗口边界也经过真实独立进程验证。各方法内子场景与 CTest 注册数分别计数。

## 审查与运行边界

首次 full 审查分别核对关闭/恢复行为和入口/发行边界，修复后 delta 复验全部受影响条件；三项 P2 均已关闭。最终行为报告（外部历史/待归仓路径：`hw-2026-10-21/hw-independent-review.md`）的 20 项输入与发行报告（外部历史/待归仓路径：`hw-2026-10-21/hw-sdk-independent-review.md`）的 30 项输入均逐文件匹配。行为轴独立验证 43/43 与 13/13；发行轴独立验证实际 wheel 安装/13 项、独立重建与 6 项构建负向，并只读核对最终搬迁包。生产依赖缺失保留 unknown，源码测试不授实际服务切换资格。

冻结的汇总（外部历史/待归仓路径：`hw-2026-10-21/summary.json`）、完整收据（外部历史/待归仓路径：`hw-2026-10-21/receipt.json`）、SDK 收据（外部历史/待归仓路径：`hw-2026-10-21/client-sdk-receipt.json`）、包清单（外部历史/待归仓路径：`hw-2026-10-21/package-manifest.json`）及全部日志保留最终身份；文件摘要（外部历史/待归仓路径：`hw-2026-10-21/SHA256SUMS.json`）覆盖本阶段 24 个原始文件。上一阶段 HSA/HES 各 22 个原始文件摘要保持一致，历史证据保持原样。

权威分钟/历史停牌日历、原日线 CLI family 路由保护、实际 QMT HTTP profile、真实 MinIO namespace/ACL/保留及结果 resolver 仍待各 owner 接入。部署工厂当前通过合成完整依赖验真，尚未提供合格生产日历工厂。跨主机单工作者/硬截止由部署监督承担，OS 文件锁只证明同一可靠本机目录范围。共享内存绑定、TDX 交易继续暂缓。未执行实际订单、撤单、账户变更、上传、Git 推送或生产发布。
