# 2026-10-23 个人观察自选候选与静态复核

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：partial；实现候选未应用，运行not-run。关联[个人观察规格](../specs/personal-watchlist.md)PWL-R1–R18、[ADR-0008](../architecture/adr/0008-personal-watchlist-ownership.md)及[完整业务范围](../migration/business-feature-inventory.md)。

## 输入和已成立结果

设计已独立full静态复核并落地七项文档，原始记录见[账户阶段记录中的后继](2026-10-23-qmt-shm-account-read.md)。当前live规格SHA为4ba3c3331a6a3f162b7ed71e948fcfbe0ca95735d1a078d00daf85213df5c786；本轮锁及路径修正对应后继规格仅在staged，未覆盖live。

后端001由root实现，session_product独立full静态审查gap-static。根核261份审查原件，0差异；报告REPORT.md（外部历史/待归仓路径：`../../build/guanheng-workspace/native-watchlist-backend-static-review-001/REPORT.md`）SHA464c2fe8f7e2046ca0a962538e4cc25da1634b16923fa76ccc766fb8f6bdc05f，manifest44e8c87f291d3121df9bbfa75357dce3bb348fa09741fc0a18a283cb0507635f。PWL-B1/P2为首次创建锁文件与后续locking之间的竞争窗口，PWL-B2/P2为resolve后实际本地支持域未复核；另C1/P3为typed字符串先完整编码后核容量。全部为静态发现，未动态复现。

root在独占backend-fix-002（外部历史/待归仓路径：`../../build/guanheng-workspace/native-watchlist-backend-fix-002/review-package/review-input.json`）中修正19项最终候选，包含沿用15项、WindowsLease/纯回归及规格/ADR两份说明。入口SHAcb04833326139dc1cf24b69c49de727dc518205523b420d9087704a56ee70632，manifestc4737e5e4ed988fdacd6504d597d895683d7171b434a641e79159fb7624bd738。242最终来源、8before、252制品及19项live before/缺失状态已根核0漂移；交不同作者独立复核，尚未授修复通过。

## 正确实现候选

- 锁由CreateFileW share_mode=0在单次OS动作中创建并取得排他性；新根用CREATE_NEW，已有资料用OPEN_EXISTING。竞争实例无法在新文件出现后抢先成为初始化者；已有lock-only仍保留资料并拒绝静默重置。
- 句柄、CRT descriptor和借用stream分别有明确归属。stream使用closefd=False；每阶段成功后先保留实际资源再检查迟到，失败和关闭未知仍可由原owner续核。在途非零时不释放锁。
- 原盘符和resolve后目标都核绝对本地drive及GetDriveTypeW；UNC/device、网络映射和未知类型拒绝。typed root/symbol/reason先核字符数量，再分配UTF8字节核实际预算。
- HTTP、完整列表CAS、原子文件替换、公开DTO及根前端API的其余逻辑保持原候选；CI仍使用同一个目录selector，自然包含新增锁测试文件。没有新增WT核心修改或旧QMT运行依赖。

## 页面独立修正复核

UI001由session_product实现，root独立full发现跨页面丢失待核完整目标PWL-UI-F1/P2，另C1/P3为维护后能力刷新提示不准确。原候选与报告保持冻结。

UI-fix-002由另一作者在新目录实现，七份完整候选中三份变化。入口SHA9df4e9187a25b31a0c4afc55bf873951641c25c91f3452bee5cf0b8243d9f547，manifest e3ea635295152ae1a50d669afbdc14990630f0c18871621ae63dbdcbcf736efb。root逐项核44候选制品、19原来源及7项live before/缺失状态，另冻结4份实际入口依赖，0漂移。

独立delta报告（外部历史/待归仓路径：`../../build/guanheng-workspace/native-watchlist-ui-static-review-002/REPORT.md`）结论complete-static，原F1/C1 closed-static，无新增P1/P2。报告SHAd1b758e5e56a5df9d3d3e106cc8c8836db0064dd781246cbefc4a7690ad692ae，审查入口0e80f574b3dea4e6058bc97899c5475e9de7c8ad59ada3aa3c39e142ed1fda3c，manifest c5013d70c99edd5ce5746c8bc1bfbf49ce39f7d9bd2bdf35ea1a559d03e708af，44审查制品。

