# 历史行情适配使用上游公开 ABI

类型：功能最终规格。状态：accepted。前缀NHA。维护范围：自有历史文件边界、消费者及隔离构建。承接[NHP](native-history-preparation-shards.md)、[NHQ](native-history-query.md)、[NQW](native-history-window.md)。

## 目标与根因

当前历史实验组合调用未批准新增的`read_dsb_bars_limited`，链接的Helper含CORE-002/003，Storage含冻结Writer差异。摘要与旧冻结相同只证明输入稳定；以该组合通过的结果不能授予原始上游或仅含批准修改的构建资格。

使用固定上游`08b230dd05facf6d650d949bfe51054115a2ecb1`公开`store_bars/read_dsb_bars`及原IRdm/Factory，必要安全边界放在自有模块。保持原工作树全部vendor文件、旧实验二进制/证据、真实数据及原运行；本切片不修改、退出或保留为交付任何未批核心差异。

## NHA-R1 自有有界读取与原始解码

自有模块统一压缩字节、V2块头/类型/长度、单帧边界、已知非零解压长度、Bar整除/数量和解压/副本预算的准入，复用并收敛现有`native_rows`相同规则。C++受管min1及IRdm路径继续限定m1；既有Python显式1m/5m/1d读取保留原类型约束，由调用方声明且与实际头类型一致，缺依据不扩大格式兼容。继续由原Helper解码完整Bar、由原IRdm/Factory索引及派生周期；不新增格式解析器、聚合器或同名伪上游导出。

预检必须发生在原Helper/Reader可能分配解压内存前，失败不调用该原生读取。回调核对声明数量、实际累计、最终标记、返回数量、指针/边界；异常、零回调、截断或不一致明确失败。线程局部收集状态须在全部出口恢复，异常不得跨C ABI；仅在回调有效期复制。

## NHA-R2 所验字节与实际读取一致

调用原路径型ABI前，自有边界固定已验证字节，建立独占新快照，并在原调用期间防止该快照写入/替换。保障覆盖完整路径命名空间：最终文件租约之外，各级祖先及reparse/junction须被持续固定或明确拒绝，防止原IRdm根路径或私有Snapshot temp祖先在预检后改指另一对象。单次属性检查、canonical、路径前后hash或原writer互斥均不能单独替代这项保障。Windows用明确的文件共享/删除限制及实际并发测试证明；已有原生generation快照同样核验其生命周期。其他平台只有在同一不变量可证明时启用，缺机制明确Unavailable，保留未验证标记，不退回不安全入口。

压缩体、原生解压体、结果副本和Reader缓存分别受界定预算；不声称进程RSS硬上限。句柄、私有临时文件和回调所有权使用RAII，成功/失败/释放均清理本次自有资源，清理绑定本次资源身份，禁止经已可替换的路径递归删除其他对象、原始数据或旧证据。release不与未完成同步原生调用并发销毁其依赖；保留原owner/队列约束。

## NHA-R3 原store ABI及发布判定

调用原`store_bars`前校验指针、正数条数、已声明周期和预算。每次输出使用独占新身份，排除旧`.pending`残留及替换复用。写入返回bool作为信息，发布资格由本次输出存在、完整原ABI回读逐字段一致、来源与内容摘要匹配及原单写者发布协议共同决定。创建失败、短写、残留旧文件及回读失败均保留原已发布数据并失败关闭。

不修改原Helper错误返回，不借Writer生命周期冻结差异实现历史发布。Store sidecar、来源会话/单位/内容冲突与恢复、冻结语义保持；不新建数据或审计数据库。

## NHA-R4 消费者与独立接口归属

C++ History的merge/readback/freeze/recover及无IRdm查询全部经自有有界入口，再调用原公开Helper。Python `integrations/guanheng/native_history.py`的目标交付路线显式使用自有边界制品及其版本/摘要，禁止继续寻找未批上游limited导出；自有C ABI使用清晰的自有名称。真实构建输入与消费者配置一同登记，旧实验消费者和证据保持可追溯，不默默赋予原ABI新保证。

既有HTTP/SDK wire、m1量额/时间、coverage、NHP固定partial窗口、NHQ代际/背压和NQW周期语义保持。自有二进制一起重建；独立SDK wheel无变化则不改版本。迁移直接断言修改版Helper行为的自有测试，新增负向测试覆盖真正责任边界。

## NHA-R5 独立固定源码构建

在新唯一目录从Git blob提取历史链必要vendor文件并逐项核Git对象和SHA。历史目标仅需WTSUtils/WTSTools/WtDtHelper/WtDataStorage及必要公共头/Factory；只叠加已批准NRC空count分支及中文注释，核其完整源身份。此历史profile不需要CORE-004/NCS，其余vendor输入必须等于固定上游。构建侧复用已验C++`/FIobjbase.h`和`NOMINMAX`处理Windows头顺序，禁止修改vendor源码求编译通过。

原Storage完整DLL可以包含原Writer，但本路径仅创建IRdm，不实例化Writer。构建/链接清单必须能证明实际输入，原Helper不导出limited，自有边界明确导出自身ABI。使用原类型声明核sizeof/offsetof、回调约定及原ABI写读；源码布局相同不替代二进制验收。构建脚本/缓存依赖复用原工具链，冻结目录及旧产物不覆盖。

## NHA-R6 验收与资格

先绑定当前未批ABI依赖的原样失败：当前消费者对原Helper声明/导出不兼容；修正后绑定新源码/测试/原始vendor对象/唯一NRC overlay/库及产物。新增预检前拒绝、异常帧/超预算/多帧/未知raw、回调不完整、零回调/重复终态、嵌套/并行TLS及异常logger边界；源替换/并发写删、IRdm及私有Snapshot祖先junction替换与普通目录的真实区别、检查后路径变化、身份绑定清理及资源释放；原store创建/短写/残留与发布回读失败；空Reader NRC、同实例追加/修订及旧副本、快速代际背压、原生Factory周期、NHP公平性/partial/发布重试、公共HTTP及Python自有边界消费者。分配故障的实际注入范围和未测范围明确登记，禁止以危险巨型分配代替安全的准入回归。

先运行必要root-cause及历史相关测试；成功后复用同输入结果，不为补数字重跑。独立审查核对所有R和真实vendor来源，旧CORE实验结果只保留其原资格。真实428输入如使用须保持源摘要和原单位精度限制；新的合成结果不扩大真实来源、跨会话、跨重启、全市场性能或生产资格。
