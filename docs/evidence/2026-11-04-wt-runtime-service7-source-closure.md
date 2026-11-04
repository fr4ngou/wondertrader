# WT 35.3.service.7最终源码闭包

日期：2026-11-04。范围：Root已接收`guanheng-wt-runtime==0.1.0a12+integrated.2.market.35.3.service.7`的永久源码闭包、版本谱系、固定重建和普通安装验证。任务只读取角色材料并写隔离worktree及新QA目录。

后继service.8及service.9已由[service.9永久源码闭包](2026-11-04-wt-runtime-service9-permanent-source.md)接收；本记录继续作为service.7谱系前代证据。

## 输入身份与谱系

前代service.5 wheel SHA256为`ca8d97f5eadf4f2058d93deb86e1508b5e52e1c8ba95ee52a08462f3a42cc548`。固定`account-wiring-runtime-role001/ROLE.json`声明service.6 wheel SHA256 `bab35d6df50c8a81e77e68abb8f7ed0ad59bd5942cd3b3913f4f18e6091af175`，只将`execution_recovery.py`从`00451f7c...`替换为`799e54d91f49ee6d6e9b79478c64ce2b9efbc325854420fcb66a99566c54a1c4`。固定`capital-formula-role001/ROLE.json`声明service.7 wheel SHA256 `465315505999c4de08386ed6b2e0ca075c07b42c51270b56f52e68e68727d97d`，只将`execution_configured.py`从`6126f64e...`替换为`2ac508f487677ea500ebf93c6bab4e4fa7356c4c3e95693d0d553a7efb489ba9`。

三份原wheel逐模块比较确认：service.5→service.6差异集合仅为`execution_recovery.py`；service.6→service.7差异集合仅为`execution_configured.py`。service.7仍为43个Python模块。第二项恢复原NRT-R34的`NAV−券商实际持仓市值`策略资金公式，不增加账本，也不读取旧数据库。

## 正确实现

最终闭包位于`apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.7`。它继续使用固定提交`c0f75a34eda046b7a4fb3b38147005b5d30f6a49`的36个逐字节相同模块，保留service.5已追溯的5份overlay，并从role006正式安装原件保存上述2份后继overlay。`SOURCE-MANIFEST.json`记录43项摘要、三个wheel身份和两步唯一差异。

两个后继文件当时位于共享工作区未提交修改中，因此闭包以Root固定角色、正式安装原件和wheel摘要为来源，不引用尚不存在的上游提交。固定后端仍为`flit_core==3.12.0`，运行依赖仍为`guanheng-market-client==0.15.0`，execution依赖仍为`guanheng-strategy-v1==0.1.0a8`和`guanheng-strategy-native==0.1.0a1`。

## 实际验证

使用CPython 3.12.13执行闭包构建，工作目录为`runtime-source-closure-20261104/service7-build-001`，输出为`service7-wheel-001`。重建wheel SHA256为`422897dd75f78142d823124ea7a7fcad9e1d95576ece940653d2be23dd9a94d0`。与Root固定service.7 wheel比较结果：43/43模块摘要一致，`METADATA`摘要均为`b7b1747a55a5acd43e56684250cce03becd9e2c0dcfbe04f061d24270ec51f38`，`entry_points.txt`摘要均为`f89d93aabb9ee1c9fe35926fe3b2d91cf1480c705c0e5ee9ebd76a86b0758bf7`。

新建`service7-verify-venv-001`，以`uv pip install --no-index`只安装重建wheel和固定market-client wheel。版本导入、全包`compileall`、`guanheng-wt --help`和`guanheng-wt-service --help`均通过。wheel容器摘要因构建时间及RECORD变化，产品身份按43模块、元数据和入口逐项验收。

暂存区7份overlay再次逐文件核验，摘要差异数为0；`git diff --cached --check`通过。`python -B scripts/project.py check`继续报告与前代闭包相同的7个仓库基线缺失链接，均来自stock-reference patch和Console security-search文件引用，本次未新增或修改这些引用。

## 运行保护与剩余边界

Root提供的接收上下文为`CURRENT dfcd8ac7`、WRI PID 32412、Native PID 24692及已产生第三笔委托；本任务只把这些视为保护边界，没有轮询或更改其状态。角色004/005/006、Source/Native候选、Native原件和本轮QA均保留。任务没有启动或停止进程，没有切换`CURRENT`，没有连接QMT，没有读取账户，也没有发送或撤销金融命令。

本闭包完成产品源码与service.7角色字节闭合。Root继续负责正式服务接线、运行事实和第三笔委托的业务记录；本证据不替代其现场运行验收。