同QueryClient的有界WeakMap owner保留唯一完整目标、原ID、最低版本与待核阶段；路由卸载只取消订阅，PUT成功/错误继续归原owner。GET在PUT未收口时保持门禁；收口后只在ID/最低版本/完整顺序同时匹配时解除待核，否则明确确认当前列表。GET失败保留目标，不自动重发PUT。维护提示明确刷新整个页面重新读取能力。原公开API由不同作者后端审查，root未借UI复核给自有API授独立资格。

## 验证登记和限制

| 项目 | 实际观察 | 资格 |
|---|---|---|
| 后端full原件、fix002来源及before | 261审查原件、252候选制品分别匹配；19项live保持原身份 | 静态身份核对 |
| 页面fix002与独立delta | 44候选及44独审原件已固定；F1/C1静态闭合 | complete-static |
| 后端测试 | 56个Python具名定义，16个TS it定义；12选择器/26文件 | 语法/类型/收集/执行均0 |
| 页面测试 | 30个test/test.each声明，含跨实际路由12行矩阵及两项对照 | 收集/执行均0 |
| 构建、HTTP、浏览器、重启、安装及SDK | 未启动 | unknown/not-run |

闪窗具体归属仍unknown，所有新进程/解释器/import/编译/测试/网络/浏览器/SDK/CI调度继续暂停。Windows共享/文件系统行为、目标CPython3.12及正式保存→关闭→重启→中文页面仍需实际验证。当前业务实现未应用，账户45场景仍2 implemented-unverified/43 pending、运行0，新schema2 guard关闭。完整策略/实时执行、真实全市场覆盖、其余配置/观察/运营和独立发行差额继续；整体目标active。

## 后继：后端002闭合与前后端联合落地

后端修正002不同作者独立复核complete-static，原B1/B2/C1全部closed-static，无新增P1/P2。入口e7e5d884d2969a7f85a8249fa58015e68f1b5f492e970becf08443bcc8d1d0e1，报告REPORT.md（外部历史/待归仓路径：`../../build/guanheng-workspace/native-watchlist-backend-static-review-002/REPORT.md`）SHAd364288843bf9ad6da228df08b6034b24fcd65f1efe1d05b7cf520c9adf0f891，manifest5943a6156cd67ff623f84e48e142cb7df8620dbebbb7dd6050148084e263ba7a；274份独审原件已根逐项回核匹配。

基于后端002与UI002两份独立静态结论，26项自有源码、测试、配置、CI和规格文档已作为同组落地。联合应用回执（外部历史/待归仓路径：`../../build/guanheng-workspace/native-watchlist-joint-apply-001/apply.json`）SHAd517c3413e2268de860aa59ba721f4214b5a8c29433774aa193bbde937bc9652，保存11份原文件和15项新增身份，逐项写后核对及261项组合来源post均匹配。UI引用的规格/ADR和后台引用的壳/分钟页上下文按同组最终文件明确替换；UI相关R9–R16正文仍逐字相同，未把组合上下文变化隐藏为原输入不变。

源码现在包含GET/PUT路由、owner、严格API与实际SPA页面接线，配置默认空关闭；没有启动应用、修改实际用户偏好根、打开账户新来源或进行交易。业务模块与F08清单同步实际入口。语法/类型/收集/构建/运行/HTTP/浏览器/安装/重启仍0，窗口归属unknown，生产未切换，WT框架及旧QMT工程未修改。此后继将前文“候选未应用”推进为“源码已应用、运行未验证”，不能登记整个F08或系统迁入完成。


## 2026-10-23 受控恢复后的安装与生产构建

用户已授权恢复受控隐藏验证，本节接续前述暂停及运行0状态。以当前缺口审计（外部历史/待归仓路径：`../../build/guanheng-workspace/retained-business-current-audit-20261023-002/REPORT.md`）定位PWL-R18；产品仍是联合落地的原实现，本轮产品源码修改0。

独立安装与静态身份（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/installed-source-static-identity.json`）逐字节核对正式非editable安装的28份App源码与当前树相同，包含8份PWL产品模块。安装来自组合002的独立CPython3.12.14 App环境；没有覆盖site-packages或导入旧QMT工程。源输入165项冻结于source-inputs（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/source-inputs.json`）。

真实已安装App运行后端回归（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/python-tests.xml`）：112 passed，0失败，约4.29秒；测试依赖单独从受管环境追加，产品来源限定安装目录。Windows真实文件/锁与注入异常各沿具名断言，不把同进程owner重开计作进程重启。FastAPI测试客户端输出一条HTTPX弃用提示，结果保留。

当前SPA四个文件的前端回归（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/frontend-tests.json`）103 passed：个人观察36、独立壳22、分钟接线6、严格API39。组件和模拟传输的资格保持此层；真实HTTP持久化及浏览器另验。

