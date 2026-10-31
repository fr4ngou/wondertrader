# 原生实时单轮数量与八目标接线

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：SDK0合成单轮范围通过；完整实时执行及生产资格继续待验。依据[NRT-R4/R7](../specs/native-realtime-strategy.md)及最终测试规范（外部历史/待归仓路径：`../../tests/integration/native_realtime_strategy/TARGET_E2E.md`）。

## 根因与修订

最初多轮测试将Bridge回调归零作为下一轮feed门槛；原Context/Engine/ticker仍有本轮尾部动作，该门槛不能证明整轮完成。revision001只做静态审查，执行0并保留。revision002使用两个独占child，各仅一次真实SCHEDULE，之后只request_stop，由控制器原stop/join核整轮退出；没有后继feed。数量输入直接消费epoch入口冻结价格，字面11只作人工oracle。产品Bridge/Reader/Factory、WT与数量算法均未修改。

## 实际链与结果

| 范围 | 实际观察 | 原件 |
|---|---|---|
| 缺价与非法完整向量 | 16次初始feed；INIT错阶段、缺589000报价及10项结构/数量反例共12次API调用；setter进入0、投影不变；1 BAR/1 SCHEDULE | 负向child（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-target-runtime-001/eight-target-preflight-stop/child-result.json`） |
| 原价与数量 | 18次初始feed；同一epoch先复制8价11，再从真实Reader复制9×125日线，历史读后原价缓存变10；唯一core输出32/225，数量fixture消费冻结11得1200份，显式历史价10反例得1400份 | 正向child（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-target-runtime-001/raw-price-core-eight-target-stop/child-result.json`） |
| 完整8目标 | 向原setter提交[0,1200,0,0,0,0,0,0]并原ABI读回；setter进入8，包含7个明确0；589680只供信号，589000为执行证券 | 同上正向child |
| 无后继feed与正常关闭 | 两child各唯一SCHEDULE；末初始feed至回调分别10.031/5.000秒。原stop/join后parser进入/返回仍16/18、active0/connected0；策略created/destroyed1、Reader真实join/关socket、child exit0/Job已reap/双EOF | 父结果（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-target-runtime-001/result.json`）、外层（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-target-runtime-controller-001/build-native-realtime-target-runtime-001/result.json`） |
| 共享工具兼容 | 最终共享驱动重跑原默认ABI两例全部通过；原9方法/10场景通过，无跳过 | ABI后继（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-abi-runtime-002/result.json`）、纯回归（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-target-helper-pure-controller-001/build-native-realtime-target-helper-pure-001/stdout.txt`） |

三外层分别30.531/25.421/0.594秒，code0、无强杀/控制台、tree0、双EOF、读线程join、资源关闭。沿唯一原截止及普通安装a5核/已安装数量模块、原四DLL执行；真实SDK/委托/撤单0。

## 独立复核与资格

002独立delta（外部历史/待归仓路径：`../../build/native-realtime-target-independent-delta-002/REPORT.md`）确认F1/F2关闭；动态独立报告（外部历史/待归仓路径：`../../build/native-realtime-target-dynamic-independent-002/REPORT.md`）核666份原件、399固定源、20冻结工具、16份DLL复制及安装13源码/收据，逐字段核1125日线一致。审查执行0；根复核666raw、当前56输入及三controller，见收尾（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-target-closing-001/VERIFIED.json`）。26份框架保护文件保持本轮基线。

Basis中的native_nav_verified=True仅是显式合成数量fixture的算法输入；native_basis_qualified仍false，不代表原生现金/NAV已认证。原actual/pending KNOWN位仍0且数量NaN；原API的pending回显不能改称券商持仓或成交。无Observation/advance，本批不认证后继理论结算、多轮完成fence/目标覆盖、T+1、真实来源、正式Host/用户入口或生产。完整NRT和整体迁移目标保持in-progress。
