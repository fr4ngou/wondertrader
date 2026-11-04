# WT Runtime 35.3.service.9 最终源码闭包

本目录只重建固定`security-reference-v5-delivery001/ROLE.json`声明的`guanheng-wt-runtime==0.1.0a12+integrated.2.market.35.3.service.9`，不改变运行、账户、交易或恢复行为。

基线为干净永久提交`757c359b00344af8ef0cae336e65c85918637946`中的`apps/wt_runtime/guanheng_wt_runtime`。其中38个Python模块与service.9角色逐字节相同。`overlays/guanheng_wt_runtime`只保存5个有明确历史原因的角色原件；service.8费用装配以及service.9两项只读证券资料准入全部直接来自永久Git源。

## 源码与角色原件

- `qmt_host_process.py`及`trade_host_process.py`的只读证券资料操作准入来自原提交`766b3219604be1d9d56d7d3c5423707785b6f4ac`、`fe1b829ce84c511aeecffd59adddb147d4440070`，干净主干对应提交为`00b0fd5cfaadcfbc06eec3765dfb308b4c355a23`、`757c359b00344af8ef0cae336e65c85918637946`。
- service.8的费用、账户恢复和资金公式均已包含在`757c359`基线中，构建时不使用旧overlay覆盖这些业务模块。
- `account_observation_process.py`、`initial_inventory.py`、`runtime.py`的角色字节来自`cd0219f688ec9cfe0754105c1f7bff45775131f9`；`backtest_cli.py`、`backtest_completion.py`来自`be40f08e7f32894b119f42be8a84c9b812b16999`。五份后继主干修正继续留在主干，overlay仅恢复service.9固定角色原字节。

构建器用`git show`读取固定提交的38个模块，避免共享工作区状态进入产物。`SOURCE-MANIFEST.json`同时固定service.5至service.9的逐版本wheel身份及唯一变化集合。

## 固定构建

使用Python 3.12及本机已固定`uv`，从仓库根执行：

```powershell
python -B apps\wt_runtime\source_closures\0.1.0a12+integrated.2.market.35.3.service.9\build.py `
  --work E:\build\wt-runtime-35.3.service.9-source-001 `
  --output E:\build\wt-runtime-35.3.service.9-wheel-001
```

构建隔离后端固定`flit_core==3.12.0`。运行依赖固定`guanheng-market-client==0.15.0`；execution extra固定`guanheng-strategy-v1==0.1.0a8`及`guanheng-strategy-native==0.1.0a1`。构建器拒绝非空工作目录、源码摘要漂移、模块增减及wheel元数据漂移。
