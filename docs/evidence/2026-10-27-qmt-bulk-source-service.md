# 2026-10-27 bulk 显式能力与源端运行服务

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：源端合成验证与独立full/RED/delta通过；真实bulk SHM、Host最终提交及全量导入仍为pending-verification。关联[BP/BQ/BG/BS6](../specs/qmt-bulk-history.md)，后继[控制确认](2026-10-27-qmt-bulk-control-ack.md)。

## 输入与实现

最终规格SHA：862e0095c875ce7167d3098a780274c2c635e14724136ec21636f6e377d49b38。新增能力精确为market.history_1m.bulk，显式qmt.read-profile.v5/control3.0；普通v1–v4准入和默认构造保持。operation_profiles只描述原普通操作，bulk_profile独立承担长窗、原queue/total及页/总量额度；联合预算核完整REPLY与base64开销。

SourceBulkHistoryService绑定实际认证generation、UUID范围和一次原D，单活跃快照及有限终态记录；原QMT线程构造BA并一次采集，后续页在原I/O线程处理纯值。共享uptime与控制monotonic先后采样，仅首次保守映射且向下取毫秒；错误钟锁存固定码，BS锁内时钟回调不递归关闭。构造、SDK、分页、编码、发布与终态查询的服务级工作计数共同决定drained。

BulkAgentControlLoop复用原peer，完整receive提交后先消费真实ACK收据，再派发新CALL。未确认页背压，空终页也等待原ACK。open订阅持原CALL控制D；到期仅移除该订阅，不cancel共享future/SDK，不向已退休序号补回复。总数受原max_pending_calls约束。RestrictedBulkReadAgent复用原运输/线程；ReconnectingBulkReadAgent复用原常驻状态机，前代I/O真实关闭且bulk drained后才能新代。

| 最终Agent模块 | SHA256 |
|---|---|
| bulk_capabilities.py | eaed94883415e2e9e4a6f8917a1102aca8a5549031417dc7a9e71cf482450344 |
| bulk_configuration.py | 855917e067e384845bfdec7eb961c1614769cdc302cca6b03879301913581776 |
| read_capabilities.py | 27e3ad151ba71e54a04773f05a5a1678a80385ef7e6fe22574461d0373487163 |
| bulk_snapshot.py | 746ee57c790851157fedf86c6a55753213dae7d37bd929db0c5c54adcb8765e3 |
| bulk_service.py | 1f81a5cb349c25ec8df1c08746d8436e7f7bb90efeb4d29a0d0eb1d8ba656c92 |
| control_bulk_agent.py | 6bedbf1d5c74dcc3f8983ab3bedd9e15b65a3618e334ebabd20cecc704fb85c8 |
| bulk_agent.py | a950b219ca5203c59b68514ba4c1ccda3932e69b9bf0e9bc8bae4551c7b4f215 |
| reconnecting_read.py | 488cdfe84ab31d20eff087c06e48f5a536ba4a3d62136df643996459b995d6b0 |
| reconnecting_bulk.py | b89ca4736de6e594c4bbfcca33935e1e384cadb2b52ce46ecac79e0da59874eb |

BS6仅新增锁内小metadata读取，保持原page/status字节与字段；不解析完整页。read_capabilities只加唯一v5常量和显式委派。普通重连只提取默认原validator/factory两个hook，其锁、定时和退休逻辑保持；独审反向还原与旧字节一致。所有改动在自有适配层，无新增WT核心改动。

## 实际执行

原始材料在build/qmt-bulk-source-validation-001。固定runner run.py SHA5239da153d2b6f0ac1d9f62c4e7599583c8e2622695cb32273cac519c164c74e，以-I -S -B从核SHA的内存源码加载，禁止未固定来源及SDK依赖。子进程继承根原双D；Job在resume前纳管，2GiB、45秒原控制D及55秒根监护。

