# 修正 JSON 精度制品的真实账户读取

类型：实际运行及未完成项证据。日期：2026-10-30。四组完整实机资格：未通过。

## 已成立的修正与实际主链

原生消费者字段差异根因为自有三个JSON边界默认解析未使用FullPrecision。原冻结RapidJSON的红绿验证及新制品离线主链沿 `build/wt-native-account-precision-001` 登记；WT框架保持。根在新的 `build/wt-native-account-fixed-real-001/native` 普通逐字复制固定制品：

- `GuanhengAccountScan.exe` SHA `5dae69603377ef7d88dde3e2d82dbc4e111c5b3002b10a456c07c528a700ad44`。
- `traders/TraderQMTReadOnly.dll` SHA `27e92a99437771432e5d0af97731dc80b94b445a5a47e1fc70bf9a696a095c42`。

本轮沿最终离线候选003的普通WT入口、原只读Host和真实QMT，保持v3/profile policy1.0及原账户绑定，仅替换原生制品及生成新的配对和私有Journal。实际WT71928、Host29660、原生Scan46744；WT启动包装63800、外层控制器48768。原生未使用诊断替身。

持仓4条、空委托、空成交三个批次正常delivered。停止后的只读逐项核对取得56项事实、12个数量/可卖/均价ABI槽精确一致，原请求/结果SHA、来源绑定和执行区间保持；原来浮点末位差异在这些真实已交付值中消失。原件为 `PARTIAL-AUDIT-001.json`，原观察从普通Scan的实际IPC帧恢复至 `real/private/PARTIAL-OBSERVATION.json`，没有追加业务查询。

## 未完成的资金批与收尾

第4个资金请求在原Journal中为terminal、ok=false、`error_code=operation_interrupted`。原生完成帧error_code=source、elapsed_ms=19899，退出码3；该批delivered=false，不以空资金或零余额代替。具体来源中断触发原因仍为unknown；本记录没有将其归因于精度修改，也没有声明故障已修复。完整严格审计脚本要求四组成功，本轮未满足且没有成功AUDIT.json。

根停止原 `SHM_READ_PROBE`，Formula记录05:02:03 doRun及05:02:50 stop success，随后逐字恢复原35d020…正文。普通Host、WT及内外Job正常回收，forced=false、tree_zero、双EOF、reader join及句柄关闭均成立。160份本轮输入SHA前后一致。来源读取失败使外层退出码2，正常关闭分别保留其事实。原4请求及其结果不重复提交，Journal仅以只读方式核验，SHA保持 `fe73e19a909ad475493562d1d1ac7c3e345111838a1a53d0fdd9788990387411`。

现有数据WT33636及行情/HPR保持，未真实下单、撤单、切换生产或修改WT框架。下一步只读核原资金请求、来源代际及原生失败映射，再决定必要的定向处理；精度修正源码/离线资格与本次真实来源完整资格分别交付。

参照：[原生真实主链与精度缺口](2026-10-30-wt-native-account-consumer.md)、[原制品两代认证](2026-10-30-wt-native-account-reconnect.md)、[账户读取规格](../specs/qmt-shm-account-read.md)。

## 后继只读分层核对

`build/wt-native-account-fixed-interruption-001/ASSESSMENT-001.json` 保留18份输入前后摘要。三批56项事实和16个实际浮点值的位模式精确一致；资金请求在同一来源绑定派发后4.002747秒被Host标为 `operation_interrupted`，距离根手动停止探针仍有33.062503秒，距离队列截止还有14.160020秒。因此人工停止和该请求队列到期均未触发这次中断。

这个终态是Host通信层中止未保存来源终态的请求所写，当前原件没有首次运输异常、代际转换原因及第4次券商调用是否进入/返回的记录。具体触发仍为unknown，资金成功资格仍缺失。后续必要的实机读取使用既有QA首故障诊断器保留有限异常类型、源码帧及退休边界；保留原请求和Journal，不按推测修改产品、不重发旧请求。

后继[精度新制品真实四查询](2026-10-30-wt-native-account-fixed-diagnostic.md)取得四批完整精确结果并通过独审，补足新制品的单次实机资格。本次失败原件及触发原因unknown保持。
