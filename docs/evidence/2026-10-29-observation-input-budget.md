# 观察供应商输入预算与真实PB后继

类型：开发及来源验证记录。状态：in-progress；完整模块C保持active。要求沿[OBI5](../specs/independent-market-observation.md)、[三会话计划](../migration/parallel-system-delivery.md)；前轮调度资格沿[原证据](2026-10-29-observation-scheduler-progress.md)。本轮原件根为build/observation-input-budget-001。

## 根因与责任层

固定baostock0.9.4的socketutil先无界累积完整响应并一次解压，ResultData再整批解析；逐行循环前已经分配数据。其setData使用split/join，会删除JSON字符串内空白。旧股票增量用zip和str处理原始行，行宽、类型及重复身份可被静默改变。HTTP和SDK的分块请求也需要同一个绝对截止，避免持续少量数据到达延长单次请求。

新增本来源BaostockClient：沿固定SDK常量和公开消息合同装配匿名公共端点，实例独占socket，不改SDK全局context、函数或默认socket超时。原始wire先归档；接收和限量解压、结构与规范表、总线上字节/展开量、实际协议发送数和原批次D分别准入。CollectionBudget的单请求绝对截止由HTTP与该客户端共用。供应商数据仅供独立观察，WT-D01/D03及A的行情/历史职责保持，未新增WT核心行为或第二套策略行情权威。

provider_tables统一股票字符串表合同；传输和归档重读共用字段、行宽、类型、UTF-8、单元格/行/字节准入。stock_partitions在Arrow前检查新增容量及日期/证券/重复身份，完整准备后才替换候选索引，合法原始字符串和可选列保持。原PB筛选与等权算法复用，未通过缩小证券集合取得资格。

## 原条件复现与开发主链

全部a15的266源码输入已先复制至review-base-001并逐SHA核同，BASELINE-SHA256.json保存原身份；此前已审制品保持。

BASELINE-PROBE.json与pytest-baseline.xml：旧函数实际接纳六类坏股票输入（浮点、短行、重复列、重复日期证券、不合法日期、伪造parent列），对应六项回归均为DID NOT RAISE。旧供应商函数在max_requests=2时实际发送5条消息，预算计数0，并改变名称内空白；新函数在2条后拒绝并关闭socket。探针只在独占QA解释器内加载已冻结旧函数，原端代码未改。

main-001的来源/完整发布成功，48指标snapshot为d96bc9fa…c58b6d；QA随后错用一般小分区读取器读股票分区，故在HTTP之前失败。其实际computation_identity与当时源码逐项核同，并冻结source-main-001/CODE-SHA256.json。后继QA改用股票流式列读取，保留原失败。

main-002使用独立Appa16第四份wheel、实际原客户端与本地合成协议TCP，4001只股票、股表分页/日历/压缩日线、完整PB和标准股票归档、全部历史/引用验证及48指标发布、实际HTTP/既有生产SPA宽窄屏通过；14条实际协议发送全部计数，字符串精度/空格/制表符及父原件保持，App/线程/端口/外层Job均关闭。原总耗时301.984秒，snapshot为611919ff…68b92fc。该004候选SHA为1b3c09ebdd6811512c50322cb51b845ed7ff48265c90dbaebfdb9b8cfe9ef891；后继真实协议修正和请求整次截止不移授此输入的整链资格。

## 真实公共来源与协议纠正

live-001已取得公开登录原件：服务器版本00.9.10，客户端常量00.9.40。原过严版本相等检查拒绝，记录为pb_protocol_schema；头部白名单原件在HEADER.json。live-002取得首批证券资料原件，列头带排版空白，原严字段检查拒绝。后继分别登记两类版本，按供应商合同规范列头首尾排版空白；JSON行值保持原样，新增实际形态回归。

live-003在35秒原D内取得9024条证券资料及1条日历，日线尚未完成，返回collection_timeout并关闭连接；没有发布模型或改current。live-004使用明确120秒总预算/30秒请求时限，9条协议消息完成公开匿名读取：9024证券资料、1条日历、5223条2026-10-28日线。socket_closed=true，原件和规范表均留本根；它授真实协议读取，不单独授全模型发布。

real-replay-001对该真实wire做零网络重放，当前字段/容量/原请求D与原PB业务准入通过。实际日线日期均为2026-10-28，universe_count=5223，sample_count=5151、excluded_count=72；盈利样本3597/排除1626。原始可获知时间保持null，没有伪造披露时点；单日计算与整个观察快照发布分别验收。

