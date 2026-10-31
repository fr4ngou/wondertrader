# 持续窗口到同一原 CTA 日线

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块 B 开发与接收记录。状态：同 CTA 四窗口、唯一策略执行及同根两代正常恢复已验；独立审查和增量制品按本根最终收据绑定，普通最终组合继续待验。对应 [NRT-R29](../specs/native-realtime-strategy.md#nrt-r29-持续发布的原生日线读取)、模块 B-04/B-06。全部新增输出在 `build/ms-daily-publication-001`，临时驱动和缓存位于本仓 E 盘；原 AWP 目录只读。

## 根因与实现

AWP 每轮创建新目录，原自有 RealtimeReader 一直复用首次初始化的 WtDataReader，后续窗口和 CTA 日线因而可能来自不同发布代际。原 WtDtMgr 在基础周期倍数1、force_cache=false 时直接调用 IDataReader。此接缝已经足够，当前新增 WonderTrader 框架改动为0。

根团队已将这一 Reader/执行衔接交模块 B 实施。修改范围为 `src/ReaderGuanhengRealtime/Factory.cpp`、新增 `PublishedDaily.h`、本次独占验证入口及 B 规格/材料；公共 AWP、Host、Common 与 WT 源码保持原归属。发布身份、路径、预算及生命周期见唯一规格，原 DSB 解码、因子和复权计算继续由原 WtDataReader 完成。

自有 Reader 每次核当前 status/window、实际 SHA、来源/因子修订、基准和当前闭合截止；只复用已固定的同代原件和委托。已核原字节复制到 Reader 新建独占投影，防止源目录未声明的 +/- 复权缓存进入原生输入。旧切片保留原输出副本。当前/待清理代际均由同一 Reader 持有，切换或停止时的文件占用保留精确删除责任；解除占用后沿原接口重试。停止成功前再次核同一截止，清理晚回返回未完成。

## 固定输入与同 CTA 验证

消费 AWP `build/root-analysis-bound-main-001/wri002/owner` 实际三轮原件，基准为 2026-10-28、29、29；前两轮增加共同闭合日，第三轮原价修订。三轮实际因子文件字节相同，因子修订字符串变化单独保留，前三轮不授实际因子变值资格。

`factor-model-001` 是明确的源事件输入模型：在原快照副本将 510300 最后一个已包含事件的第7列乘以1.01，原价保持，经原 AWP materialize、Import、prepare、原 Reader 和 QNA 生成第四份完整输入。原源接收时点保持，来源明确标为 synthetic，无实际 SDK 调用。模型原件关系和变更位置写入 `PROVENANCE.json`，原目录摘要保持；全部复权结果由原 WT 计算。

最终 `native-008` 固定708份原生源、27份当前源码及13份库输入；只新编自有 Reader/支持、原 WtDataReader 和探针，原 CTA 库沿已批准固定制品。第三方 Boost/RapidJSON/spdlog 头仍从共享固定依赖目录读取，安装工具链与系统头未逐文件冻结，完整工具链闭包留给最终普通构建核准。`cta-005/RESULT.json`、`RUN.json` 证明：

- 同一原 WtCtaEngine/WtDtMgr/IDataReader 处理4轮、8标的；原价、前复权及因子结果逐字段等于每轮直接原 Reader。
- 第四轮因子文件、getAdjFactor 和前复权值实际改变，原价尾部保持；32份旧切片在切换及 Reader 释放后保持原值。
- 缓存命中时删除窗口、同 SHA 错修订和本次未闭合基准均拒绝，恢复原发布后可继续。
- 实际持有投影 DSB 的非共享删除句柄，使旧代清理及 stop 首次返回未完成；释放占用后重试完成，责任清单保持，最终 cache_root 消失。
- 原件0漂移，探针 PID72644、OS0，Job 树归零、管道 EOF、reader join 与资源关闭均成立。该探针没有策略下单能力。

`default-regression-003` 使用最终 Reader 运行已有默认 HTTP/日线 loader/切片保持例，通过并回收。旧20261029 DMB例在本次原封旧 DLL 和新 DLL均返回 short window，保留两端失败，不授当前日期的原生分钟场景资格；原分钟代码未改，当前正式策略主链使用既有 HTTP 分钟来源。

## 唯一策略和执行主链

`main-002` 在已安装无观衡依赖的 WT/WRI、原 Factory/ticker/CTA、唯一1.1.2、原 NSQ、股票执行器和真实 WinSHM SDK替身中依次消费原三轮窗口，4笔原 SDK替身买入、实际开仓周期及后继收敛成立，35.622秒关闭。Reader 为 native006，生产源后继只补清理责任/停止截止，最终身份以 native008 后继运行核准。

`main-003` 增加第四份因子模型后，原核产生新的卖出；旧仅买入的替身断言在 SDK入口失败，保留 unknown/recovery_drain 和无成功 clean，未进入第二代。`main-004` 补明确的次会话可卖模型、买卖替身和完整收敛后，首代6笔SDK替身、四窗口和正常关闭成立，第二代读取失败。`main-005` 消费根正式构建的公共 Native Trader，仍发生读取失败。`main-006` 在独占 QA 对原 Host 工厂显式选择既有认证续接合同，也在首代 recovery_drain 失败；三个原件均保留。

同次原因摘要与公开字符串的精确匹配均为 `qmt_http_remote_failure`，代理记录均有 HTTP503、账户查询恰64次。QA 的 Host配置固定 max_records=64，持续 P/A 刷新和委托后查询用尽记录容量；此前关于认证续接的判断属于待核假设，当前用此直接容量证据更正。后继只在 QA 把 Host 容量和字节额度改为有界256条及256倍原unit_bytes，原总截止及产品预算保持。原 Native host/runtime/批准股票工厂与根公共制品一致，Native Trader 消费已集成的认证续接实现，Host 工厂显式选择正式配对使用的 `qmt.trade-auth-continuity.v1`；生产 Host/Common 没有新增修改。

`main-007` 随后在账户租约准入返回 native_error183，查询/SDK均0；事后查询未发现其他存续owner，保留原准入失败。`main-008` 的 QA 账户字符串替换误改了输入文件名，FileNotFound且SDK0。`main-009` 改用精确 AST 字符串常量替换，为隔离模型选专用 `R29SYNTHETIC` 账户；同一案例两代保持同账户、Source、Journal、原金融根与配置。前序失败的目录和责任原件全部保留。

最终 MAIN-RUN-009（外部历史/待归仓路径：`../../build/ms-daily-publication-001/MAIN-RUN-009.json`） 和 BUSINESS-WITNESS-001（外部历史/待归仓路径：`../../build/ms-daily-publication-001/BUSINESS-WITNESS-001.json`） 证明：

- 最终 native008 Reader 实际装入原 WRI/Factory/ticker/CTA、唯一 `resonance-regime-v1@1.1.2`、原 NSQ、股票执行器和 WinSHM SDK替身主链。首代同 CTA 消费四轮，四个原核输入 SHA 均不同；实际因子修订后产生原核卖出。
- 原源线程完成6笔 SDK替身调用：4买、2卖，最终 converged。正常停止后同根第二代恢复序号8并推进到9，再次 converged，SDK总数仍6。
- 全程106次查询（P45/O31/D2/A28）；HTTP200共1357、202共297、503为0。两份 Native closed.v2 均 ok/recovery_ready/exit0，两份 WRI 均 stopped；Source、Host、Agent、server、proxy关闭字段成立。
- 外层PID75064，74.8039053秒，OS0；Job树归零、EOF、reader join、资源关闭均成立，Reader独占缓存移除，70份绑定来源0漂移，27份当前编译源码0漂移。

本次正常恢复使用既有保存/恢复路径。最终 Reader 已安装身份和根正式公共 Trader 已安装身份均在见证中逐文件核对；这是明确 QA 安装副本的组合证据，最终普通整包重编、安装及搬迁另验。

业务运行的行情日期为明确的下一工作日模型，源成交时间取实际测试时钟。第四窗口前的可卖刷新明确标为 SDK替身次会话模型；其作用是验证更新输入到原决策/执行和状态恢复的接线，不授真实跨日、真实 T+1 或实际市场日运行资格。主链顺序消费冻结的 AWP 发布原件，完整九组件的实时 AWP 同进程组发布仍归根组合验收。

## 根后继重编及原分钟兼容验证

2026-10-30，根在 `build/root-continuous-daily-native-001` 从同两份已审自有生产源码重新编译 Reader 和原 CTA 探针；固定原 WtCore 库保持，新 WT 框架修改0。公开构建/运行驱动只调整仓库定位和独占输出根，原算法、调用和断言保持。新 Reader SHA-256 为 `fa7e9f88cf50727fa620cd0cc65d34ddfba07480f6075760e856c518d85f518f`，编译闭包沿上述固定源码/库范围，系统头完整冻结资格继续独立保留。

`cta001/RESULT.json` 与 `RUN.json` 证明原 CTA 四轮、八标的的 raw/front/factor、实际模型因子变化、同日修订、32份保留切片及占用释放重试通过；全部绑定原件0漂移，缓存已移除。外层 `CTA-CONTROL.json` 记录约3.203秒退出0，内外层进程树、EOF、读线程和句柄正常回收。

旧默认分钟测试的日期缺口使用今天已冻结的真实早盘三证券 DMB 样本补验。`minute001/RESULT.json` 经原 `GuanhengNativeLiveRead.exe` 实际装入新 DLL，三证券各15根09:31—09:45 OHLCV/金额逐值等于原 Helper 输出；各14次闭合通知，重复分钟新增0，Reader 删除后保留切片一致。输入摘要保持；外层约0.610秒退出0，资源正常回收。此项读取冻结样本，无 QMT/来源请求，覆盖原配置未选择 publication 的分钟路径。

`COMPONENT-001.json`/`INTERFACE-001.json` 固定独立 `native_published_daily` 组件及11份安装文件：新 Reader/探针、原对照 Reader 与运行库。原市场包 Reader 保留，后继运行配置显式选择新组件。最终系统包、实时 AWP 与同一运行策略的组合仍须实际验收；本项未切换现场。

## 完整模块的剩余范围

普通最终组合/搬迁、实时 AWP 九组件同实例、真实来源和真实跨日、完整400期 RT/BT 比较、未知责任解除及整个模块 B 继续待验。真实委托、撤单和生产切换为0。独立审查、最终文件 SHA、增量制品和接口交接采用本根后继收据，已失败原件保持其当时输入和结论。源码/生命周期审查 `REVIEW-PROTOCOL-001.json` 的 C1 结论绑定 native008/cta005；最终009的 C2证据另按后继审查登记。
