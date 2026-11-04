# 2026-11-04 分钟角色实际启动接线修正

类型：故障后继验证及交付记录。状态：`pending-verification`；实际阻断已无启动复现，修正及新候选准入完成，正式重试由Root执行。接续[首次正式采用候选](2026-11-04-minute-daily-adoption-candidate.md)，保留其当时范围与失败现场。

## 触发链与根因

Root正常停止原日线、GH行及旧data/quotes（exit0/all_trees_zero），按CAS采用完整Source166418…后，首次新data没有发布OWNER-READY。原现场为`E:/workspace/wondertrader-data/minute-adoption-20261104-001/data-owner001/a799be53-b7b2-4b9d-aa26-bb4113aeb1b8`；status明确为`component_start_history`，history为unexpected_exit，原HPR已经正常closed，collection尚未启动。父级runtime_start/RuntimeError是组件失败的上层结果。

配置生成器从旧角色继承history/collection的legacy-hpr解释器，而最终`.9`入口按包导入helper时保持宿主SDK解析，该旧解释器没有`guanheng_market_client`。用描述符实际解释器`-I -B`仅runpy入口稳定复现ModuleNotFoundError，尚未创建服务控制目录；同一入口在Root013和日线015完整环境加载成功。

同一启动链的collector直接入口还遗漏release根，只加入integrations/agent/host，无法解析完整`integrations.guanheng.quote_collection`。实际Root013及legacy环境均无启动复现；先前配置schema与daily015入口准入没有覆盖这两个primary实际解释器/入口组合。

## 正确实现

配置准备显式要求`process_pythonw`固定描述符，新history/collection两子进程统一采用其完整运行环境。原HPR解释器、pair/profile/Journal以及原日线解释器保持。新请求在完整Source处于已固定before或after时均能准备新目录，任意第三种目标正文仍拒绝；实际Source不由准备命令写入。

collector直接入口加入自身release根，保留`.9`的`if not __package__`条件；按包导入helper保持宿主sys.path及完整SDK身份。修改位于自有入口和配置生成器，WT框架及Runtime监督实现保持。

共享helper的后继SHA同步到统一日线源码成员清单，后继构建声明及包元数据为`.10`。原`.9`标签、安装015及其实际解释器保留，本轮未构建、安装或部署`.10`；源码成员核验通过，避免修正共享入口后主干仍锁旧文件而失去可重建性。

## 证据与固定材料

QA根：`E:/workspace/wondertrader-qa/minute-adoption-20261104-001`；数据根：`E:/workspace/wondertrader-data/minute-adoption-20261104-001`。

| 证据 | 结果与范围 |
|---|---|
| `STARTUP-ENTRY-DIFFERENTIAL001.json` | 原history实际legacy环境失败，Root013/daily015成功；collector原入口在legacy/Root013均失败；0服务/Source/新增线程 |
| 新`minute_collection/test_entry_bootstrap.py` | Root013实际解释器两个新入口隔离加载通过，模块文件必须来自当前release；0服务 |
| 原`daily_security/test_entry_bootstrap.py` | 在实际daily015解释器两项回归通过，包helper不改变宿主路径、完整SDK及独立CLI保持 |
| `STARTUP-REPAIR-PREFLIGHT001.json` | 实际Root013原Runtime工厂构造host/history/collection三owner，状态new、无start、线程未增加；三个子入口按各自实际解释器加载、全程序/配置及after CAS核验通过 |

新`program003/INSTALLATION.json` SHA为`c5027125e6cdcbbc407af0f8743264112e390ba6bb55f01d976213a04c2961ee`；`configuration003/DEPLOYMENT.json` SHA为`220029b27245b7af8ff214411d2d425b38d359c03a8f7764559198a1c96759d9`；`bindings002/BINDINGS.json` SHA为`f8c1a9a8dcbc6726406b0a27b8da4d619426c67f63aca48598a38db2b0f96cf5`。Source166418…及原before/after CAS不变；Native输入未变，复用原构建，未重新构建或重复全套回归。

最终正常重试/完整回退入口为QA根`HANDOFF-REPAIR-001.md`及`commands002.ps1`。Root从现有已采用Source现场使用新`data-owner002`启动，旧failure目录和原HPR closed保留；quotes、GH及日线仍按实际ready逐段接续。失败原因清楚后修正接线，没有删除锁、重放请求或修改原失败状态。

本轮未操作服务/QMT，金融八组件保持原所有者；实际重试、12样本及覆盖继续由Root登记。金融模拟交易已验结论及自然行情后续观察不因本次分钟接线增加门槛。
