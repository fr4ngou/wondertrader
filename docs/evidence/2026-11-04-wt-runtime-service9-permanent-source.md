# WT service.8运行谱系与service.9最终永久源码闭包

日期：2026-11-04。范围：当前service.8角色谱系、尚未部署的最终service.9产品候选、永久源码选取、可复现重建和普通安装。任务只读取固定角色、Git对象及wheel，并写隔离worktree和新QA目录。

## 固定角色与业务源码

`fee-input-role001/ROLE.json`固定service.8 wheel SHA256 `f5c778a2105336502883caee194199a56571613cf3bcb84b21aa74ab301db532`。service.7→service.8只改变`execution_configured.py`和`retained_evaluation.py`，其费用装配业务提交为`69e8f37e6f7175c42a7df2d8eae1d7eb320c0d15`，版本提交为`b856b9fdbcb14ad78a9776397d3b8c0907b18cc2`。

`security-reference-v5-delivery001/ROLE.json`固定service.9 wheel SHA256 `c0c950176bae15465f856202cee44e05b7a400214142bb671dfa92f9722c1bc8`。service.8→service.9只改变`qmt_host_process.py`和`trade_host_process.py`，增加v5及QMT Host两项只读证券资料操作准入，另外41模块保持。原业务提交为`766b3219604be1d9d56d7d3c5423707785b6f4ac`、`fe1b829ce84c511aeecffd59adddb147d4440070`；干净主干对应提交为`00b0fd5cfaadcfbc06eec3765dfb308b4c355a23`、`757c359b00344af8ef0cae336e65c85918637946`。

## 永久源实现

service.8闭包以`b856b9f`为固定基线，service.9闭包以`757c359`为固定基线。构建器使用`git show <固定提交>:<模块路径>`读取38个业务模块，拒绝摘要漂移；共享工作区文件不会进入产物。两个闭包只保留相同5份历史角色原件：`account_observation_process.py`、`backtest_cli.py`、`backtest_completion.py`、`initial_inventory.py`和`runtime.py`。

费用装配、账户恢复、资金公式、`qmt_host_process.py`和`trade_host_process.py`均直接来自永久Git源，未使用旧overlay覆盖。`SOURCE-MANIFEST.json`逐项固定43模块摘要、基线提交、原角色wheel身份及service.5→9版本谱系。构建后端固定`flit_core==3.12.0`，运行依赖固定`guanheng-market-client==0.15.0`，execution依赖固定`guanheng-strategy-v1==0.1.0a8`和`guanheng-strategy-native==0.1.0a1`。

## 重建与新目录安装

CPython 3.12.13从永久源重建service.8，输出`runtime-source-closure-20261104/service8-source-wheel-001`，重建wheel SHA256为`f937c9b225928a3fa77949b53032bba8f2a88da32cf70313cb534d3d6c14d95c`。与固定service.8 wheel比较：43/43模块一致，`METADATA`摘要均为`576e19200986835c63bacf99cc1758329b8cb2b1d07d06f34e0637dbc63677c7`，入口摘要均为`f89d93aabb9ee1c9fe35926fe3b2d91cf1480c705c0e5ee9ebd76a86b0758bf7`。

同一解释器从永久源重建service.9，输出`runtime-source-closure-20261104/service9-source-wheel-001`，重建wheel SHA256为`033b39321022a1cf3f14a8d51082ba8304e3f613d1766e796804b91fc2a2075d`。与固定service.9 wheel比较：43/43模块一致，`METADATA`摘要均为`dc8b2b3195892064150fddda2637380e692c723bdd4e88fa06c207bec40f41bf`，入口摘要均为`f89d93aabb9ee1c9fe35926fe3b2d91cf1480c705c0e5ee9ebd76a86b0758bf7`。

新建`service9-source-verify-venv-001`，使用`uv pip install --no-index`只安装重建service.9 wheel和固定market-client wheel。版本导入、43模块安装、全包`compileall`、`guanheng-wt --help`和`guanheng-wt-service --help`均通过。wheel容器摘要受构建时间及RECORD影响，产品身份按模块、元数据和入口逐项验收。

全新安装目录按`SOURCE-MANIFEST.json`复核43项，摘要差异数为0。`git diff --check`通过。`python -B scripts/project.py check`继续报告7个既有仓库链接缺失，均来自stock-reference patch和Console security-search文件引用；本次未新增或修改这些引用。

## 运行保护与清理边界

Root提供的运行上下文为service.8控制`713edbdb`、WRI PID 15980及Native PID 27616；本任务未轮询或改变这些状态。service.9角色、service007/009、所有`account-host-read-wait*`、`security-reference*`、`trade-repairs*`、Native原件及本轮QA全部保留。没有启动或停止进程，没有切换`CURRENT`，没有连接QMT，没有读取账户或账本，也没有发送或撤销金融命令。

本轮未发现同时满足“无引用、无未合入成果、可重建”的外部材料，因此没有执行外部清理。Root继续负责service.9真实运行验收和统一最终清理；本记录证明永久源码和普通安装，不替代现场运行证据。
