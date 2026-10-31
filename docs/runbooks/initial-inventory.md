# 当前持仓作为新运行初始库存

类型：模块B运行侧准备入口。状态：开发候选，当前资格见[实际证据](../evidence/2026-10-30-initial-inventory-baseline.md)。要求为[NRT-R30](../specs/native-realtime-strategy.md#nrt-r30-当前持仓初始库存与新的运行基准)，业务决定及初值定义沿[唯一方案](../migration/retained-strategy-takeover-proposal.md)。本入口只准备配置输入，运行由原WT受管宿主负责。

## 输入与原生复用

原RetainedRuntimeInput模板保留行情、复权、参数、显式本金和数量policy；其中旧cycles及previous_exits被本次初值整体替换。当前事实文件使用guanheng.initial-inventory-facts.v1，精确包含schema、broker_source_sha256、captured_at、valid_until、captured_uptime_ms、valid_until_uptime_ms、trading_date、positions。每个非空库存包含symbol、quantity、sellable、mark_price、mark_source_sha256。证券限唯一策略八标的，数量为股/份，标价为CNY/份；总量/可卖从当前券商事实传递，标价从明确当前行情来源传递。来源摘要绑定原事实，捕获/有效时间表示该冻结输入的接收准入，分别保留原来源时间，不宣称四查询共同事务。

UTC与同进程系统uptime有效窗均需覆盖准备时点，最长一小时；两个源文件均显式提供完整SHA。事实文件不接受旧开仓日期、历史交易或旧周期记忆。缺当前数量、标价或来源时由生产者补当前事实。新运行库存基准不读取旧交易流水。

准备入口为普通已安装解释器的`python -I -B -m guanheng_wt_runtime.initial_inventory`，参数为`--template <绝对路径> --template-sha256 <SHA256> --facts <绝对路径> --facts-sha256 <SHA256> --output <全新准备目录> --seconds 30`。输入只读，输出根的父目录须已存在且无链接/重解析点；目录独占创建，已有目录保留。项目当前工作根及TEMP/TMP/缓存均使用E盘。

先读取和核摘要，再建立启用UTC基准，用原唯一核预检。成功输出runtime-input.json、非空库存时的native-input.json和最后的PREPARED.json。各文件独占写入、flush/fsync及输入回读；失败留下本次已写原件，完整准备资格只由最后收据及文件摘要确认。该收据表示输入准备完成，不表示启动、clean或交易成功。

## 接入原受管宿主

将runtime-input.json的路径/SHA交原guanheng.retained-cta.v1配置的input_file/input_sha256。非空库存的native-input.json交原takeover.input_file/input_sha256；其内部协议继续原P23的guanheng.cta-takeover.v1和takeover-mark，不要求旧开仓资料。周期ID以initial-inventory标识新运行，时间是本次启用基准；原WT会重新核当前券商数量/可卖与未决责任，再加载原持仓/组合文件。空库存没有native-input.json，沿原fresh空仓初始化。

首次运行使用原record_clean及独占空金融根；有未决/活动/unknown命令时仍按原责任准入。生成的库存作为已有数量，不发初始化买单；首轮业务计算仍可按原策略目标产生真实差额。原WT起始标价成本、收益/费用0和原KV保持唯一账本，准备工具不维护金融状态。

后续正常重启使用原resume_clean与相同输入身份，延续本系统已生成的周期、数量阶段、费用及盈亏；不重新调用初始准备清零。真实下撤单及生产切换需相应授权。当前事实生产者的自动装配、统一安装和真实来源资格与本准备入口分别验收。

## WT启动时自动准备

自动启动后继使用guanheng-strategy-v1==0.1.0a8。策略核接收明确的initial_inventory状态和baseline_at，opened_at为空；原P23载入明细的时间仍表示新账本起点。旧a7开发候选与证据封存保留，后继资格以新的安装与实际入口为准。

在原guanheng.execution-deployment.v1中显式加入initial_inventory对象，字段按[NRT-R30](../specs/native-realtime-strategy.md#nrt-r30-当前持仓初始库存与新的运行基准)：state_root是全新E盘准备目录；account_observation的descriptor/sha256指向原账户扫描部署；market声明原行情SDK连接及token环境变量名；max_age_seconds为本次账户/行情来源有效期，最多3600秒。原python_strategy仍提供策略参数、预算和市场模板；运行侧自动替换旧周期及退出初值。配置不填写库存数量或旧交易文件。

首次record_clean由原执行监督线程运行原ManagedAccountScan，完成当次四查询及资源回收，按原事实提取数量和可卖，向原行情SDK查询这些证券的有来源标价。随后调用原准备API和唯一核预检，在state_root独占写当前库存事实、原输入与BASELINE.json，逐文件flush/fsync和同D回读。该目录保存启动来源与输入，不存资金、持仓、成交或绩效账本。旧成交查询仅用于当前责任与来源身份，不导入策略历史。

每代实际原生配置写在原控制目录，指向这一份固定输入，再由原P23重新核当次实际数量、活动订单和未知责任后加载原WT文件。BASELINE.json只证明原输入已准备，不证明原生启动或正常停止。来源不完整、无有效标价、已有不完整准备根或原责任不允许时沿当前阶段失败，原件保留。

后续resume_clean使用相同state_root、模板和来源配置，核原准备文件摘要后只读复用原基准；原Native仍取得本代账户查询并按原clean准入。改成record_clean不会覆盖原准备根。省略initial_inventory对象时，原手动准备/空仓执行工厂保持其原入口。自动启动、非空库存主链和恢复资格正在后继验证，准备CLI的封存资格保持原范围。
