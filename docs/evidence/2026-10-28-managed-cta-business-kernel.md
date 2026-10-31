# 受管CTA唯一运行体与实际配置核接线

类型：验证记录。状态：partial，STQ-P20/NRT-R9隔离主链通过；完整模块B保持in-progress。真实下撤单0，新增金融账本0，新增WT核心修改0。原P19的003冻结制品及证据保持原身份。

## 输入与实际调用链

原件根为`build/ms-business-001`。唯一运行体是安装后的`app/GuanhengCtaRuntime.dll`，薄exe与Python ctypes均调用该运行体；标准`strategies/GuanhengManagedStrategy.dll`工厂装配两个独立原上下文，复用原Session、ticker、组合、Local、Adapter、Standard及真实Host/WinSHM。自有ContextAccess收敛原NRT值复制与全向量setter正文；金融状态继续归原WT。

实际Python为`build/ms-business-runtime-001/app/venv/Scripts/python.exe`，普通独立安装包含configured纯核0.1.0a5、NSQ0.1.0a1及tzdata2026.3。App薄监督适配来自安装wheel 0.1.0a6，见本候选最终身份清单。旧NRT安装回执绑定的基础解释器已变化，因此另用原冻结安装器生成本代完整安装回执；旧回执保持原件。

原Reader与Helper取自`build/ms-business-legacy-002/cmake/bin`，使用原NRT输入生成器及原Helper写9个day DSB；每证券125个显式合成完整交易日日线。分钟源复用原NRT有限HTTP夹具；Parser使用专用SPI替身。信号8只、执行映射589680→589000、读取并集9只。全部价格、辅助事实、资本和费用均明确属于合成输入，原QMT/真实账户未进入本链。

## 已观察业务结果

`business-core-008`记录首次通过主链，后继`business-core-009/RESULT.json`、`business-proof.json`、`callback-proof.json`及`POSTFLIGHT.json`另绑定NSQ实际发行身份。二者运行资格按各自源码及收据保存：

- A/B在各自原schedule复制九证券125根d1，逐字段匹配冻结输入，再调用安装的唯一configured核；各自结果与同输入直接纯核参考完全一致。参考比较覆盖算法目标，原BT实际撮合及绩效比较继续待验。
- 每策略显式合成预算50000元，数量核使用进入该回调时冻结的原价10.01元/份，CSI300目标700份，其余7项明确0；价格11元的反例为600份。完整8项逐一经原void setter并回读，两个策略共16次setter。
- WT原净额目标为1400份。原MinImpact的显式单次2000份容量允许本目标一次提交，Host/源端使用同一显式合成ETF许可身份，SDK替身实际收到一笔`510300.SH`买入1400份、价10.01的原请求。四查询完成，原策略JSON分别记录700；后继同分钟行情未产生重复委托。
- 创建/删除策略各2、借用epoch过期拒绝、十类错误代码配置在真实DLL准入拒绝；拒绝后configured/created/setters/failure均保持0。正常关闭不强杀，整树回收、双EOF/线程join、Host/源端/代理/HTTP Reader资源均已确认，首错及代理首错为空。

本次Basis的native_nav_verified仅用于明确平仓零、资本50000、费用0的合成纯数量样本。报告同时固定`native_basis_qualified=false`、`production_qualified=false`；原RT actual/valid/pending、真实费用及资金变动的通用资格保持待验。

## 根因修正与原触发条件

独立full静态审查发现受管证券配置仅核NUL，63字节主代码可进入原64字节bar key；缺点/空段和单独复权后缀还可越过原CodeHelper的前置假设。修正在自有配置边界统一核2/3非空ASCII段、总长小于原32字节容量，以及第三段单独`+/-`拒绝。原常量以当前CodeHelper为准，原注释中的Q/H没有作为真实后缀依据。

停止文件可能先于在途回调返回，原运行体在join前置success，导致最终回调失败被成功收据掩盖。现完整close确认后再次读取原子health，失败发布`ok=false/error_code=strategy_callback`并返回1。

`stop-callback-002`用在途A回调等待，父请求停止，回调通过同一已安装Parser的connected状态归0确认原close已进入，随后返回失败。原终态失败、策略删除2、setter0、SDK调用0、无强杀、整树/双EOF/join及运输资源关闭均通过。停止先完成部分生产者、回调后失败的原窗口已实际重现。

调试失败原件保留在business-core-001..007：原getter读取历史bars会改写策略本地price map，数量输入按既有NRT规则在历史读取前冻结；原ticker建立时段后需要第二遍完整合成行情；旧代理128页采证容量不足，当前默认128保持、该业务长链显式512且仍有请求/字节/原总截止；初次ETF委托因原单证券夹具许可拒绝，当前Host和源端共同使用显式ETF绑定身份。旧失败未授运行通过资格。

## 兼容性、审查及剩余交付

原NRT共享正文改动已用固定原Reader/ticker/安装核跑`build/ms-business-legacy-002/e2e-targets-004`的两项完整目标场景，旧ABI与unknown语义保持。最终原生exe五组合矩阵、独立审查、全部文件SHA和组件制品随本候选收据登记。

当前Python命令装配仍是专用测试入口，尚未交付配置算法的正式安装子进程入口与App动作/状态投影。完整资金/T+1/费用、BT/RT实际撮合比较、取消终态与跨进程恢复继续按[模块B](../migration/module-b-delivery.md)推进；核心保存接口提案仍待明确授权。真实源日线沿A统一SDK接入，单位/完整性/available_at保持原来源资格，不能由本合成主链授予。
