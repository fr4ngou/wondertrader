# 正式逐日CLI纯值输入的观衡消费适配

类型：模块C安装与消费开发证据。状态：新外层适配已进入普通App a55、WT读取依赖a11及最终SPA002，两根全新离线安装通过；正式归档的产品期限消费、HTTP/SPA及独审继续。此记录不授400期完整主链或生产资格。

## 根因与正确入口

B正式逐日CLI的输入为guanheng.retained-per-date-replay-input.v1，含schema/session/source。原C报告选择把它落到旧nsb-report-v2，配置和绩效直接读取外层policy/request而丢失内层结构。新backtest_reports统一选择及规范化：调用B公开规范化入口，保留完整外层/source和原请求会话摘要，配置与绩效共用session_for_projection读取原内层；归档核输入报告族和完整source绑定，不更改资金/费用、策略、收益或价格算法。

未知逐日外层版本、外层多/缺字段、坏内层schema及来源摘要/窗口均拒绝。内层schema在C边界明确选择原guanheng.retained-replay-input.v1，避免WT纯值解析接受未知schema标签后被规范编码覆盖。默认最终批次及既有报告族保持。变更限C backtest_reports、backtest_archive、backtest_performance、相应测试和规格；B生产文件保持。

## 已执行验证

使用B固定relocated-001普通安装WT a11纯值API与C源码，原已安装a54解释器提供测试依赖；这是明确的源码/依赖组合QA，未冒充新App普通安装。真实输入来自B原CLI runs/db064578941f44dbbe743eb613b0186a/request.json。red002十项实际失败，错误选择nsb报告和缺投影入口已复现；首轮red001缺pytest属于QA依赖失败，保留原日志。green001暴露一项QA误读strategy_version字段及未知内层标签准入缺口；修正测试字段依据和C边界后，green002十项通过。full001包含相关backtest_workspace、既有逐日报告和新增输入测试，142项通过、无skip；25.85秒，原Job/树/EOF/join/资源完整回收。测试客户端有一条依赖弃用提示。

## 正式归档缺项

B relocated-001的400期CLI正常完成且报告可读，实际run目录当前只见request.json、installation.json、result.json、stdout.log、stderr.log及原输出/基础资料；缺completed-archive.json。C原NBW-R6准入继续要求原父owner的完成证明。当前不从B stdout或result补造归档，也不把未归档目录纳入页面。配置/绩效读取的源码适配与正式归档完成分别验收。

## a55普通与离线安装后继

`build/per-date-cli-observer-001/PREPARED-001.json`固定193项源码、30个分发，WT a11的35个模块与B原relocated-001安装逐字一致。普通安装收据SHA为`b63d845ad8f7f2c98a6c800e654be90998dea41c76871a0ef28768fc329c4b71`；只合入明确C改动，依赖锁在独立stage离线生成后按原摘要比较再写回。安装范围530项通过、无skip，产品包从自身prefix装载；首次importlib测试目录缺失的收集失败保留，后继仅补测试依赖搜索目录。

最终前端202项输入，62项测试、类型检查、生产构建及分块检查通过；静态目录为`build/per-date-cli-observer-001/spa-002`，18文件清单`SPA-002.json`。首轮前端测试仍预期内部来源ID而失败，后继按中文来源要求修正断言并明确内部ID不可见。fork worker启动超时和QA输出目录准备失败保留。

`package-001/observer-a55-windows-x64.zip` SHA为`6d734db43d2f31758a90806688345f04e8bd3dc6bed3bc495faafca2b99f37cf`，清单SHA为`0eabc71f40d1ace1ca576a1445ed3e3bea4d7172eaef6aca8ca0cae48f7d895f`。原安装器完成两根全新require-hashes离线安装，三根142模块、18静态文件相同。两离线自身Python分别完整读回统一57项/54642行，逐值摘要一致、来源网络请求0，并实际规范化B原三字段请求；正常Job/树/EOF/join/资源关闭。旧a54随后读取同一数据也一致，仅授数据兼容回退；旧版不支持新外层并保留旧停止标签问题，完整功能回退资格另验。

## 原完成证明的后继

B已在`build/ms-backtest-completion-001`实现由最终HostResult父责任层发布原NBW证明，原400期主链及证明见[生产者证据](2026-10-30-wt-backtest-completion.md)。早前缺证明的relocated-001原目录保持。生产者已记录当前C源码三次5秒绩效读取超时、一次扩大诊断D的分阶段耗时；诊断成功证明该原件格式兼容，产品5秒完整消费仍待验。C继续原归档→配置/记录/绩效/比较→HTTP/最终SPA，完成证明只由WT父owner发布。

独立审查按a54固定源码到a55的精确文件映射及23源组合进行。用户18126、原后台和a54制品保持；完整400期RT/BT、隔离取消、统一系统和整个C继续。

## a55构建及实际样本身份补件

独立Standards full001发现一项P3：原202前端输入漏记Vite实际读取的index.html、generated-storage.ts和品牌配置，构建身份不完整；原CLI测试样本也未纳入本轮前后输入摘要，单列证据gap。原报告和202映射保持。新增完整206输入（含实际分块检查脚本），生产mode、两个公开VITE选择均unset、无本地.env，记录Node及安装依赖锁摘要；类型/构建/分块实际通过，重新生成的18静态与已安装/打包SPA002逐字相同。软件及ZIP无需重建。

同普通a55自身包重验十项输入边界，原B request/result/installation三摘要逐项等于其INTERFACE-HANDOFF，测试及原件前后相同。REVIEW-INPUTS-002为226件冻结补件，SHA65914cd1b2c4567b57f63ca7d272e40acbbd96773720a0a35a3bd3365126b096；原full001的16406件及固定制品保持，后继独立补审判断该P3和gap关闭。C共享源码的正式400性能后继单独沿[主链证据](2026-10-30-completed-cli-observer.md)，不得混入a55源身份或既有包。

## a55固定交付

两轴full001及226件delta002已完成。Spec最终报告SHA19cb0e95bdd3be9e1cfdf1854b73640892afab9cef92f9f44189ada05f4be68f，Standards最终报告SHA521a5c8d347bf166259afd82c592ffac2d2a34c64b40cbb5b4717b866ae47224；共同P3构建输入和当前样本字节gap均关闭，原full报告及历史失败保持。finalize001再次核16406+226件、193源stage、206前端、18静态、ZIP及当前57根一致，原Job3秒内正常关闭。

固定收据`build/per-date-cli-observer-001/DELIVERY-001.json` SHA205b4bbd74dab1e09be697cbdd806ac3eeb890a24590b1c9350b672564ce1222，`INTEGRATION-HANDOFF-001.json` SHAa327cb033a0f3e65bf9f5650d79b1e4d9e6cd905dfce6504da646bc233b2e69a；软件及数据CURRENT共同绑定该收据。A按固定stage和制品选择，当前共享a56性能源码另有安装/验收。此交付授a55读取/统一57限定开发资格，原400产品5秒失败、完整M1/C及生产保持原范围。