新生产SPA构建（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/frontend/build-result.json`）完成TypeScript、Vite生产编译和原分块预算检查，8个制品保存在新专有frontend/dist，旧dist保留。首次协调脚本把浮点剩余时间传给Node整数timeout，实际在任何编译前退出1；修正仅在后继协调脚本取整，同一原D不续期，重跑通过。原失败和成功均存受控回执（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/verification-receipts.json`），均未强停、整树归零、管道EOF、reader join和资源回收。Vite未来native配置加载提示及新outDir不自动清空提示保留，没有为取通过扩展产品修改。

本节尚未登记PWL-R18完成：真实HTTP→文件→正常退出→新进程同根→生产SPA和360px页面正在补验；行情/账户/交易未启，当前运行QMT与生产应用保持原状。


## 正式安装与生产SPA真实用户链后继005

维护测试入口（外部历史/待归仓路径：`../../tests/integration/watchlist/pwl_user_chain.mjs`）及真实App入口（外部历史/待归仓路径：`../../tests/integration/watchlist/pwl_app_entry.py`）已落本仓库，匹配最终夹具005（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-fixture-005/manifest.json`）。调用方显式提供发行源码SHA映射、正式安装解释器、新生产dist及专有全新偏好/结果/截图目录；QMT/账户/回测来源保持未配置。测试复用原ThreadOwner与真实create_app/WatchlistOwner，浏览器连接专有隐藏Edge，不替换HTTP或持久化owner。

最终实际结果（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/browser-run-005/result.json`）约15.194秒、exit0：

- 实际/market标题“观衡量化平台”，有效空→键盘加入600000.SH→加入510300.SH→移除600000.SH；三次UI动作各一次PUT，最终版本4。
- 第一个App自然退出，新launcher及实际Python进程同根读回同UUID、版本、updated_at和剩余有序列表；在360视口移除最后项，版本5并保持原UUID。
- 同N两不同真实HTTP PUT得到一200/一409；成功响应绑定对应完整请求，GET与主文件五持久字段在清空前核同，然后才显式PUT清空。
- 第二App进程无法取得同根writer，GET/PUT均503、health200且原主文件不变；真实生产页中文不可用、无添加按钮、零自动watchlist GET。原writer正常退出后新进程同根恢复相同快照及编辑能力。其他HTTP方法DELETE为405。
- 四个360状态均以documentElement.clientWidth排除垂直滚动条后检查scrollWidth；实测innerWidth360/clientWidth345/scrollWidth345，整体宽度门槛通过。布局明细最多前512元素/32行，仅作诊断，未授敌对DOM硬内存隔离。
- 浏览器warning/error和pageerror均为空，框架overlay0；应用/浏览器可见请求无行情、账户、交易或退役API。四个App及Edge均实际close/exit0，所有reader/在途/lease归属按各自实际事实收尾；外层Job自然整树归零、EOF、reader join及资源关闭通过。没有修改或重启现运行QMT/Host。

完整回执索引（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/verification-receipts.json`）保留001失败和002–005各自结果。001将Windows标准venv launcher PID与实际Python PID混同，且浏览器正常缓存深8超过夹具通用深6；App自身正常关闭不抹去整轮失败。后继保留launcher/实际PID/parent链和同ready/closed身份，profile使用独立深12、2048文件/64MiB后检查，static仍深6。早期002绿灯只授当时判据；独立full指出非空360、PID与CAS清理前持久确认三项P2，003补严、004增加真实异常/恢复、005按clientWidth精确核宽。产品源码始终不变，原红/绿记录不回写。

最终独立delta005（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-independent-review-005/REPORT.md`）complete、新增问题0、静态执行0；其前置full/delta逐次范围保留。根复核244份来源（外部历史/待归仓路径：`../../build/guanheng-workspace/pwl-user-chain-001/final-independent-root-check.json`）无漂移，维护两文件与最终已运行字节相同。软件112+103、独立安装28模块、生产SPA8制品及实际用户链分别取证。

资格为Windows CPython3.12.14/Edge155/Playwright1.62.1专有开发安装的个人观察核心用户链；坏文件/tmp/迟到提交等异常沿112项原测试的实际层级，真实TCP断连及全部故障浏览器矩阵没有借此扩授。此专用E2E入口尚未登记托管CI实际运行，生产实例未切换。F08配置版本/激活回滚、F03实时策略、F18/F20及整体迁入继续active。
