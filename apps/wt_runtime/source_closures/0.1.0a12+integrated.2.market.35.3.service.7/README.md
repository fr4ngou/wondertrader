# WT Runtime 35.3.service.7 源码闭包

本目录只重建Root已接收的`guanheng-wt-runtime==0.1.0a12+integrated.2.market.35.3.service.7`，不改变运行、账户、交易或恢复行为。

基线为提交`c0f75a34eda046b7a4fb3b38147005b5d30f6a49`中的`apps/wt_runtime/guanheng_wt_runtime`。其中36个Python模块与service.7角色逐字节相同。`overlays/guanheng_wt_runtime`保存另外7个正式角色原件，构建器按`SOURCE-MANIFEST.json`组合并逐文件核SHA256。

## 七文件来源与主干影响

- `account_observation_process.py`、`initial_inventory.py`、`runtime.py`的正式行为来自`cd0219f688ec9cfe0754105c1f7bff45775131f9`。后继`4f44e2e460871c5b9c3a35bbf8d394d25b5b71e9`只增加中文字段注释，主干保留这些注释；闭包overlay保存正式安装的原字节。
- `backtest_cli.py`、`backtest_completion.py`的正式行为来自`be40f08e7f32894b119f42be8a84c9b812b16999`。后继`f62e80d5b2950389679a5f5a9094249d87d7b21a`将完成证明绑定到Host已准入的规范会话身份。该后继修复继续留在主干；service.7角色沿用尚未采用该修复的前代部署字节。
- `execution_recovery.py`来自固定`account-wiring-runtime-role001/ROLE.json`，service.6只接入只读账户发布定位，SHA256为`799e54d91f49ee6d6e9b79478c64ce2b9efbc325854420fcb66a99566c54a1c4`。
- `execution_configured.py`来自固定`capital-formula-role001/ROLE.json`，service.7恢复R34的`NAV−券商实际持仓市值`资金公式，SHA256为`2ac508f487677ea500ebf93c6bab4e4fa7356c4c3e95693d0d553a7efb489ba9`。这两份角色源码尚未形成独立上游提交，闭包直接保存Root接收的角色原字节。

## 固定构建

使用Python 3.12及本机已固定`uv`，从仓库根执行：

```powershell
python -B apps\wt_runtime\source_closures\0.1.0a12+integrated.2.market.35.3.service.7\build.py `
  --work E:\build\wt-runtime-35.3.service.7-source-001 `
  --output E:\build\wt-runtime-35.3.service.7-wheel-001
```

构建隔离后端固定`flit_core==3.12.0`。运行依赖固定`guanheng-market-client==0.15.0`；execution extra固定`guanheng-strategy-v1==0.1.0a8`及`guanheng-strategy-native==0.1.0a1`。构建器拒绝非空工作目录、源码摘要漂移、模块增减及wheel元数据漂移。
