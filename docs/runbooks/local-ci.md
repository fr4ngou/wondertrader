# 本地CI与master合入

类型：操作手册。范围：本地开发检查、执行链回归和本地master合入。

## 日常流程

1. 在独立开发分支完成修改，将最新本地master合入候选，解决冲突。
2. 运行本地CI或直接使用自动检查的合入命令。
3. 检查结果对应最终代码；开发者按明确文件清单提交，再快进合入本地master。
4. 发布按独立发布流程执行。

使用Python3.12+的开发测试环境。先安装本仓锁定依赖及`config/local-ci-test-requirements.txt`中的测试依赖；运行服务的解释器保持原样。配置及所需测试入口见[规格](../specs/local-continuous-integration.md)。

```text
python -B scripts/local_ci.py check
python -B scripts/local_ci.py integrate --master-worktree <本地master工作区绝对路径>
```

`integrate`省略`--receipt`时自动执行检查。预先检查过的同一内容可用下式合入，检查后提交且内容保持相同时也可复用：

```text
python -B scripts/local_ci.py integrate --master-worktree <本地master工作区绝对路径> --receipt <成功RESULT.json绝对路径>
```

默认结果在`build/local-ci/<唯一目录>/`，也可指定仓库外的`--output`。失败保留日志与结果，修正后使用新目录。结果含代码摘要、基线、选择的profile、阶段状态和日志；输出处于running或failed时不作为合入成功证据。

## 当前覆盖

| 变化 | 自动执行 |
|---|---|
| 纯文档 | 项目文档导航检查 |
| 软件 | 文档检查、本地CI流程回归、app_console及wt_runtime中pytest可收集的软件回归 |
| 执行相关 | 上述检查，加当前C++产品重新构建、真实WT执行器/标准插件/Host/WinSHM的四项券商替身E2E |

软件层只收集`test_*.py`，CLI探针由各自显式阶段执行。缺少依赖、收集失败、断言失败及子进程失败均保留失败；测试数量和功能完成分别解释。其余模块、完整策略与浏览器链需逐模块继续接入，当前结果只证明表列范围。

## 本机执行缓存

机器路径保存在Git忽略的仓库根`.local-ci.json`，不含账户或生产连接参数：

```json
{
  "execution_inputs": "<已验证工具链、依赖源码及已批准WT快照所在目录>",
  "legacy_fixtures": "<显式历史测试tests/integration目录>"
}
```

`execution_inputs`需要原产品构建生成的TOOLCHAIN.json、SOURCE.json、inputs/upstream及deps。入口核验上游快照和批准覆盖，冻结当前自有源码到独立结果目录，重新构建项目对象。缺少缓存时先按[构建手册](build.md)准备，CI本身不调用Git远端或托管平台。

当前执行夹具仍有显式历史目录依赖，成功结果登记相关摘要；归仓和统一开发环境安装还需继续完善。纯软件测试使用当前候选包的PYTHONPATH，第三方依赖取调用解释器的正常环境。环境依赖异常先修开发环境，保留首次失败记录。

## 发布衔接

合入后记录master提交和成功RESULT.json的位置，发行构建使用该固定提交；版本化配置、依赖、源码及制品摘要一并进入[发布记录](../releases/TEMPLATE.md)。仅合入的任务到此结束，保持运行版本原样。已获授权的发布继续完成独立打包、安装、稳定入口与端口核对、持久日志检查及实际业务验真。

源码、依赖和适用输入相同时复用已有结果；变化时按影响重验。WT和观衡独立发布，本地CI不引入新的策略上线人工审批。完整步骤见[发布规范](release.md)，原生制品流程见[构建手册](build.md)。

## 本地Git行为

入口先验证结果、内容及master基线，再用Git正常快进。master已推进时更新候选并重验，冲突由Git保留。CI不会清理worktree、停止常驻进程、发布制品或触发真实下撤单。

当前通过统一本地命令自动检查，普通`git merge`未安装额外钩子；团队日常合入使用本手册入口。其余源码提交、审查及发布规则沿[开发流程](../development/workflow.md)和[发布规范](release.md)。
