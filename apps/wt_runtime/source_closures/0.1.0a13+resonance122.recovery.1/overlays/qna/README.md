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
