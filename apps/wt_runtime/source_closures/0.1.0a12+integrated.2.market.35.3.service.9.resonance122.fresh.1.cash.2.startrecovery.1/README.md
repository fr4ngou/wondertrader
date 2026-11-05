# 执行启动前失败的原材料续接固定源码

类型：发行源码闭包。状态：构建及正常安装工程验证通过，实际采用由Root负责。

本发行在[原cash.2闭包](../0.1.0a12+integrated.2.market.35.3.service.9.resonance122.fresh.1.cash.2/README.md)45模块之上，仅替换自有service_control.py；其余模块、依赖、策略及QNA保持原输入。最终行为见[WSC-R1](../../../../docs/specs/wt-service-control.md#wsc-r1-执行组件之前的启动失败)。原闭包保持原件，SOURCE-MANIFEST.json记录继承来源与本代覆盖SHA。

运行本目录build.py，显式指定全新--work及--output目录。构建读取固定原Git及永久overlay，通过缓存Flit3.12.0离线构建普通Runtime wheel，不导入业务模块、读取现场配置或启动服务。安装与现场原账接续由Root沿受管入口另验。

[工程证据与执行闭包换代边界](../../../../docs/evidence/2026-11-05-service-preexecution-recovery.md)列明14项安装回归、候选wheel及原账实际采用范围。
