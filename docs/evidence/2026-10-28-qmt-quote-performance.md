# 全市场共享内存与DataKit分阶段性能

类型：开发验证证据。日期：2026-10-28。状态：终端外源端完整规模运输和冷/热成本定位通过；完整规模原生进程最终退出失败，真实QMT日间采集继续pending-verification。

## 输入和隔离

使用实际沪深股票/ETF清单6982证券、当前同一内存运行时代码，配套CPython3.6.8独立pythonw进程和SDK替身。两次初始回调合计51156输入行，另2条增量；同一8字段、HMAC及真实Windows命名共享内存。每次独立私有配对；终端正文、QMT界面、账户及原数据保持。辅助文件协调只属于终端外夹具；QMT运行时合同仍无文件/网络访问。

Source内存runtime SHA 84b407e24a566a67fdaa312fd7df2670b09163e08486f19b57c1c4ba4c5efccf，symbols SHA c1d171b68c07a57d5eb349d411ada0ec155128db277b4980ecaa25815642b5aa。合成epoch1792548060000对应上海2026-10-21 10:01；量额倍率为明确合成值1，不授真实来源单位资格。上游固定08b230dd05facf6d650d949bfe51054115a2ecb1，原Writer源码SHA075d07b16938a742f1d1baeb09c0a175b8bd333edb3b05ab1a65a63dac06c35a。沿原编译参数/静态库构建单独的自有Session计时DLL，原Writer DLL SHA282be3428a36f04e4caf91668b3a88c178f692f25a885a7d4748f5a55e9423d3。工作区冻结Writer差异未参与验证。

## 差异对照与定位

| 组合 | 完成结果 | 耗时和边界 |
| --- | --- | --- |
| 无DataKit的完整内存正文/SHM | 6982快照+2增量、完整心跳、源/接收端关闭，exit0 | delivery1.094秒，正文load0.109秒/init0.094秒 |
| 原DataKit同步Writer，25秒采集窗口 | 原生2800、源发3000，无心跳/增量，exit2 | 原窗口未完成；这是失败容量观察 |
| 分阶段计时，同样25秒窗口 | 原生2600/13批，源发2800，未完成 | 映射0.0134391秒，adapter/Writer调用25.2677356秒；关闭返回 |
| 200证券首次/重复/另200首次 | 每阶段200实际processed，exit0 | Writer分别1.7801609/0.0001053/1.7684746秒；映射各约0.001秒 |

主要耗时位于首次adapter/Writer调用；同证券后继更新明显更快，结合原getKlineBlock首次创建及映射文件的源码，支持先区分启动与稳态成本。测量没有细分WT内部每个系统调用，不能把调用总时长全部归为某个文件API或安全软件。QMT内置并行SDK、替换分钟算法及调大业务请求超时均没有获得依据；本轮未实施这些修改。

计时仅存在build/qmt-quote-phase-timing-001/Session.cpp诊断副本，以steady_clock累计映射和adapter调用耗时；DLL SHA7ee74fb10c58dca9e47d4d318f50ebeb68436c33911e97759e3c45ae28903d72，诊断源码SHA2fa73e5be3294dffddd016b952ba75bee9355d2323522c414ed12b6a4e2b0a35。未扩展产品公开计数合同。

## 完整首次落盘与原生异常

独立qmt-quote-cold-capacity-main-001按冷200测得容量设置新的135秒总预算、100秒采集观察；原25秒两次失败证据与截止保持。该测量用于求实际初始化成本，未作为修复。源端65.469秒完成6984条发送、1订阅/1退订、资源关闭；capture.confirmed由接收观察器在6982唯一快照+2增量及完整心跳条件满足时写出。

外部原生消费者随后退出0xC0000005（3221225477），未写出最终RESULT。控制器约70.297秒观察子进程终态、未强杀，整树归零/EOF/join/资源关闭确认。因此源端关闭与数据交付的证据成立，原生close/最终完整落盘资格仍未通过；capture标记不能替代退出及文件回读。异常是否发生在close内部、后台原生线程还是之后的销毁，尚缺同次原生栈证据。

