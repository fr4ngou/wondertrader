# 未知委托恢复增量接收与双角色候选安装

类型：增量验证记录。日期：2026-11-01（北京时间）。状态：两条SDK替身业务主链已由Root核验；新版Source的Host/WT角色候选已普通离线安装。最终源码与配套Native交接、审查和活动委托跨进程恢复分别继续，完整交易模块尚未完成。

## 已核实际业务

Root只读接收 `ms-sdk-unknown-fresh-main-001` 和 `ms-sdk-unknown-fresh-transport-main-001` 的原始SDK记录、查询、原生状态、通信SQLite和关闭证明，没有重放业务。前者是SDK已接收后异常，后者是首次提交回复中断。

两案实际SDK均只调用两次insert，数量依次1000、200，原1000股只提交一次。完整ORDER查到原1000股已全成，后继POSITION查到1000股后，才实际提交新增200股。最终券商查询1200股，WT原生总持仓1200股，测试策略A800+B400与总量一致。原始命令正文SHA、身份和通信结果保留；第一案原记录始终为unknown，第二案原记录始终为sdk_returned，核清券商终态没有覆盖原SDK调用事实。

SDK调用及查询都在各案原来源线程。原Host/Source及外层Job正常关闭；Root核24份原件前后相同。读取已停止的通信库前确认WAL为空，使用immutable只读连接，没有创建或修改SQLite辅助文件。根接收记录为 `build/root-unknown-recovery-business-intake-001/INTERFACE-001.json`。

这些是普通CTA前端、合成SDK和测试策略的恢复证明；唯一保留业务策略1.1.2的正常53笔、当前库存接入与同根恢复，继续沿其各自既有证据。上述结果不代表真实券商委托或带活动委托的正式策略跨进程恢复已经通过。

## 双角色候选

Root沿已验独立WT制品，仅选择新版Host `0.1.0a22+mdphttp.3.tes.1.uc.1` 和Agent `0.1.0a12+marketdaily.4.uc.1`，更新对应锁及版本清单。其余Host角色13份、WT角色21份wheel保持原字节；候选不包含观衡App。角色制品SHA256为 `3cc798859323b72f9267a4da13057b56bb9c28b1298b69c6d736c61df62a638a`。

两角色使用原 `install_artifacts` 入口在全新目录普通离线安装：Host15份、WT23份依赖，pip check及原运行收据通过。实际已安装模块、完整版本和WT公开CLI可读取；两个环境均未安装guanheng_app。根记录为 `build/root-unknown-source-role-install-001/INTERFACE-CANDIDATE-002.json`，所选制品沿 `build/root-unknown-source-role-selection-001/INTERFACE-CANDIDATE-001.json`。

安装后Root核验脚本误写类名HostTradeRuntime，原外层失败及日志保留；实际公开类为HostTradingRuntime。原普通安装已经完成，后继只修正核验导入并读取同一安装，未重复安装、变更产品或覆盖原失败记录。

## 剩余范围

当前Python角色是待整包装配的候选，必须搭配本增量对应的Native组件；尚未用该角色候选启动WT交易或切换现有服务。开发者1继续固定源码、制品和复审材料，已完成增量先交Root合入，同时继续正式CTA金融/KV状态下的活动订单跨进程恢复。目标包括恢复原委托身份、查询其当前状态及沿原责任处理，保持未知委托不自动重发。

开发者2继续公开市场来源的闭市原件归档及原09:00服务循环，独立观衡a75已交付。用户暂时关闭QMT期间，真实查询和界面操作暂停；本轮没有QMT请求、真实下撤单、生产切换或新增WT框架修改。当前无需用户新增决策或操作。
