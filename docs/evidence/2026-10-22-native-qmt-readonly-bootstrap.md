# 原生 QMT 只读交易初始化的开发验证

类型：开发证据。状态：限定范围独立审查通过；真实HTTP与生产未验。规格：[NQB](../specs/native-qmt-readonly-bootstrap.md)。

## 行为与所有者

自有动态插件经固定上游 `08b230dd` 的正常 `TraderAdapter::init` 接口加载，保留配置所有权；显式 `savedata=false`。同一owner线程启动并pump，worker只生产有界结果，在解锁后由owner回调原SPI。账户、持仓、委托和成交初始化复用原Adapter；历史成交只作为查询结果，避免重复推动持仓。写接口拒绝，无执行器。

当前来源是显式fixture；真实QMT HTTP尚未实现。初始化与退出仅授予每独立进程一次的资格，实际重连、常驻资源与生产接线仍待验。原框架文件保持冻结，本切片未修改WT core。

## 原发现及根因修复

首次独立full发现三个问题，结论与原冻结包保留：外部/非法委托标签可能被原Adapter识别为本策略；JSON递归解析发生在深度检查之前；同一事实的键序差异被当成内容冲突。

修订在自有来源边界完成：fixture归属证明绑定精确adapter、券商委托号及规范本地号，缺证明的外部事实以空管理标签保留；整批本地号冲突在任何该批SPI前拒绝。迭代SAX先限制深度、节点、成员、重复键和UTF-8，再进行迭代DOM；重复判定比较已校验的规范业务字段与数值。fixture证明只服务测试来源，真实HTTP布尔字段不构成生产委托归属证明。

## 实际核验

维护者复验：60项根因回归、原68项矩阵、8项补充及4项原生形态编码检查通过。补充8项含3个新进程与5个结果断言；编码检查只证明固定源编码器字段遗漏，当前QMT源端修正另在独立工作树准备审查。

主任务重新核对1351冻结文件、17个当前输入、原生构建输入/库及DLL/host摘要；原850项冻结文件保留。独立delta重查NQB-R1–R9，新增22个隔离子进程全部通过，三个原finding关闭，新finding 0；18个成功初始化进程实际join后worker_live=0、queue=0，4个初始化拒绝进程正常退出。40万层数组与10万层对象正常拒绝；外部标签不进入活动委托，合法双本地号统计及真实冲突拒绝通过。

最终清单：`build/native/capability-audit/native-qmt-readonly-bootstrap/repair-001-4af864e3-0f51-430a-8a60-83a090a3f787/frozen/freeze-manifest.json`，SHA256 `ac6fa438fea65de2218437df80ffba2ba752fae7608fd9de5e92ce07fda567cb`。

审查包：`build/native/nqb-review/repair-001/review-pack.md`，SHA256 `d484bc2f9932cabd935d8c18df30c85ce296e23274960cadd53692f67a248fd1`。独立报告：`repair-001/independent-delta/review.json`，SHA256 `0e64fc86c309871ab73511b63adfca170a4aad440f585ce2af7c518b5a62df83`。

## 未覆盖与后继

继续真实HTTP提交/认领、来源字段语义与精确原命令身份恢复，保持签名、账户边界及原事实所有者；随后才评估真实交易通道。当前未访问真实QMT、订阅、下载、账户委托、数据库或Docker，未发布。私有原生统计只由固定源码核查，未增加私有字段探针；线程退出证据不授予长驻恢复、热卸载或逐对象堆无泄漏资格。
