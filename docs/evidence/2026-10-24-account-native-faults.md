# 2026-10-24 原生账户故障与普通数值矩阵

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证证据。状态：同源码QA输出/关闭切片及普通EXE补充矩阵通过；原45场景完整资格和公开schema2门禁保持关闭。

## 自有测试接缝与原生构建

新增同源码QA（外部历史/待归仓路径：`../../tests/integration/native_account_scan_fault/README.md`），调用原GuanhengAccountScan/main.cpp的scan、普通TraderQMTReadOnly DLL和固定原TraderAdapter。默认OFF的GH_ACCOUNT_FULL_SCAN_TESTS只新增独立测试目标，不安装到产品，不修改WT框架。首次编译中根将WTSVariant.getString误认为指针而改strcmp；真实声明返回std::string，已恢复原值比较，失败日志保留。增量编译通过并完整回收，源码和有效overlay封存。

构建结果（外部历史/待归仓路径：`../../build/native/account-full-scan-001/result.json`）记录普通EXE SHA adafbd8bab79d3abc6d93e08a2a4da3e6c5712eb3e91d458cd05e10d59dc9278、普通DLL SHA 2a150698a0a12933453c6b41118a9aca1ef8f4c0db8bf9bcad32a4c48ff63c5a、QA EXE SHA 59da6697d7bebc6f40b441c903a93df639dd0e6eae284884fe543e247d59af83。上游固定08b230dd的实际snapshot与自有来源分别登记，活动树其余差异不进入本构建资格。

## 同源码输出故障运行

冻结34成员验证包（外部历史/待归仓路径：`../../build/guanheng-workspace/account-full-scan-live-001/inputs.json`），使用普通独立安装的App/Host解释器，合成三参数SDK，经真实旧kind=shm Win32传输、Host及普通C++账户映射完成四查询。该组测试不使用实际QMT，也不授builtin运输或目标3.6.8资格。

一次独立control及九配方各一control/一fault，共19次原生运行、76次SDK替身调用。每轮保留原stdout/stderr、来源绑定、实际退出与父端资源回执。结果见九类汇总（外部历史/待归仓路径：`../../build/guanheng-workspace/account-full-scan-live-001/faults-result.json`）。

| 故障 | 故障轮实际native exit | 关键事实 |
| --- | ---: | --- |
| prefix短写 | 2 | 只写2字节，无重发 |
| body短写 | 2 | 保留部分帧，无补帧 |
| observation flush失败 | 2 | 输出owner永久失败，仍关闭API |
| closed后completion短写 | 2 | API已关闭，部分终态不冒充成功 |
| 未join时completion短写 | 4 | 保留API/依赖，无destroy，进程失败退出 |
| 原D后prefix返回 | 4 | 原D不续期，内部关闭unknown保留 |
| 原D后body返回 | 3 | 实际关闭后仍拒绝成功退出 |
| 原D后observation flush返回 | 4 | 原D耗尽，内部worker仍活的事实保留 |
| 原D后completion flush返回 | 3 | 完整帧不能覆盖晚返回失败 |

10次control native exit0；故障exit2共4、exit3共2、exit4共3。所有故意exit4的原件保持内部joined=0/destroy=0/API retained；其中unjoined注入轮worker_live=0，两个late轮worker_live=1。外层tree0、管道双EOF和父端reader真实join只证明子进程树与父端读取资源收口，不能写成内部API已完整释放。

九配方保持CLI exit3/full_45_qualified=false；外层汇总脚本逐项检查该实际退出及原件后exit0，非forced且tree0/EOF/join/资源关闭。独立control的内部断言完成/native0与外层非零失败回执分别保留，不把内部JSON当外层成功。源码静态full见QA报告（外部历史/待归仓路径：`../../build/guanheng-workspace/account-full-scan-qa-review-001/REVIEW.md`），实际原件见独立核证（外部历史/待归仓路径：`../../build/guanheng-workspace/account-full-scan-live-review-001/REPORT.md`），201份来源核对保留有效证据零漂移与导航索引并发变化的区别。

## 普通EXE数值与异常矩阵

普通程序另跑正常/空组2轮、四阶段SDK异常4轮、四阶段SDK超时4轮、显式新观察2轮，共12轮。原来的第一版测试只核facts，独审发现position/order/deal ABI漏核，以及CLI前置错误可能绕过3/4出口，两项P2已在测试责任层修正。产品源码无错值证据，不将测试缺口称作WT缺陷。

第二版独立固定期望覆盖5行65个ABI槽的值/type/mapping，逐槽篡改但facts保持的反例必须拒绝；完整原D和owner finally保持。CLI缺参/help/错身份/registry/发布失败统一去敏4，正常开发配方仍3；QA同类出口也已修，并保护诊断写本身失败。修正后定向403项纯回归通过，追加六项QA错误入口回归已单独通过，不能与前序323简单相加。

第二版原件（外部历史/待归仓路径：`../../build/guanheng-workspace/account-ordinary-matrix-002/matrix-result.json`）四配方全部断言完成：正常/空组与刷新native0；各阶段异常/超时native3，SDK调用前缀分别1/2/3/4。所有CLI3、full45=false；受控外层exit0/非forced/tree0/EOF/join/资源关闭。测试清单SHA 3f8d3ac62e856c74a4eb6066307f47fde75162065c8a791a1499077c02e19f13。首次gap报告（外部历史/待归仓路径：`../../build/guanheng-workspace/account-ordinary-matrix-review-001/REVIEW.md`）保持，后继delta（外部历史/待归仓路径：`../../build/guanheng-workspace/account-ordinary-matrix-review-002/REVIEW.md`）关闭两P2且无新增P1/P2，运行证据另分层承担。

## 资格与剩余范围

原45定义及registry未改，仍3 implemented-unverified/42 pending；新增配方是明确补充证据，不通过改注册状态缩减验收。完整wmain文件/哈希/加载/基础资料/异常视图等剩余确定性接缝、App并发/父死亡、真实C++账户→业务HTTP/中文页、builtin现场整链及正式独立发行继续。真实行情/账户源证据保持[10月23日原范围](2026-10-23-qmt-memory-account-read.md)，所有源/金融值/运输/关闭资格分别使用对应制品。
