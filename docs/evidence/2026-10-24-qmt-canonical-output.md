# 唯一金融映射器的可选交付标识

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-24。状态：accepted切片的限定开发验证通过；完整事件功能未完成。范围：[SEV-R3](../specs/native-qmt-standard-events.md#sev-r3-来源元数据与唯一金融-mapper)的accepted可选canonical输出；完整事件provenance、Bootstrap事件begin、交付索引/SPI和query/live仍待实现。

## 最终行为

AccountMapping保留原六参map_account_rows符号、金融视图和source_to_output；新七参入口由调用者显式传AccountCanonicalLimits，仅order/deal可启用。每最终WTS下标输出一个canonical_key和derived_facts_sha256，原重复行仍指同一下标。key包含可信账户/环境/币种/profile、证券/市场/来源日期和原broker；成交继续复用原scoped_trade_id/RefOrder。hash直接取唯一mapper原canonical/seen处的规范金融事实，不包含本地接收UTC，不冒充Host源摘要。

输出有独立记录/字节限额，失败不发布半批；旧调用的canonical输出为空/0，旧view_bytes保持。canonical_bytes只计两个输出字符串的逻辑字节及各一个NUL，不宣称完整事件索引、分配器或进程物理内存额度。

四类WTS对象统一由自有append_owned临时release-owner持有；真实WTSArray.append(false)成功后才转交。扩容失败由临时owner释放新对象，已入数组对象由原batch释放；未修改WT框架。该问题是调用者转交时机缺少异常保护，不能据此泛化为WT框架不可用。

## 验证与独立审查

首轮七组CTest与新增115次样本调用通过，保留原128项币种/账户样本。独立full发现两项P2：create至append间裸对象所有权缺口，以及新增6个非法绑定样本被旧行账户/币种冲突遮蔽。两项已修：统一临时owner；新绑定准入样本移除可选行绑定干扰，旧冲突样本保留。修前原bytes分别保存在qmt-account-canonical-output-001/before与002/before。

根另加真实分配失败探针（外部历史/待归仓路径：`../../tests/integration/qmt_shm_account/mapping/append_probe.cpp`），独立翻译单元包含生产mapper，在真实WTSArray的下一次new注入异常，定义4个场景：裸append失败对照主动清理、空数组失败释放、新对象失败且已入前缀保持、成功单次转交。没有产品故障开关；该探针不代替CNG分配异常或四类完整金融流程的逐分配失败矩阵。最终构建/运行结果见下方后继。

## 保持的边界

本切片提供后续事件消费所需的规范标识，未启用实时SPI或新增第二份金融账本。生产Factory仍旧；实际SDK、真实账户恢复、全量历史、完整独立安装/发布分别验收。

## 后继：最终修正验收

最终八组CTest（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-query-canonical-native-002/ctest-identity.log`）全部通过，60.72秒；原始分组输出（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-query-canonical-native-002/LastTest.log`）确认实际执行128个旧样本、115次新样本调用及4个append所有权场景。真实new异常在空数组和已有前缀两个窗口均命中，成功转交后由数组恰释放一次；裸append对照观察未自动释放后由测试主动清理。CNG分配异常及完整逐分配窗口未由这4例覆盖。

独立delta（外部历史/待归仓路径：`../../build/qmt-account-canonical-review-001/DELTA-001.md`）静态关闭两P2、新增P1/P2=0，执行0/动态unknown；根对9份最终来源回核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-canonical-final-001/REVIEW-ROOT-CHECK.json`）相符。作者/审查/根动态证据分别登记。构建控制器实际77.047秒、exit0/nonforced，整树、EOF、reader及资源关闭；运行源码前后无漂移，真实券商SDK0。标准候选受影响的固定上游组合另行重建验收，不用这八组替代整个插件或正式发行。
