# 2026-11-01 WT独立候选交付

类型：development候选交付记录。状态：制品及使用说明已交付，既有已验本机安装复用；最终真实QMT只读验收待终端恢复。

## 使用与版本

交付目录`E:/workspace/wondertrader-deliveries/wt/0.1.0a12+integrated.2.reconcile.1`包含完整WT ZIP、摘要、`DELIVERY.json`及《开始使用.md》。已验安装位于`E:/workspace/wondertrader/build/root-simple-recovery-wt-package-001/installed`；本次直接复用该安装，未重新构建、安装或执行业务。

包内包含C++原生执行、策略和行情组件，以及独立WT/Host辅助环境；不含观衡App或SPA。实例配置、配对秘密、账户材料、金融状态和历史文件独立维护。启动使用原公开WT CLI及对应实例的配置、原字节摘要和新控制身份，见[WT运行手册](../runbooks/wt-independent-runtime.md)。其他目录安装使用原[extract/install/resolve流程](../runbooks/system-installation.md)，已安装的虚拟环境保持原绝对路径。

WT运行角色版本`0.1.0a12+integrated.2.reconcile.1`，最终交易增量源码提交`56effe9d4761cd3ef787e5f9dcb97b1268b58a6f`；整体制品沿固定上游、已批准覆盖和原来源清单组合，分别保留各组件身份。ZIP逐字复用[完整安装验收](../evidence/2026-11-01-wt-simple-recovery-installed.md)中的同一包。

## 已验范围

普通安装、路径解析、正式共振市场状态ETF策略1.1.2首次接管、同一金融目录正常重启及全部9组件正常关闭通过。带活动单的简版使用原查询和订单表定向撤单，实际SDK替身场景为卖200股、成交40股、撤余160股，重启后以券商持仓和资金重新计算160股；人工委托保持。未知委托继续按原命令身份查询。观衡与WT分别启动和关闭。

精确身份：

- ZIP SHA256：`6a99eac2c75f83b3756d0719774300f5e358e05d3a19bd149178dc8af1a2c3c4`。
- `SYSTEM-RUNTIME.json` SHA256：`2f919124d9ae2cdb7696dc1f75709b24a76845a0362b6b2dfa5f50606d14892c`。
- 本机安装收据SHA256：`e4aa7622c1105d8d3bee418d6eac4c961c5e32c014e6636f589e0aa037a4d1ac`。
- 本机`DELIVERY.json` SHA256：`41d241c19cee11429b46ec33abc6a24a31d460c99227ca3d9549976d24baae85`。

## 剩余与运行边界

以上交易及完整组合使用SDK替身；此前真实只读账户、报价和原生分钟读取保留其原固定输入资格。最新版真实QMT重连及账户/行情消费需在用户恢复终端和原共享内存策略后进行。本次不启动第二个账户执行实例，不切换原WT、Host、采集或观衡服务，真实下单、撤单和生产切换均为0。旧未定位失败及异常金融状态重放限制沿原验收记录保留。