## 当前候选与续接

第五份Appa16已从85项源码冻结构建并独立安装，wheel SHA为e9b09681cd34484dce19c281537937fd2538c1c6ee5664b689e7e37119d11573，普通环境30发行依赖检查通过。独占测试环境按uv.lock哈希装公共依赖和固定SDK/纯包/App，37发行兼容；原隔离子进程-I缺App的环境失败已通过安装修正，不降低测试隔离。

focused-003当前35项通过，含64KiB HTTP/协议分块、真实版本/列头、分页/原字符串、超请求/响应/解压、超时/取消、坏行/容量/来源失败保留原current。最终backend-004为142项通过。原冷启动10秒正向用例耗尽D，正向声明改为30秒，原D本身始终没有续期。后续独审指出64KiB HTTP用例没有覆盖真实小块聚合，不能据此授予HTTP全部截止资格。

main-003第五份安装的真实来源→历史尾部至10-28→完整48模型/股票归档→实际HTTP/SPA主链已通过，原总耗时390.766秒。实际16条协议消息、3443724线上字节、8225679展开字节；新快照48a63f386a5cd0f9df9bd43f5f2e0c747bfc700cba1ec15eb33e1ce41974b589，末日5151样本、等权PB3.9576187503397398；页面显示3.9576。30发行4680 RECORD、270源码/39原件/15 QA均核同。该入口为安装环境公开refresh手动调用，后继App只读；新PB的实际CLI/受管调度另验。其他47指标沿冻结历史，完整21来源/A八指数/自然09:00、M1、全策略和统一发行继续。

## 两轴独审与HTTP后继

005两轴full均gap，两项P2：HTTPX在检查前聚合小块并自动无界解压；collection构造Fetcher只传全局时限，来源级更短时限失效。原报告SPEC-REVIEW.md SHA为19890af2808cd895c20cf579cf1d65e77e6710f0198fef57e32798d0000224b8；STANDARDS-REVIEW.md SHA为0d35524bdff0ec36ff7595979c7347978886967534e75c26ba9a327497d2ce20。当前270输入已逐SHA保存至build/observation-input-budget-002/review-base-005，旧001制品/原件/QA保持；HTTP后继在002独立登记。

后继原条件：baseline-http.xml使用冻结005源码和冻结测试，10项中6项预期失败，实际复现1字节响应头/正文、停止、gzip/deflate展开前内存及来源时限。新网络接缝在原始IO和SSL BIO/TLS-in-TLS层共用原请求D，原始正文先留存后有界解码，来源时限统一取min；HTTPX/httpcore保持固定版本，环境代理/NO_PROXY/系统证书验证继续有效。http-green006.xml的24项通过，含实际HTTP代理、池复用、无代理、CONNECT/TLS及HTTPS代理内TLS正常/慢头、自签证书默认拒绝、压缩层/多成员/截断/未知编码/总解压量。首次补测发现OS毫秒取整提前超时会误分来源/批次owner，已由RequestDeadline统一归类，原失败green002/005保留。当前后继安装/受管完整发布及delta独审继续，尚未授后继切片完成。

未操作QMT界面、旧QMT、137/140实例、真实下撤单或生产。公开供应商访问与本地合成/真实原件重放各自登记；本轮无用户必需操作。

## 006受管安装与真实来源矩阵初查

006 wheel SHA为a3081eb0cc987c55887d74a8ee82dd7aed3e4ed24fff67afadb4bba250abfdc8；86构建输入、88 ZIP成员、普通30发行4681 RECORD与安装匹配。SOURCE-SHA256绑定272输入，review-current-006保存同字节镜像；相对005为7改2增。backend-001为166通过，包含当时正常请求0.2秒/间隔0.25秒的24项；当前正常连接复用正向声明为1秒/间隔1.1秒，避免在完整发布并行负载中把存证IO的0.2秒容量当正常条件，原失败保留。实际-I安装24通过在installed-http-collection.py.xml和INSTALLED-HTTP-collection.py.json（QA局部变量覆盖输出后缀，已修命名，原件保留）；它绑定当前1秒/1.1秒测试字节，其他142项产品输入保持。

