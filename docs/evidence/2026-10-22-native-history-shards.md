# 原生历史准备分片的当前行为验证

类型：开发证据。状态：源码及当前根因行为独立审查通过，历史首次红灯身份未知。规格：[NHP](../specs/native-history-preparation-shards.md)。资格限定合成来源、同SourceSession、进程内有限任务及历史-only受管根。

## 根因与实现

原准备队列把最早与最晚缺口交给一次fetch，跨72小时会持续背压。仅缩小count可能截断尾页；partial期间重算范围又改变了正在采集的页身份。自有队列按来源实际行数/自然分钟跨度和队列预算规划固定窗口，每次work至多一次fetch和一次发布；partial保留窗口与暂存，发布背压先重试原暂存，已结束的空片也推进扫描。源页结束与原请求完整覆盖分别判断。

exact-limit仅在实际唯一有序时间集合覆盖闭区间每个自然分钟、且to不晚于同会话源时钟时允许结束。原rows<count条件保留；未来to、稀疏缺点、来源变化及无权威网格继续受原限制。发布复用原Store→Helper→DSB/sidecar及IRdm/Factory代际刷新；WT core、SDK wire和旧history.read单窗准入保持。

## 当前验证

维护者最终38项市场测试、8项分片原生检查、61项服务用例通过且无跳过。主任务核对43个输入、9个二进制、959个可用跟踪源码摘要及真实日志、原生结果。独立full复验38市场、8分片原生、20查询原生、6公共任务/兼容/容量用例，全部通过；337冻结源及补充259项QMT认证/DTO、29项SDK导入闭包分别绑定。系统Python缺tzdata的最初公共setup为0用例，按环境失败保留；实际公共验证使用原项目venv。

新增对照和独立delta均验证四组观察：旧实际Bridge长窗连续两步Backpressure、0源POST、无DSB；当前候选两步4321→4322根、Gaps→Complete。相同3分钟/count=3，旧库complete=false，当前库true。独立harness分别记录观察成功与功能断言，避免把预期的旧行为误记为测试程序崩溃。674个绑定路径事前事后无漂移，阻断finding 0。

## 证据身份及历史限制

最终输入：`build/native/history-shards/run-20261022-a1/candidate-inputs-v2.json`，SHA256 `3f0c4541bf4bd2e02ee90591193894bbc95bb93cc48635a0d3e50713e25914bc`；当前Bridge `88a857d89b03ba6828d7b8befef442292d2f1623d5f7ce47a0ebf48221956406`。正式full包 `build/native/history-shards/review/review-pack.md`，SHA256 `c59cc9d3f1b9537f32accbe9aa1ade2c38cfd6f869d0debca9035f5c8ae01e95`。

新对照包 `review/comparison-review-pack.md`，SHA256 `e9592aa4665466a1b5f0a231e6d029ae595ca988de52b4842303fd83618283d7`。独立delta报告 `review/independent-delta/review.json`，SHA256 `b9e0c737fb0c26e12e48b821441ab2ad987d592cfa5d2424c79776f9319af507`。R1–R6 complete，R7当前根因行为complete，R7历史首次红灯身份/先后仍unknown。

原最初两失败日志缺当时源码及二进制绑定，继续保持原样。此次新对照的旧Bridge/Helper匹配旧NQW历史清单；exact旧静态库只有本次事前摘要。两旧头文件匹配原摘要，旧cpp一次恢复未匹配后停止，没有声称恢复了原源码。这些新结果只证明当前可复现对照，不回填最初红灯身份。

## 未覆盖与后继

跨超时/重启的源请求身份恢复、跨会话数据采集谱系、真实覆盖/精确量额、十年全市场容量与实时CTA仍须独立完成。expected网格上限10000保持，十年需外层有限请求或专门批量导入路径。每次Store合并和原生首次载入仍访问累计数据；尚无全市场持续吞吐/内存压力验收。原生关闭实测约5秒属于观察，不能授予最大退出时限。未访问真实QMT、主动下载/订阅、账户委托、数据库或Docker，生产未发布。