最小对照使用原未修改DLL：无行情创建/关闭后观察12秒通过；200证券push/关闭后观察12秒也通过。它们分别正常exit0，不能将完整规模异常泛化为所有实例不可退出。原Writer检查线程与释放路径在此前CORE-005已有冻结分析，本次尚未证明该项就是直接根因，未启用旧冻结修正。下一步补完整规模异常的阶段/栈，再决定责任层；新增上游行为改动仍须批准。

## 材料和限制

结果分别位于build/qmt-quote-memory-performance-001、002、003，build/qmt-datakit-cold-warm-001，build/qmt-quote-cold-capacity-001，build/qmt-datakit-empty-stop-001及build/qmt-datakit-mapped-stop-001。对应控制器actual_exit/整树等原始证明位于build/guanheng-workspace各同名main目录。私有runtime/source正文继续受控，不写入本文。

本轮未操作QMT界面、未更改WT框架或运行产品源码、未真实下撤单、未切生产。此前真实QMT仅3000条及停止中现象与本次终端外测量分开登记；新的合成证据不能代替实机源端恢复、盘中分钟、自动收盘及全天吞吐。


## 后继：完整规模关闭后原生根因已定位

qmt-datakit-native-fault-main-001使用同一原版Writer DLL，在原容量作业已经终结的专用合成store上重开，输入6982条递增量额行情；不启动Source、QMT、SHM或SDK。每200条记录阶段，全部6982 delivered/processed在45.422秒确认；close_enter45.422、close_return45.500。随后继续在原135秒总预算内观察，约50.281秒发生0xC0000005。控制器实际exit2/子进程3221225477，未强杀，整树/EOF/join/资源关闭确认。

仅在隔离进程加载自有异常记录DLL；其Windows异常过滤器记录故障线程33712、地址及x64原生栈。首地址属于原WtDataStorage.dll：RVA0x38243；下一帧RVA0x2daff，随后是ucrtbase线程入口。公开材料位于build/qmt-datakit-native-fault-001/events.jsonl、COUNTS.json、native-fault.txt及相应原控制器。

从同一已验Release对象/库仅重链接到新的map-bin，原DLL和源码保持原SHA。整个诊断DLL的text SHA不同，因此未据此直接复用整个地址表。另核具体函数区间：原DLL与诊断DLL的check_loop RVA0x37be0起2384字节完全相同，SHA fa5242f794545303e7f13c1f63caa81aa079bebe5477ed5a9abaa2d16cf83d6c；线程调用入口RVA0x2daf0起48字节也相同，SHA e515c3b0f7e29b42e0fa1bf39276f0d8139af6c13d8e613f3646def02481813e。异常位于check_loop+0x663，其调用帧为该线程入口+0xf；MAP-RECEIPT.json和FUNCTION-IDENTITY.json保留逐函数地址身份。

固定原源码对应关系：init无条件启动_proc_chk；release置_terminated并只join _proc_thrd，随后释放映射；DataManager::release再调用工厂释放Writer。check_loop在循环开头判断_terminated后睡10秒，醒来没有先复核停止状态，就继续读Writer成员。实际事件已经确认Writer关闭返回后check_loop仍执行。这证实当前组合的关闭生命周期缺口：后台检查线程未结束，对象已释放，之后继续访问。此前0/200通过仅支持小样本观察，不能反证此完整规模反例。

本次结论仅针对同次固定原版Writer及此关闭路径，不代表所有WT组件或正常全天运行均有同一故障；并发过期、其他异步线程等CORE-005冻结项没有因此整体获得实施资格。下一步先核原收盘/状态机可复用的完整停止路径，再形成最小必要修改范围；当前未修改框架、未启用CORE-005候选，也不以强杀/延时退出代替线程关闭。真实QMT源端停止仍单独处理。
