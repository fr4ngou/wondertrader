# 原生策略读取券商资金与持仓

类型：模块B隔离开发证据。状态：安装主链通过，独立审查与精确制品封存中；完整模块及真实M1保持in-progress。验收对应[NRT-R17](../specs/native-realtime-strategy.md#nrt-r17-策略读取当前券商观察)。

## 实现和事实归属

唯一1.1.2实时桥需要当前券商数量、可卖及资金，原策略上下文继续提供WT策略理论状态。自有BrokerQueryAdapter在原完整P/A回调后分别记录接收时间和修订号，StandardExecutionHost复制原账户表与最近CNY观察，CtaProcess在查询完成后发布不可变副本。Python的CtaRuntime.broker_observation及INIT/SCHEDULE借用期的CallbackContext读取该副本。各自接收时间保持原查询时间，不因重复读取延长新鲜度。

原Adapter继续拥有账户事实，原WT继续拥有策略持仓、组合与绩效。扩展没有累计成交数量、分摊归属、推算成本、补建资金账或改变WT调度；本轮新增WT核心修改0。完整零行查询为已知空仓，公开集合只包含非零方向持仓；关闭前后无可用副本时返回broker_unavailable。缺可选扩展的旧运行库报告broker_capability，其余原入口继续工作。

## 固定输入和安装

原件根为`build/ms-retained-runtime-001`。最终native-002复用P23冻结原库，重编自有CtaProcess并重链同批Runtime/exe，BrokerQueryContext、Session及Host自有库沿native-001输入复用。BUILD记录618份冻结源、33个链接输入及21个安装文件；构建没有从当前共享脏树重新编译WT核心。

INSTALLATION-002是Appa19的隔离开发wheel，只替换B拥有的execution_strategy.py及wheel RECORD；其余原payload保持。实际普通安装35发行、4803条哈希RECORD及pip check通过。这套旧依赖闭包仅验证公开接口，不授予唯一1.1.2完整App发行资格。最终运行DLL、wheel、安装API与安装头/导入库身份见本根BUILD、INSTALLATION及DELIVERY收据。

## 安装主链和关闭

| 原件 | 实际结果 |
|---|---|
| broker-hold-002 | 原Factory的INIT/SCHEDULE读取券商1000份/可卖1000及资金30000元；同根两代12查询、新委托0，原接管记录不变 |
| broker-refresh-003 | 显式SDK替身卖200，完整委托/成交及查询后返回800；后继策略调度读取800，持仓revision递增、账户revision/接收时间保持，13查询、实际替身调用1 |
| broker-multi-002 | 两证券分别1000/400及原各自开仓时间保持；公开集合2行，C ABI容量1返回-5及required=2，6查询、委托0 |
| broker-empty-002 | 源端完整P返回零行，公开positions_known=true且空tuple，原策略保持空仓，6查询、委托0 |
| broker-zero-002 | 源端含额外零量条目，公开集合只保留实际1000份条目，6查询、委托0 |
| broker-legacy-002 | 新Python实际装载旧P23运行库，缺新能力单独返回broker_capability；原接管、策略回调、关闭均正常，6查询、委托0 |
| header-consumer-003 | 实际安装C头/导入库编译链接并加载同版DLL；Facts72字节、available偏移64、Position88字节，运行前Unavailable及参数拒绝，退出0 |

各正向子进程自然退出0；原closed收据、受管进程树/双管道及Host、SDK替身、HTTP/proxy关闭证据保存在各案POSTFLIGHT和控制目录。直接Runtime在运行前后不可用，过期CallbackContext拒绝借用，重复读取保持原接收时点，Python值不可变。所有真实券商调用、真实下撤单和生产切换均为0。

## 保留尝试与资格边界

native-001及broker-hold/refresh/multi-001保留首次输入及结果；最终零量过滤后在native-002重验相应链。header-consumer-002因QA编译未声明UTF-8而失败，003使用项目UTF-8选项后通过，原失败日志保持。broker-refresh-002业务链通过，但QA把成交后800误标为initial_quantity；003固定报告初始1000并重验通过，002原件保持。

本轮资金、行情及证券为明确隔离替身，目标为合成持仓接管目标，真实数学核未运行。P/A独立接收，源SDK采样时间未知，未授予四查询事务语义。当前值不提供真实连续持仓周期或成交归属；唯一1.1.2仍须消费实际周期起点、预算及A同基准前复权材料，接入当前C纯核/回放合同，再验证完整实时目标、委托撤单和同核结果。资金/T+1及费用、异常恢复、统一安装与最终页面仍按模块B逐项推进。

## 最终限定交付

独立full及零量delta已封存于本根REVIEW-001，SHA256 `fe473a80ec08d694db830c2591c15ec542fb5b7acd00e9e39ab5154d54f296c4`；原冻结12源/53直接绑定/1720原件全部零漂移，零量P2已关闭，所声明安装合成API范围通过。C3的nullable/断线/缺CNY及未知资金None仍保留静态边界，未新增动态资格。

最终Runtime SHA256为`b8d525706ac2f5cca92a73379b41a287a54217305f1c4422f10ef03ff887aa23`，开发ZIP为`289f5377503706c5d6b220eacdd558a4ea1b4634896f8427e1969946dd3fd964`。开发包26成员包含21原生安装文件、1 API wheel及4份收据；完整35-wheel离线环境、当前唯一1.1.2 App及生产发行均保持待完成。DELIVERY-001和FINALIZATION-001登记最终接口、文件身份、实际关闭及上述缺口；本段为作者封存后继，已审源码/规格/原件均保持。
