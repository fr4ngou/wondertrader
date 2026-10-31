# 受管CTA产品安装与多策略主链

类型：验证记录。结果：partial，STQ-P19 fresh产品切片通过；完整模块B与自动恢复继续in-progress。关联：STQ-P14–P19、B-03/B-04；原生金融账本与绩效复用，新增金融账本0，新增WT核心修改0。

## 输入身份

独占原件根`build/ms-product-003`。固定上游/已批准覆盖继承`build/ms-account-002/composed/input.json`的610项来源；产品快照在此基础叠加自有main、StandardExecutionHost类型边界、Session故障传播及CMake/专属测试。`BUILD.json`、`composed/input.json`和最终`DELIVERY.json`登记精确源/二进制/工具命令身份。共享脏树其他框架修改未据此进入构建。

实际产品：`GuanhengCtaHost.exe` SHA256 `3b7aa40f47fe81f8e7c2a5c612b40f5a8af182613995b3fb92e27587a286f2f7`；`TraderQMTStandard.dll`为`b7146f7e511c6a8b200dce889a9614b49ba9404702b9c9fb1849a7d193e6e9ed`；原`WtExeFact.dll`为`2c72aa5d4ee6d434b9552c2bc4b645c8cec5a5cdca2bdca52d3841228feb58e6`。App wheel0.1.0a4为`f8973f59ecb0779cf2936dc4ba758d06eac32b31ed5a9ad544e3db87d0a9ed5e`，实际安装到`python-install-002`后导入，运行入口断言安装路径。该wheel包含当时App输入，C负责后续统一App候选；B只交薄execution_process装配。

MSVC x64 Release、C++17、Python3.12.14，原执行时钟使用系统时间；行情显式注入未来工作日模拟分钟，SDK账户日期仍为夹具固定日，属于隔离调用链。价格10.01、手续费0、合成现金30000，真实资金/T+1/税费资格没有由该输入获得。

## 安装后主链与观察

`tests/integration/qmt_cta_product/run.py`消费实际CMake install、安装App包、显式合成策略/Parser/Reader。每轮复制安装并登记工件摘要，用配置驱动原exe→原Factory/CTA ticker→固定A/B→原汇总/唯一owner→原MinImpact/Adapter/Standard→真实Host/WinSHM→SDK替身。源端记录调用线程/令牌/顺序；没有加载真实券商、操作QMT或真实下撤单。

| 场景与原件 | 真实替身调用及原生策略状态 | 结论 |
|---|---|---|
| `final-add/RESULT.json` | 一笔买1000；A600/B400 | pass |
| `final-exit/RESULT.json` | 券商1000；一笔卖600；A0/B400 | pass |
| `final-net/RESULT.json` | 券商1000；A800/B200；委托0 | pass |
| `final-pending/RESULT.json` | 券商600；买400；活动余量400查询；后续tick没有重复提交；6查询 | pass |
| `final-partial/RESULT.json` | 买1000；同令牌成交回报500；后继查询P500/U500；A600/B400；后续tick没有重复提交；7查询 | pass |

每轮同时核实际策略原JSON、关闭收据、退出/整树回收、双管道EOF/读线程join、Host/源端资源及server/proxy线程；无force、无pending。双管道有实际非空字节，关闭后原监督器清除私有缓冲。最终矩阵`MATRIX-FINAL.json`五案全部通过。

内部开发组件`GuanhengExecution-fresh-dev-candidate-003.zip` SHA256为`49f34d834c47f3f47f6ec381e701a0d3fffc3e55d8927b3356136a8e88154322`，包含实际native安装、匹配App wheel和第三方许可证；运行库、App依赖及正式数据/策略插件按组件要求另外装配。实际解压搬迁、逐工件核哈希、从归档wheel重新安装后，`moved-main/RESULT.json`再次通过买1000及完整关闭；此为组件安装资格，完整统一发行继续待验。

## 根因修复与坏例

自有宿主公共配置原先直接调用WTSVariant布尔getter，容器会进入非法字符串解引用。修复统一在StandardExecutionHost准入核类型，原Adapter/Local/执行算法继续消费同一对象。`execution-fault/RESULT.json`通过22类公共类型拒绝，以及原pump返回非负计数但故障已锁存时Session立即失败并关闭；4查询、0委托、2策略删除。

薄App适配原先缺少max_output_bytes；现在每管道256KiB，实际双管道输入已验。启动验证还重新有限遍历库集合；安装后`test_deployment.py`验证load之后增加extra.dll，在Job创建前拒绝，保持faulted且无pending。配置拒绝的close返回false代表此前失败，资源回收另外核。

| 安装入口坏例 | 观察 | 结论 |
|---|---|---|
| `boundary-existing-state` | 4查询；行情/策略未启动；原文件字节保持；子收据ok=false/error_code=cta；0委托；父回收完成 | pass |
| `boundary-account-busy` | 同账户/环境/profile的OS mutex已被另一owner持有；0查询/0委托；子阶段account_lease；父回收完成 | pass |
| `boundary-trader-container` | position_by_query为对象；0查询/0委托；子阶段trader；父回收完成 | pass |

父监督状态当前保留unexpected_exit等生命周期错误，子收据另含固定阶段；完整业务中文错误及公共账户/策略/命令投影仍由后继接口与C组合。

### 间歇关闭异常的实际根因

旧来源`main-003`发生0xC0000005；诊断来源`stress-008/feed/crash.dmp`再次捕获，`CRASH.json`及同对象链接MAP定位：`WTSPoolObject<WTSTickData>::release+0x2c → WTSHashMap::release → WtDtMgr::release → CtaExecutionSession::close`。独立原生栈证明来源worker的TLS pool已经随join销毁，DtMgr仍持有tick。产品未新增绕过分支。

修复在测试来源`native_realtime_strategy/synthetic_parser.cpp`：独立堆分配OwnedSyntheticTick，完整复制原WTSTickStruct，沿原WTSObject原子引用计数最终虚析构。复用正式QmtPollingParser已存在的OwnedPollingTick边界，保持WT池和核心原样。最终普通夹具主链`STRESS-FIXED.json`20/20通过，再用普通夹具重跑上述五案；诊断filter仅在独占build诊断DLL，正式测试来源不携带filter。失败原件保留，不计为成功。

## 独立审查与限制

独立review_execution已静态核完整产品装配及后继修正：公共类型、新增库、输出容量、Session故障传播、策略/插件生命期和OwnedSyntheticTick释放；未读取运行报告。其初审发现已按根因修复；最终测试增量按REVIEW.json登记。运行结果由本owner逐项核验。

当前证明fresh安装产品链与上述拒绝条件。自动恢复仍固定recovery_ready=false，原状态根拒绝；最小原生保存结果提案待用户批准。真实业务configured算法/历史与实时桥、公开状态/动作投影、完整取消/部撤矩阵、资金/T+1/真实费用桥及异常跨进程责任交接均继续模块B，当前结果不关闭整个模块目标。真实四查询与统一A/B/C安装/中文页面另按同候选验；真实下撤单、生产切换保持独立授权。

本轮project.py check一度受C正在新增的strategy-configuration-workspace.md未入索引影响；B交接文档连接实际消费的SCW合同后最终检查PASS，不把文档检查解释为应用/实盘资格。