managed-http-001已通过正式普通安装App→原observation_service受管子进程→实际HTTP代理gzip固定响应→48指标完整验证/事务发布→同版生产SPA宽窄屏→两代停止/重启去重。原时钟补跑2026-10-28的09:00窗口，来源日期27；该输入明确合成，natural_0900=false。snapshot为cb26a9e88bf41bdd6df8591c9cf4ae434bbd5fe562b8ade0bb854551f419a4db，3次GET，原总耗时333.109秒；资源、监视线程、Job/EOF/join关闭。真实PB的managed-pb-001另在原时钟/原受管入口运行，当前尚待其终态，不能挪用手动或合成资格。

后继终态：managed-pb-001复制的根已经登记同一窗口完成，原调度正确跳过，QA的新版本断言因此失败；其原runs与正常closed收据保留，不授新增PB采集。managed-pb-002改用此前未完成该窗口的既有隔离根，没有删除完成索引或修改去重规则。正式普通006 App→原service CLI核来源原字节SHA→原时钟补跑→实际公共匿名PB→全48验证/事务发布→实际HTTP/生产SPA宽390→两代正常关闭/重启零新attempt，406.062秒通过。15协议消息、3079189线上及7264877展开字节；10-27的5154样本、均值3.9240724493597208由实际规范原件独立重算匹配。snapshot为c6ec9a29ff0d5fc206c1c0352af476b674d8eef737c7edd9f60979668bd9acf2，其他指标沿冻结历史，natural_0900=false。

最终安装补件INSTALLATION-006.json SHA为fbaa43e56d790733a6302ddbbeae3a13899aa7d0be3bbe632cd9b379bc5adcc7；272源码、23 QA、83原件的清单分别为SOURCE-SHA256/QA-SHA256/EVIDENCE-SHA256，镜像与实际安装核同。最终两轴独审补件继续，不授完整来源或模块完成。

同006安装对19路HTTP公开来源按原source_window逐路初查，原件在build/observation-source-matrix-001，各路显式55秒原D/32请求/64MiB总量及原70秒Job。11路实际解析：基金配置2行、北向13行、市值/GDP225月及20年、港股三指数各13行、中债13行、中金所7组各13行、上交所5组各6行、深交所6行、SGX12行、融资13行、Shibor6行。4路披露页仅留存正文、没有观测数据；PBC大型银行已取得PDF但缺pypdf安装依赖，repo/IRS/申万3路原网络失败。所有客户端已关闭；这些是实际逐源读取及解析，尚未授同一完整候选发布/来源语义独审或21路全部可用。A八指数仍待相应真实接口。

后继诊断独立于006资格：build/observation-pbc-001使用捆绑pypdf6.10.0/pypdfium2读取、渲染并人工核对央行一页原表的2026年月列和亿元单位，既有业务解析可读取9月比值；该工具环境不转授普通安装资格。三路连接与原HTTPX对照同错：repo/IRS为UNSAFE_LEGACY_RENEGOTIATION_DISABLED，申万verify_code20。另在build/observation-source-connections-001用系统默认可信CA且保持证书验证，申万实际13行解析；HTTP候选失败，货币网HTTP候选亦失败。该诊断尚未改变产品TLS政策或普通安装。后继按NEXT-PROVIDERS-PLAN.md补PDF闭包、官方连接、逐路语义/范围、A八指数及同候选真实发布。

## 006最终交付与后继

两轴独立审查均完成固定源码/普通安装/受管HTTP及真实PB主链的最终补件核验，原两项P2关闭，未发现新增P0/P1/P2。SPEC-DELTA-REVIEW.md最终SHA为fe87e2bca3b3fffffcfe07c0b030691d3bd1f461a03882cad5f824676bacd8a7；STANDARDS-DELTA-REVIEW.md为9ab2587ad2fe3dee30371431a59fe71aa024daec6a064890cd55ef4763b8bc5e。审查者分别复算捕获SHA/线上与展开计数、PB样本与均值，并核普通安装/四代控制收据/SPA和原件范围。

build/observation-input-budget-002/DELIVERY.json状态为engineering_slice_complete、full_module_complete=false、goal_status=active，SHA为8377c5a3d70b950f5a777c0b7baeb989664e1edb3e53d0f411447df4bca02aab。最终原件/源码/QA摘要再次核同；project.py check通过。该结论授HTTP/PB输入预算修正及限定的正式受管主链，完整目标沿原模块计划继续。

下一段推进PDF独立采集依赖和输入准入、系统可信CA候选的明确连接政策、货币网官方有效连接及完整19路语义/组合发布；A八指数、自然09:00、M1稳定与完整保留策略、统一安装/升级回退/操作员链仍须实际验收。当前没有活跃验证进程或需要用户处理的新增事项；两轴审查均终结，未真实写或发布。
