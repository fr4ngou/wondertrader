# WT Runtime 35.3.service.8 源码闭包

本目录只重建固定`fee-input-role001/ROLE.json`声明的`guanheng-wt-runtime==0.1.0a12+integrated.2.market.35.3.service.8`，不改变运行、账户、交易或恢复行为。

基线为永久提交`b856b9fdbcb14ad78a9776397d3b8c0907b18cc2`中的`apps/wt_runtime/guanheng_wt_runtime`。其中38个Python模块与service.8角色逐字节相同。`overlays/guanheng_wt_runtime`只保存5个有明确历史原因的角色原件；费用装配及账户恢复直接来自永久Git源。

## 源码与角色原件

- `execution_configured.py`及`retained_evaluation.py`的费用装配来自`69e8f37e6f7175c42a7df2d8eae1d7eb320c0d15`，版本声明来自`b856b9fdbcb14ad78a9776397d3b8c0907b18cc2`。`execution_recovery.py`的账户发布接线也已包含在该基线提交。
- `account_observation_process.py`、`initial_inventory.py`、`runtime.py`的角色字节来自`cd0219f688ec9cfe0754105c1f7bff45775131f9`；后继主干只增加中文字段注释。
- `backtest_cli.py`、`backtest_completion.py`的角色字节来自`be40f08e7f32894b119f42be8a84c9b812b16999`；后继规范会话身份修复继续留在主干。

构建器用`git show`读取固定提交的38个模块，避免共享工作区状态进入产物。五份overlay只恢复对应角色原字节，不覆盖service.8新业务模块。

## 固定构建

使用Python 3.12及本机已固定`uv`，从仓库根执行：

```powershell
python -B apps\wt_runtime\source_closures\0.1.0a12+integrated.2.market.35.3.service.8\build.py `
  --work E:\build\wt-runtime-35.3.service.8-source-001 `
  --output E:\build\wt-runtime-35.3.service.8-wheel-001
```

构建隔离后端固定`flit_core==3.12.0`。运行依赖固定`guanheng-market-client==0.15.0`；execution extra固定`guanheng-strategy-v1==0.1.0a8`及`guanheng-strategy-native==0.1.0a1`。构建器拒绝非空工作目录、源码摘要漂移、模块增减及wheel元数据漂移。
