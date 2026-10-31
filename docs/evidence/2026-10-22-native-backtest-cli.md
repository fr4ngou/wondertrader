# 原生回测操作员入口开发验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证。日期：2026-10-22。状态：18项CLI测试、独立安装与3条实际命令通过，独立full进行中；依赖NSB/NSH和完整业务资格分别验收。

## 输入与实现

最终要求为[NBC-R1–R4](../specs/native-backtest-cli.md)。`backtest_cli.py` SHA为`b25eaa81f94754f978fb76bf3d98cb476f975b9b15ac7200be8ae22c019a6bea`，通过`python -I -B -m guanheng_app.backtest_cli`读取受管安装绑定及冻结会话。文件准入复用父宿主检查，读取耗时扣除后再交唯一NSH运行owner；信号仅设置cancel事件。stdout只输出有限ASCII JSON收口回执，完整历史保留原宿主输出，不装配账户或交易插件。

本次安装位于`build/guanheng-workspace/strategy-cli-001/install-63a7a76def274a278fb8cc6daff983e0`，与NSH审查使用的旧安装保持隔离。正式Flit构建app a2、原core a5/native a1及SDK0.12 wheel，全部生产依赖按uv.lock导出并用hash安装，pip check与安装版本核对通过。新app wheel SHA为`768bd25dcc242eda9d5b6210897694e8019833c15058e7e03dd1f5f09240641d`；未发布候选以内容身份分别登记，相同开发版本不混用旧NAC/NSH整包资格。当前CLI源码与新安装内文件逐字节相同。

## 实际验证

18项测试覆盖冻结值转交、文件容量/类型、消耗读取预算、准入超期、非法binding/期限、正常/繁忙/不完整回执、取消信号与处理器恢复、回执容量。最终XML为`strategy-cli-001/pytest-004.xml`；Ruff及本地文档导航检查通过。替身验证仅授CLI路由及错误语义。

另由受管外层Job启动独立安装的实际CLI，子CLI再通过NSH启动固定原WtBtPorter。三条正式命令均非外层强制终止，外层Job成员退出、wait及管道收口已核：

| 场景 | 实际观察 |
|---|---|
| 普通冻结合成输入 | CLI退出0，运行`40d79dce2e6d442b900f02f19c76d20a`完成，内层2390ms、非forced、exit0/reaped/pipes；5个闭合日期与冻结源日期一致，v2报告存在 |
| 0.1秒紧预算 | 文件/宿主准入消耗预算后拒绝，CLI退出2，未启动内层原生回测 |
| 错误安装摘要 | 准入拒绝，CLI退出2，无成功回执 |

根任务另外读取普通场景原始trades.csv：两笔现金多头OPEN，2024-01-05数量900、2024-01-08数量500，均价格10、费用0，和明确合成输入一致。该例仅证明已测模型及调用链，不授实际市场成交或真实来源。

实际命令/原始stdout和stderr、完整回执及独占原生目录见installed-results（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-cli-001/installed-results.json`）。测试脚本早期错误的原件保留，不计入正式通过场景；修正的是测试入口及期望，产品语义由最终源码身份绑定。

## 封存与限制

审查输入（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-cli-001/final-001/review-inputs.json`）SHA为`a67049c964ff7d8f6bdb4bf3eb287ea6f681b86a2b2d059e9d25561b49d45dab`，source ZIP SHA为`301140a87c6c439755d27489c833fefd800c753d93bfdf536b98d4445347cb1a`，1211项清单（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-cli-001/final-001/manifest.json`）SHA为`3e428459af31f2491f5ee89bfbb2783f966087a9922d19b053b888bfbb53b096`。独立审查由未实现CLI的审查者执行，产品及原安装冻结。

NSH独审已另行存证创建返回后原始句柄接管窗口P2，NSB v2也正在独审；这些依赖的资格不由CLI测试提升。浏览器策略页、其他策略族、真实ETF/辅助输入、实际柜台与生产未验。所有输出在本仓库，不执行旧QMT工程、终端HTTP、SHM或真实交易，未新增框架改动。

## 2026-10-22 后继独立delta

原CLI full发现两项P2：argparse拒绝未进入完整去敏回执；非法日期时分直到DLL装载后才拒绝。责任层已统一解析拒绝，且CLI与Porter共用纯`validate_backtest_window`，Porter原时间块按AST核实为等价抽取，其余算法和ABI保持。

最终CLI SHA `dedebaf489d84b5e38052740071d909c95cdff07d52fd1555ba7efeb53861ea2`，Porter SHA `fdeaf11daf168d096b2edfa1cff48cc29a40b79fc95daa6896a2662895426e29`。独立delta-002（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/strategy-cli-delta-002.md`）complete、无新增gap，报告SHA `dd47afcc74fb3c067984452943e97b549a2d32c18d82e0b781054c877ebece1a`。26安装场景、14时间边界、9控制流反例及34测试通过；参数/时间拒绝均零读取/零Host构造/零子启动/零WtBtPorter装载，完整14字段ASCII无secret，三个实际信号退出130且回收确认。

根任务核对报告与manifest摘要，并逐项回核278原件一致，1个junction仅保存自身metadata而未遍历。此CLI资格绑定新Job和旧Session，后者F3独立修正另见策略证据；新组合应用/浏览器由NBW独立验收，实盘与生产仍未授予。
