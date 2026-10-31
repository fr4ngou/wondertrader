# 2026-10-27 bulk 控制语法与源端 ACK 确认

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：限定 pass；整体 bulk 运行接线 pending-verification。关联 [BC1/BW1](../specs/qmt-bulk-history.md)，复用 BS/BA/BF/HP。

## 输入身份

- 规格 SHA：952def8332734dde325d28f2be49c337f5994637fd66c81e10224df0910e0622。
- 固定来源：build/qmt-bulk-ack-validation-001/PINS-MODERN-001.json，SHA fe5bd3c68f9c1d7f801b53eb111b4c6c3da408cfb509188a49d41a8239cc3fa6；51份现代源码和测试的字节在加载前固定、加载后核同。
- 目标清单 PINS-TARGET36-001.json：a853cfcf1603fd4944e47b22f1e2bd984115627c537b5477f54bafa597d616a0。实际国信 Python3.6.8 GUI exe：49cfc2336b4386b851d575d97e649a1c2bf6f18f339b172386423820e2026c85。
- 基线清单 PINS-LEGACY-001.json：a36770437abe155ce2a9540e68138f82ecd9c06786b7ed801f1d2f911045733c，包含原控制测试及本仓库既有 .venv 的471份pytest依赖文件；禁用外部插件自动加载、conftest和缓存。
- 根负责执行，两位作者仅静态交付；独立full审查只读最终规格、源码和原始结果。

## 实现与观察

原ControlPeer在匹配ACK和close时都会删除incoming，缓存消失不足以证明业务确认。新增可选observe_reply_ack仅为当前成功缓存创建一个小收据，绑定generation/call_seq/requestSHA/replySHA。receive全包语法及上下文验证完成后，与ACK退休同锁发布acknowledged；close令未确认收据abandoned。收据没有业务回调或payload/peer反向持有。默认未观察路径不分配收据，窗口额度和原reply返回值保持。

公开3.0 grammar新增host发起的open/page/status三操作，复用base1.0封套、窗口和预算；trade2.0独立。既有生成器增加显式--protocol bulk，默认trade生成字节仍匹配485f441b520ab93fa109bfed10c56ec811862d8681a3efb2ade2fef2c3d52d4e。旧read profile继续拒control3；grammar不授SDK权限。

| 执行 | 原始结果SHA | 退出与结论 |
|---|---|---|
| 原peer/messages固定源码pytest | LEGACY-001.json：5e11e50a9cbe293f4a6942952fe78bffb20a7b4272524707fd4fe1ac7d5546de | 65通过；根44692 exit0，1.640秒 |
| 现代Python3.12.14固定源码unittest | MODERN-001.json：aa739328248914b564ebd294e2c9e9e2de599b507d0fbb5cd101428ba762efed | 100通过；根42484 exit0，0.784秒 |
| 国信实际Python3.6.8固定源码unittest | TARGET36-001.json：fce562a379b7cebc1df58f3ebfb6b845ddaaf1ae0683c7beb677ab73a5132aa5 | 95通过；根74124 exit0，0.933秒 |

三个结果均0失败/错误/跳过。生成器5方法仅属于现代构建侧，目标3.6.8没有运行它们。不同解释器的同一方法分别授环境资格，数量不作为互不重复用例相加。

结果均在build/qmt-bulk-ack-validation-001。准确argv、原双D及三个Job控制器收据见ROOT-HANDLES-001.json；现代/目标run.py SHA5239da153d2b6f0ac1d9f62c4e7599583c8e2622695cb32273cac519c164c74e，原pytest runner SHA7991ad154f62e65c40ed9183e3cfd18be5050960a247d8f09bef1795e21432a0。所有Job在resume前纳管，2GiB内存上限、45秒原D/根55秒监护；实际整树0、双EOF、reader join和资源关闭，无强杀或控制台。输入前后匹配，无新存活线程、SDK或旧项目导入。

## 证明范围

覆盖新增15项ACK、8项3.0wire、5项现代生成器；复用原16交付、12交易control、44快照/SDK/v1方法。三页合成BS通过真实内存ControlPeer往返：Host take/ack/prepare/sent各阶段源端仍awaiting_ack，receive后凭收据推进，五行三页仅capture一次；确认事实不延长原快照D。

原65项pytest覆盖双方向预留、退休缺口、重放、未知、截止、整包拒绝及并发释放。非法包不提交该包拟议转移；receive入口原expire仍按既有时钟独立处理。

独立full报告（外部历史/待归仓路径：`../../build/qmt-bulk-ack-independent-001/final001/REPORT.md`）核当前输入与实际结果。初版多行编辑未匹配CRLF，缺收据终态写入，初审已发现；修正为control_peer SHA05dd65ef26f34726d3a6dd6e5cfe52dc2c91adddf6c078a12e319276fcccb478后才执行上述测试。初审与before原字节保留，初版未取得运行成功资格。

### 空快照组合补充

full指出空快照与BC1组合尚缺专例，根仅在ACK测试新增26行方法，生产/规格保持。最终test_bulk_ack_receipt.py SHA15e6021e89d1514a1917bcd292432aa73276bd57b1802d5af38b74d922a9d75b，共16方法；PINS-ACK-002.json SHA7596f1a424015f0d91ab92d3656ed0714a8ede6739ca965df0357bb4d871946e。现代和国信3.6.8各16方法通过，0失败/错误/跳过：ACK-MODERN-002.json SHAed5eefcaffa596fa3e02f67e2718fa1ea6a0f7631268fa492aedab36d8020b7f，ACK-TARGET36-002.json SHA90063de97441d2e4ae41c8904ddd458c64fdc1c261950dcdae919568db77c89f。原15方法重跑，其他来源不变的65/100/95证据按影响复用，不将数量叠加为独立场景。

空页final/0行在Host本地ACK已sent后仍保持源receipt pending及BS awaiting_ack；Source receive后收据确认，随后BS原ack才completed/1page/0rows，capture一次。两根19040/44268分别443.140/489.621ms正常exit0；控制器仍在同原D内确认整树/EOF/join/关闭，无控制台或强杀，准确事实在ROOT-HANDLES-002.json。独立delta（外部历史/待归仓路径：`../../build/qmt-bulk-ack-independent-001/delta002/REPORT.md`）补该内存组合资格；最终Journal与真实SHM边界保持。

## 限制与后继

本轮限定控制语法与内存peer/BS消费；真实SHM bulk、final QMI与原Journal提交的实际Host域调度、真实月窗/全历史仍待验。普通registry和已装正文未开放bulk，不因grammar存在扩大资格。

下一步冻结显式v5能力/配置、共享uptime原D和小artifact terminal，再接原QMT线程capture、I/O分页和唯一HostDomainWorker。中间CSV耐久后ACK，最终QMI与Journal terminal确认后ACK；COMMIT后超D先GET原终态，不interrupt覆盖成功，不续ACK期限。同代数字不证明原collector/snapshot owner恢复。随后接C++ artifact、实测月窗及证券/ETF库存，再扩全历史。

旧项目只读，本轮未执行或导入。WT核心未新增修改，批准TraderAdapter两摘要在POSTFLIGHT-001匹配；已装GH_WT_MEMORY_VERIFY正文4034e03e12be1ee219ce828829ba76eb64a3843e1c3871e7d278ceb3707bd09d保持。本轮未启停策略、未真实下撤单或生产切换。常驻实际两代、完整交易恢复、策略/观衡和独立发行保留总目标，当前无用户待决策或必需操作。
