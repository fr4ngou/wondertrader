# 2026-10-20 原生发布、上游维护与测试盘点

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：调查及文档验证记录。状态：pass（文档与操作步骤验证）。范围：部署与更新方案、长期规范来源对照、静态测试盘点；不在实际项目执行原生构建、上游合并、部署或账户操作。

## 输入身份与方法

WonderTrader 源码基线为 `08b230dd05facf6d650d949bfe51054115a2ecb1`，原生源码未修改；本地为 shallow/partial/sparse checkout。读取当前源码、构建目标、启动器、插件加载与测试入口，并查询第一方 GitHub 元数据及 Git 官方手册。

QMT 参考工作区为 `D:\workspace\qmt`，只读核对 AGENTS、开发流程、文档治理及相关 ADR。逐文件 SHA-256、观察 HEAD、测试声明与 API 结果摘要保存于机器盘点（外部历史/待归仓路径：`2026-10-20-test-inventory.json`）。QMT 文件可能处于并发开发中，引用以实际读取文件摘要为依据，不将快照当作对其他任务的写授权。

## QMT 方法承接

前一轮使用通用 Bootstrap 骨架并参考 QMT AGENTS 与已确认原则；本轮进一步对照正文，保留可长期使用的方法。

| 参考来源 | 提炼的方法 | 本仓库唯一正文 |
|---|---|---|
| AGENTS、开发流程 | 先看总体调用链与事实所有者，按任务读取组件；根因回归先于送审 | 开发流程、架构及模块说明 |
| 开发流程审查章节 | full/delta/reuse/none 范围理由；独立审查依据最终规格和代码 | 开发流程 |
| 开发流程任务与证据、ADR-0358/0416 理由 | 绑定内容与环境，按影响选择并复用有效结果 | 验证规范、测试手册 |
| 文档维护机制 | 当前规则、规划、历史分层；唯一正文；已合入历史通过后继更正 | 文档规范 |
| 开发流程字段口径要求 | 注释解释业务定义、来源与消费者，回归使用可区分语义样本 | 注释规范 |
| AGENTS、ADR-0351 | 唯一集成者、正式源身份、注释标签与实际运行身份分离 | 开发及发布规范 |
| AGENTS 发布完成条件 | 真实调用链、中文界面、核心数据、主要操作和异常/空/恢复验真 | 发布规范、测试手册 |
| 受控授权边界 | 构建/部署/交易权限分别核对，故障时保留事实和未知结果 | 发布与故障处理规范 |

ADR-0358/0416 在读取时标为 Proposed，本记录引用其问题与方法，适用要求还与当前 AGENTS/开发流程核对；不把参考 ADR 的状态复制为本系统 Accepted 决策。不搬入原 Compose 命令、旧任务流水、账户值、阶段特定兼容分支或原工具已经自动生效的假设。

## 部署事实与方案范围

- 原生 `WtRunner/main.cpp` 支持 `-c/--config` 与 `-l/--logcfg`，先配置后运行；`WtHelper` 将默认生成状态放在工作目录的 `generated/`。
- Parser/Trader 插件存在工作目录优先、实例目录次之的搜索行为。包级验收必须检查实际加载路径，避免旧插件覆盖目标发行包。
- 上游 `docker/Dockerfile` 描述 Linux 编译环境，不能据此推断已经提供本系统运行镜像与部署流程。二进制包可用于 Windows 原生组件，兼容服务仍可使用容器。
- [新方案](../specs/native-release-and-upstream.md)为 proposed，[原生手册](../runbooks/native-deployment.md)明确列出待交付的打包/完整校验/监督/切换入口。示例清单不是发行制品，文档片段未作为生产工具交付。

## 原生测试盘点

在固定基线 `src/TestUnits` 下静态发现 11 个 `test_*.cpp` 文件、16 个 GoogleTest 宏声明；数量表示源码声明，不表示编译 collection 或通过用例数。部分源码涉及文件、LMDB、共享资源及固定外部路径，不能统一视为纯 UT。

| 入口 | 已观察能力 | 结论边界 |
|---|---|---|
| `TestUnits` | GoogleTest；转换、工具、存储/共享资源、手续费等源码 | 未在本轮构建/运行；实际支持与通过未知 |
| `TestParser` | 加载配置和 Parser，接收回调，等待人工输入 | 接入调试工具；缺配置也可能 return 0 |
| `TestTrader` | 交互菜单、查询、登录、委托与撤单 | 可产生真实副作用；不自动运行 |
| 各 `Test*Porter` | 原生导出接口、回调与回放/执行调试 | 需配置和人工步骤；不是完整系统 E2E 通过证据 |
| `TraderMocker` | 仿真交易后端 | 可用于测试链；编排、确定输入和自动断言仍需核实/补齐 |

已检出的 CMake 文件中未发现 `add_test/enable_testing/gtest_discover_tests` 注册；固定 Git 树未见 `.github/workflows`。GitHub API 本轮只返回动态 `pages-build-deployment` 工作流，releases 列表为空。这些观察不能证明外部机构没有独立测试；它们不足以建立本系统已经具有充分自动化 E2E 和发布流水线的结论。

后续优先补齐系统关键链路的隔离 E2E、故障恢复、原生 SDK/终端只读验真及包级部署恢复。现有组件尽量复用，按照输入、断言和覆盖范围决定资格。

## 本轮验证

| 检查 | 结果及范围 |
|---|---|
| `python -B scripts/project.py check` | exit 0；文档链接、索引及技能清单完整 |
| 两份操作手册内 PowerShell 片段语法解析 | pass；只解析，未执行真实升级/部署命令 |
| 隔离 Git 仓库演练 | pass；merge 保留上游祖先与自有文件、正式分支快进已验合并、冲突显式可见、abort 恢复原干净候选 |
| JSON/示例清单及盘点范围核对 | pass；示例保持 `example: true`，源码声明与实际通过数量分开 |
| 长期规范范围审查 | pass；不含专项选型、机器路径、日期和任务进度 |
| `git diff --check` | exit 0；空白检查通过 |
| `git diff --exit-code HEAD -- src` | exit 0；实际项目原生源码保持原样 |

机器结果在忽略目录 `.tmp/native-release-upstream-checks/result.json`，共 12 项通过；临时 Git 仓库和 worktree 均位于该隔离目录，不与实际运行或主干集成相连。演练后仅修正文档用词，保留未变化的 Git 演练通过证据并重验文档范围与项目索引。

代码、SDK、原生进程、制品、部署和交易资格不属于此通过范围；没有构建二进制、运行原生 UT/系统 E2E、在实际仓库 fetch/merge/rebase 上游、推送或发布。

## 第一方依据

- [上游 Parser 文档](https://github.com/wondertrader/docs/blob/main/source/docs/cpp/parser.md)：原生模块、动态依赖与发布构建说明。
- [固定基线 TestTrader](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TestTrader/main.cpp)：交互与真实副作用入口。
- [上游 GitHub Actions](https://github.com/wondertrader/wondertrader/actions)：结合 API 和固定源码树判断自动化证据范围。
- [Git merge](https://git-scm.com/docs/git-merge)、[Git rebase](https://git-scm.com/docs/git-rebase)：历史与冲突操作语义。
