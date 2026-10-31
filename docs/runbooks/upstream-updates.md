# 上游更新操作手册

类型：操作手册。范围：获取上游、选择新基线、隔离合并、解决冲突、验证和集成。命令使用 PowerShell 模板；替换尖括号值并逐步检查退出状态，只有读取/准备步骤可在没有集成授权时执行。

## 1. 前置核对

记录 origin/upstream、正式主干、当前下游基线、已吸收上游完整 SHA、候选上游 SHA/tag 及更新理由。确认任务区提交已保存；现有脏工作区和运行实例保持原样，在独立 worktree 集成。

```powershell
git status --short
git remote -v
git rev-parse --is-shallow-repository
git fetch --filter=blob:none upstream
git fetch --filter=blob:none origin
```

若为浅克隆，在计划允许的流量/时间内使用 `git fetch --filter=blob:none --unshallow upstream` 补足祖先，或分段 deepen；`merge-base` 必须证明共同祖先。仍缺祖先时保持更新阻断，采用有限深度不构成无共同历史的结论。只读获取不会更新已登记的生效上游基线。

## 2. 固定身份与范围

```powershell
$downstreamCommit = (git rev-parse '<正式主干或已验提交>^{commit}').Trim()
$oldUpstream = '<上次已集成上游的完整 SHA>'
$newUpstream = (git rev-parse '<选定上游 ref>^{commit}').Trim()
git merge-base $downstreamCommit $newUpstream
git merge-base --is-ancestor $oldUpstream $downstreamCommit
git merge-base --is-ancestor $oldUpstream $newUpstream
git log --oneline "$oldUpstream..$newUpstream"
git diff --stat $oldUpstream $newUpstream
git diff --stat $oldUpstream $downstreamCommit
```

每次身份解析和 ancestor 检查单独确认 exit 0 后继续；失败时停止并查明原因。上游发生历史重写、回退、已吸收精选提交或来源改变时单独评估，保留双方来源，不强行套用正常增量流程。

按上游日志与差异核对 API/ABI、状态/文件格式、时间/单位、执行与风险语义、依赖、许可证及[自有覆盖](../maintenance/upstream-overrides.md)。记录需要保留、被上游取代或仍待验证的每个行为。

## 3. 隔离合并

下面 `<新的绝对 worktree 路径>` 与分支名必须经操作者核实，且与运行目录分离。仅创建新目录，不移动或覆盖现有工作区。

```powershell
$integrationPath = '<新的绝对 worktree 路径>'
$integrationBranch = 'codex/upstream-<更新标识>'
git worktree add -b $integrationBranch $integrationPath $downstreamCommit
git -C $integrationPath merge --no-ff --no-commit $newUpstream
git -C $integrationPath status --short
git -C $integrationPath diff --name-only --diff-filter=U
```

没有新增上游内容时记录 no-op 并退出。发生冲突时在集成 worktree 按三方语义逐个解决，显式暂存路径并检查完整 staged diff。解决后确认无 unmerged paths；按授权提交最终 merge，保留上游祖先。放弃时先确认该 worktree 原本干净且只有本次合并，再在此目录执行 `git merge --abort`；原工作区保持原样。

## 4. 验证候选

按[测试手册](testing.md)选择受影响 UT/组件、接口契约、固定回放、隔离 E2E、故障恢复与包级测试。确认自有策略和接口行为、状态恢复、核心覆盖以及实际依赖；结果绑定合并候选完整身份。

文档、基线及核心覆盖登记在同一候选更新。只通过文本合并或文档检查时保持 `pending-verification`，不能宣布升级可发布。源码/依赖/配置改变后复验受影响证据。

## 5. 正式集成和发行

由单一集成者复核正式主干是否前进。主干仍位于已验下游基线时，可在其干净工作区使用 `git merge --ff-only <已验集成分支>`；已前进则先重新组合并验证差异。

上游合并保留 merge 提交与 ancestry，随后读回 `git merge-base --is-ancestor <新上游 SHA> <正式主干>`。更新生效上游记录，按独立授权推送正式主干、创建发行标签并走[原生部署](native-deployment.md)。推送使用普通快进规则，已发布历史保持稳定。

上游集成结果不自动替换运行包。失败候选、冲突决策、回归证据和已发布版本均可追溯，回退运行版本按发布恢复规则执行。

## 参考

- [Git merge](https://git-scm.com/docs/git-merge)：合并、冲突和 abort。
- [Git rebase](https://git-scm.com/docs/git-rebase)：提交重放与共享历史注意事项。
