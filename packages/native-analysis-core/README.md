# 原生分析 Core

独立可选分发包，提供原生历史导入、质量检查、前复权、回放及签名来源运输。
公共路径保持 `integrations.guanheng.*` 和可选的
`guanheng_market_client.qmt_native_replay`。基础 market-client 的元数据与源码清单保持独立。

`config/source-packages.json` 声明本包逐成员的永久来源。算法继续由仓库
`integrations/guanheng` 中的唯一实现维护；本目录仅拥有隔离包初始化、公开重导出和元数据。
构建工具在临时目录组装声明范围，通过锁定 Flit 构建 namespace，沿既有 Core wheel
映射方式加入公开重导出并重算 RECORD。构建不读取历史 wheel 或 `build/source001`。

使用 `python -B scripts/source_packages.py build --work <新目录>` 构建三个来源包。
完整说明见 [源码构建手册](../../docs/runbooks/source-packages.md)。

当前辅助组合使用a3+currentaux.1，仅调整发行依赖为V1 a13；固定QNA算法、Source HTTP运输和公开replay导出保持原字节。与AWP auxiliary.4.current.1和Runtime currentaux.1精确组合安装，不能把新V1混入旧a2精确依赖环境。

该组合的source-packages固定映射明确选择既有qmt-data-v2-hpr3中四个基础模型/读导入依赖，与原a2活动闭包逐字节一致；其余QNA/运输/导出成员沿既有永久源码。此声明消除当前开发模板与已采用闭包之间的来源歧义，不从运行安装取构建源码。
