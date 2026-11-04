# WT 35.3.service.5正式源码闭包

日期：2026-11-04。范围：`guanheng-wt-runtime==0.1.0a12+integrated.2.market.35.3.service.5`的可重建源码、固定构建元数据和普通安装验证。运行中的WT、`CURRENT`控制、统一日线、observer候选、QMT及交易链路均保持原状。

后继`service.6`和`service.7`已由[service.7最终源码闭包](2026-11-04-wt-runtime-service7-source-closure.md)接收；本记录继续作为service.5谱系前代证据。

## 输入身份与根因

正式安装位于`E:/workspace/wondertrader-data/runtime-service-20261104-004/venv/Lib/site-packages/guanheng_wt_runtime`。原正式wheel为`continuous-runtime/snapshot-wheels001/guanheng_wt_runtime-0.1.0a12+integrated.2.market.35.3.service.5-py3-none-any.whl`，SHA256为`ca8d97f5eadf4f2058d93deb86e1508b5e52e1c8ba95ee52a08462f3a42cc548`。固定主干提交为`c0f75a34eda046b7a4fb3b38147005b5d30f6a49`。

根审计`continuous-runtime/SOURCE-CLOSURE-AUDIT.json`确认43个Python模块中38个与固定主干逐字节一致，5个存在差异。历史追踪确认：`account_observation_process.py`、`initial_inventory.py`和`runtime.py`的后继差异只增加中文注释；`backtest_cli.py`与`backtest_completion.py`的后继差异为完成证明绑定Host已准入规范会话身份的实际修复。当前主干继续保留这些后继内容。固定版本闭包在`apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.5`保存五份正式原字节overlay，并以`SOURCE-MANIFEST.json`统一声明全部43个模块摘要。

## 正确实现

`build.py`只从固定主干包目录和五份overlay组合源码。每个输入必须匹配清单SHA256，模块集合必须为43项；输出wheel再次逐模块核验。构建后端固定`flit_core==3.12.0`，基础依赖固定`guanheng-market-client==0.15.0`，execution依赖固定`guanheng-strategy-v1==0.1.0a8`和`guanheng-strategy-native==0.1.0a1`。工作目录和输出目录必须为新目录。

## 实际验证

从隔离worktree执行：

```powershell
python -B apps\wt_runtime\source_closures\0.1.0a12+integrated.2.market.35.3.service.5\build.py `
  --work E:\workspace\wondertrader-qa\daily-mainline-20261103-001\runtime-source-closure-20261104\build-002 `
  --output E:\workspace\wondertrader-qa\daily-mainline-20261103-001\runtime-source-closure-20261104\wheel-002
```

CPython 3.12.13构建成功，`REBUILD-RESULT.json`登记43项全部匹配。新wheel SHA256为`c2f6cd4ecefa5dcb10bc9b642c4b0345fe564a925ad2dbf2bdd8b6cd3af9e31e`。新旧wheel的`METADATA`摘要均为`ba8561af091ace67d374b4313c1225d79b73f571bf3a3598382921b2ff5d35d3`，`entry_points.txt`摘要均为`f89d93aabb9ee1c9fe35926fe3b2d91cf1480c705c0e5ee9ebd76a86b0758bf7`。wheel容器摘要受构建时间及RECORD影响，因此按模块与元数据逐项验收。

使用CPython 3.12.13新建`verify-venv-002`，以`uv pip install --no-index`只安装新wheel和固定`guanheng_market_client-0.15.0` wheel。验证结果：版本均匹配，43个已安装Python模块摘要差异数为0，全包`compileall`通过，`guanheng-wt --help`与`guanheng-wt-service --help`均正常退出。

`git diff --cached --check`通过。`python -B scripts/project.py check`继续报告7个仓库基线缺失链接：`docs/maintenance/upstream-overrides.md`引用的stock-reference patch，以及`docs/modules/security-search.md`引用的6个Console文件。本闭包未新增或修改这些引用；该项目级检查保持失败状态并作为剩余仓库问题登记。

## 证明范围与剩余风险

本证据证明当前正式角色的Python源码可从仓库固定输入重建，并在全新普通环境安装和加载。既有正式主链证据因43个模块逐字节一致而继续适用。此次没有启动服务、读取账户、连接QMT、发单、撤单、切换`CURRENT`或发布新wheel。execution extra及真实金融运行仍沿各自既有发行和运行证据；新重建wheel尚未部署。
