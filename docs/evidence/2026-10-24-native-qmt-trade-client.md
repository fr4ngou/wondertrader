# 原生QMT交易客户端与原委托关联验证

类型：开发验证。日期：2026-10-24。范围：NQT-R1/R2、QST-R21及受影响的Host关闭链。状态：本切片源码与隔离调用链通过；标准TraderQMT插件、完整安装和真实交易待验。

## 实际实现与根因

- `GuanhengCommon/QmtHostCodec`统一原有codec；账户客户端显式选择v4/control2，默认v3/control1保留。
- `QmtHostTradeClient`提供准备、一次提交、原ID查询、原委托查找、撤单引用和持久事件读取。通信身份自动生成，实际WT委托身份完整保留。
- R21在同一通信Journal事务内保存有限原委托关联，不计算订单、资金或持仓状态。首次迁移只恢复原insert空索引；未知早到事件不会在后续插入、重放或重启时追认。实际派发后的完整token、账户及真实回报建立证明，当前来源校验决定能否撤单。
- 修正原命令核查失败误降为NotSent、提交前背压误升为unknown、合法撤单后置异常bool信号丢失、完整HTTP409引用未解析、未到持久前沿的空页误报成功五项根因。
- Host物理关闭仅退休没有成功交付的观察；已领取页、ACK及域事务继续沿原截止保存。父读链失败时，先确认域worker已退出，再独立收敛交易事实，最终保留原父异常；域仍运行时保留owner。
- 两份测试夹具在Python 3.10缺少`add_note`时保留原异常对象，所有owner继续独立清理。原事务提交故障测试改为准确注入实际写事务，避免前置只读提交提前触发。
- 账户空币种红测在真实C++四查询的第四项资产查询失败，原件明确为`account_resume`。Core原来强制来源币种CNY，与Agent和QAR已有空串语义不一致；现保留精确空串并沿映射表示unknown/null。账号绑定、部署CNY及非法值拒绝保持。

## 最终运行证据

源码、原件及构建目录均位于`build/guanheng-workspace/`，没有使用运行中的券商SDK。

| 验证 | 实际结果与入口 |
|---|---|
| 原生构建 | `qmt-native-trade-build-001/currency-fixed-build-result.json`通过；Common、codec探针、交易探针及独立故障DLL均重编。测试宏只进入专用DLL。 |
| 受影响Python回归 | `qmt-native-trade-regression-002`：513通过、16显式制品用例跳过，18.43秒；这16项另由下列原生CTest实际运行。 |
| 正式CTest | `qmt-native-trade-verified-003`：三组全通过，25.61秒。源码回归明确设置本仓Host、Agent及App导入路径。 |
| 协议codec | `integration.qmt_trade_v4_codec`通过；共用codec、显式控制版本和完整profile准入。 |
| 真实C++闭环 | `integration.qmt_native_trade_client`实际6个测试通过：正常往返、只读、回复丢失、源unknown、空币种往返及异常兼容。正常往返下单/撤单替身各一次、三条回报持久及源确认、账户四查询均在原线程；回复丢失只GET原ID，没有第二次POST。 |
| 原生故障 | `integration.qmt_native_trade_client_faults`实际11个方法、27个场景通过；含原五根因及V3/V4共18个账户币种场景。正例核原data字节，负例必须到完整账户terminal后命中精确数据错误。 |
| 空币种红测 | `qmt-native-account-currency-red-001`保留失败原件；两个异常兼容测试通过，空币种往返按预期失败，资源正常关闭。修正后的同路径通过，未替换来源币种。 |

最终探针SHA-256：`ea006ea2b7d91d98d6a3aaacee6953e25eb7cf0e4d41bf42336219966d552421`；故障DLL：`89c504e35342ec8b464b0d7e43b4ae99aea87c54ae8af9155aca0b50152320c6`。实际完整响应、请求摘要、首次期限、SDK替身次数及关闭事实分别保存在最终`native-cases/`各场景中。

所有启动由隐藏、有界控制器管理，创建时绑定Windows Job。最终进程树为零，管道EOF、读取线程join与资源关闭分别核实；没有依靠强制终止取得通过。unknown场景保留源`source_unknown`及交接未确认，源I/O和worker实际退出，Host本地owner完整关闭；没有把源未确认改写为成功。失败场景目录保留，首异常不被自动删除失败覆盖。

## 独立审查与输入身份

- `qmt-native-trade-host-review-001`：R21首次full及后继delta，迁移因果缺口修正后静态complete。
- `qmt-native-trade-client-review-001`：首次full记录五项P2；`qmt-native-trade-client-review-002`按新输入完成对应delta。
- `qmt-trade-close-native-review-001`：独立首次审查发现父读收尾与Python 3.10异常保护两项P2；最终`DELTA-001`核闭合两项，并覆盖Core空币种、V3/V4终态及测试接线影响，静态complete，无剩余P1/P2。

审查者静态结论与根执行的动态结论分别保留。R1上下文作者关联已在相应报告声明；最终关闭及空币种复核由未编写该实现的独立审查者完成。`qmt-native-trade-final-001/REVIEW-ROOT-CHECK.json`按后继范围核对84项记录、55个去重输入，最终漂移为零。首次失败与后继报告均保留，没有回写原报告。

## 剩余交付范围

当前客户端仍是标准插件的依赖，现有自有`ManagedTrader`额外签名、资格等级及四查询原子前提尚待退出目标链。标准ITraderApi/TraderAdapter/SPI的实际下撤单、回报消费与恢复、交易独立安装包、真实终端验证和正式发行继续开发。真实委托仍按明确授权执行；本轮真实券商SDK调用为零。

历史分钟覆盖、单位、实时CTA及保留观衡业务的完整用户入口仍需各自证据；没有将本切片通过视为整体迁入完成。本轮未新增WonderTrader框架修改，旧QMT工程保持静态只读参考。