| 输入/执行 | 实际结果 | 结果SHA |
|---|---|---|
| PINS-PURE-001：d029d7d9a170108cba53bab971e418973b8bedef0daa5fd9e133845abbf89b68，现代3.12.14 | 配置/BS6/原快照及普通读取重连125方法通过；root73988 exit0 | PURE-MODERN-001.json：7b1873541e83972e9ac767be0a49fbc4d61407f3dbbfb0337f039a41d589d86b |
| 同PURE输入，国信实际3.6.8 | 同125方法通过；root71116 exit0 | PURE-TARGET36-001.json：83ae48800e0604add06d27f5c3b1225a0b9d1a7b947466a9adb97aac9d29f5a2 |
| PINS-SOURCE-001：6289aa383ca4fb743bd9cec5930c52ea3a3c753b4b202282b88547a1f6837a5e | 001源端/控制/新重连各环境40通过；后被独审发现未覆盖窗口，001不授最终资格 | SOURCE-MODERN-001.json、SOURCE-TARGET36-001.json原件保留 |
| PINS-SOURCE-RED-002：f0ade1ffa01f15d511316788c45c91addc8aacd72006177d58159742384209bc，原001产品加新回归 | 35方法，30通过/5断言失败，0error；root58276正常exit2、child1，预期反例 | SOURCE-RED-002.json：89b49c75f068f1214de8fa5b732c2bb13fb920b446e5223a978eda90d041e41c |
| PINS-SOURCE-002：cc06dc859d5e1dc597573a24c93ee81b206654db512d3fd4dde04b787be5e21c，现代3.12.14 | 最终46方法通过，root13468 exit0、514.847ms | SOURCE-MODERN-002.json：5ac14b61abdd16d163dcf1059bbfb0d7b3c3aa1e39768fc9b24b0251905ca36c |
| 同SOURCE-002输入，国信实际3.6.8 | 最终46方法通过，root19852 exit0、656.929ms | SOURCE-TARGET36-002.json：38a3384d829fa30cd6774e855b9a4a60ca71222c188bab6f239f4c46f50b6fb9 |

各GREEN结果0失败/错误/跳过，源码与适用静态输入前后匹配，无SDK导入或新存活线程。最终46包括服务24、控制12、重连10；两环境重复方法分别证明环境兼容，数量不相加成独立场景。PURE的对应生产源码保持，BG2合同后继补充仅作用新控制订阅，按影响复用125证据；它不替最终源端46或真实运行。实际argv、根句柄、原D、双EOF、tree0、reader join、资源关闭分别见ROOT-HANDLES-001、ROOT-HANDLES-SOURCE-001/002及ROOT-HANDLES-RED-002；无控制台或强杀。RED的业务失败与资源正常收口分别成立。

## 根因回归与审查

001发布前只比较stage/code，编码若跨原D仍会发布旧成功；状态封套也存在同类窗口。002在内外编码完成后沿原D刷新并有界重取安全终态，成功认领点先核原D，锁外发布仍持续计owner。三个Event门控分别使内层open、最终completion编码及status跨D，原001实际返回snapshot成功，修后返回expired。

001的open订阅只等future完成，不随原控制CALL退休。实际双peer在Source接收D较早而Host自身D未到的窗口正常收发过期REPLY/ACK后，原seq已退休；重复同业务ID可累积订阅，迟到SDK完成再reply触发ProtocolError。原反例六轮数量为1..6，修后各为0，SDK仍只一次且共享future保持。该fixture使用可信注入的两端UTC偏移模拟接收D较早，未实测OS采样中断。新增poll/decode跨控制D回归共同验证完成边界；不修改原peer。

独立full001（外部历史/待归仓路径：`../../build/qmt-bulk-source-independent-001/full001/REPORT.md`）保留原两项发现；RED复核（外部历史/待归仓路径：`../../build/qmt-bulk-source-independent-001/red002/REPORT.md`）确认五失败与实际字节。最终delta002（外部历史/待归仓路径：`../../build/qmt-bulk-source-independent-001/delta002/REPORT.md`）已关闭两项发现，无新必要P1/P2；报告SHA99515ae50a0ed57dea64af407f7c9464f0d75d4321527c1419acaac238635468，清单SHA0b6daf527190b24daa27532483041f7c57a731893c2b23b44965a2c997142087，共81项封件逐字核验。作者与独审均未执行，根统一运行。wrapper十项使用FakeAgent验证常驻退休责任，服务/控制使用实际BA/BS及内存双peer，不能把它们称为真实SHM或供应商SDK。

## 限制与后继

尚未生成/装载v5配对正文，真实月窗/全历史、证券ETF覆盖与吞吐未验。Host最终CSV/QMI→原Journal terminal→ACK、C++ bulk/artifact及正式系统发行仍待接线。历史文件交原Importer/Helper/DSB/Reader，不引入行情数据库。Host后继已选择[原正文固定身份与D、复用同表且无新增列](../migration/qmt-bulk-history-export-plan.md#host持久接缝的实施选择)；精确HTTP与产物定位schema先冻结再实现。

本轮旧QMT项目只读参考，未执行或导入。未启停终端策略、未真实下撤单或切换生产；已装GH_WT_MEMORY_VERIFY摘要仍4034e03e12be1ee219ce828829ba76eb64a3843e1c3871e7d278ceb3707bd09d。常驻实际两代、完整交易恢复、策略/观衡与独立发行保留总目标。当前无需用户决策或操作。

模块、方案、证据索引及NOW/CURRENT/TARGET已同步。project.py check实际PASS，仅证明本地文档导航和技能清单；root30892 exit0、4.033秒，原Job/双EOF/join/资源关闭确认。最终输入、审查原件及已装正文摘要复核在build/qmt-bulk-source-validation-001/POSTFLIGHT-001.json；本轮文件保持工作区状态，未发布。
