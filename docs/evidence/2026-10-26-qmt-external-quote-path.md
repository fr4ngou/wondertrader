# QMT终端外行情读取入口核验

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-26。状态：OS与解释器实测通过；004/006外部RPC连接与两次小窗口查询完成，均空0行；全历史读取仍缺证。003身份门原失败保留。

## 已取得的事实

现有外部Host18017最近一次单次健康读取为HTTP200、来源unavailable/OSError；端口监听不代表共享内存来源可用。未使用其认证资料调用历史、账户或交易。私有输出事件见[事件记录](../incidents/2026-10-26-private-config-tool-output.md)，本记录不读取或复制私有生成入口。

本轮只读OS元数据确认国信XtItClient.exe派生的miniquote.exe（PID6272、创建于2026-10-22T11:53:41.8067110Z）拥有58610及58341两个监听端口。仅输出进程名、路径、父PID、创建时间和监听地址/端口，不读取命令行或运行配置。58610是SDK公开实现使用的默认行情RPC候选；监听事实尚不能证明RPC或历史读取成功。公开事实见OS白名单摘要（外部历史/待归仓路径：`../../build/qmt-quote-rpc-listener-observation-001/summary.json`）。

独立启动供应商pythonw.exe，以-I/-S/-B仅执行标准库ABI探针，实测Python3.6.8、64位、isolated1/no_site1，未导入SDK或启动终端。ABI原件（外部历史/待归仓路径：`../../build/qmt-quote-sdk-abi-observation-001/result.json`）。OS和ABI两次均实际code0、创建期Job归属、无控制台、自然退出、整树0、双EOF、reader join及资源关闭通过。文档start首包装调用因runpy缺脚本目录失败且正常回收；改为直接调用project.py后通过，原失败保留。

## SDK静态边界与候选

当前安装xtquant.xtdata.get_local_data在函数体直接return None，不能作为已下载数据的离线导出器。get_market_data_ex(1m)依赖行情RPC；reconnect显式ip/port路径在Python层不调用全局用户发现逻辑，失败最多再次连接同一client后抛错。未证明原生内部cache-only、网络/日志副作用或完整第三方依赖闭包。静态研究的辅助进程边界偏差独立见[事件记录](../incidents/2026-10-26-research-process-boundary.md)，不使用退出回执补授隐藏及整树回收资格。

新探针限定单证券600000.SH、2021-11-01 09:31至09:32、count2、未复权、fill_data=False；仅显式127.0.0.1:58610，不订阅、不下载，不调用账户、委托或撤单，不重启或换终端策略。使用33份选定供应商解释器/quote/BSON/config/DLL摘要和模块来源核验；这是选定输入身份，不是完整运行闭包。

候选004（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-004/PLAN.json`）由专用控制器（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-quote-rpc-small-window-controller-003/control.py`）直接以创建期Job启动；原单调45秒一次映射系统uptime，业务最多30秒、诊断收尾仍沿原45秒，第一层stdout8MiB/stderr64KiB保留有限原始字节至受控外部目录。只接受单次build模式，无实际SDK预热。SDK原始输出、异常文本和traceback不进入公开记录，公开结果仅白名单。

首轮静审发现来源前置绑定、原异常保留和D门禁三项P2；002继承的hidden_build/native.run会先无界收集并合并解码SDK输出，外层tail额度不能限制第一层原管道，已在未执行候选中改为直接Job。该发现只修试验入口，公共native.py和框架未改。具体full/delta结论分别沿对应源码身份记录。

## 首次实际执行与身份门根因

003只执行一次，实际coordinator2/child2、0.578秒、stage=preflight、RuntimeError；业务D未过、SDK未导入、无行情连接/读取。创建期Job、无控制台、双EOF、整树0、join与句柄回收均正常；原失败见根观察（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-003/ROOT-OBSERVATION.json`）。未读取private首错原文。

独立的有限OS探针证明：QueryFullProcessImageName图像与CIM路径及resolve都相同；GetProcessTimes返回FILETIME为134371436218067112，CIM时间推导为134371436218067110，同微秒而差2个100ns单位。原身份门用CIM微秒精度值作100ns精度相等判断，导致同一实际进程被拒。见公开创建时间原件（外部历史/待归仓路径：`../../build/qmt-quote-owner-identity-observation-001/result.json`）。004只将该常量换为精确GetProcessTimes值及新的输出/候选路径，保留严格进程代际相等判断。该有限OS探针code0并完整回收；没有以SDK失败归因此门。

## 实际RPC连接及空结果

004已按38固定输入再核后执行一次：600000.SH、2021-11-01 09:31/09:32，connected=true、stage=done、status=empty、row_count=0、源33项前后核同、业务D未过；实际coordinator0/child0、4.078秒、正常Job整树0/双EOF/join/句柄关闭。见公开结果（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-004/PUBLIC-RESULT.json`）与控制器白名单收据（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-004/CONTROLLER-RESULT.json`）。它授外部RPC连接及一次空查询完成，未取得历史行情行。根最初误用仅允许observed的断言拒绝了empty，已保留空结果，未重复执行004或改原数据。

005加入000001.SZ已有非空窗口控制及缓存目录枚举后，独审发现固定文件stat后缺SDK调用前D门（P1），未执行；006仅在实际SDK调用紧前补原D门并使用新独占输出根，窄审无新P1/P2。006再核38项后执行一次，000001同两分钟也是connected=true/empty0、业务D未过、源33项前后核同；实际coordinator0/child0、0.875秒及完整回收通过。见006公开结果（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-006/PUBLIC-RESULT.json`）、控制器收据（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-006/CONTROLLER-RESULT.json`）及审查（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-review-006/REPORT.md`）。两次独立D，不拼成非空或全覆盖通过。

006观察SDK Python的data_dir仍为sdk_default_relative；源init_data_dir会捕获并忽略其内部错误，这个枚举不能指认具体失败。旧已验ContextInfo交换样本中，两证券相同09:31/09:32均有真实行；已知D:/software/guoxin/datadir下对应DAT目前约18.4MB且存在，见已知行情文件元数据（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-004/KNOWN-MARKET-FILE-INVENTORY.json`）。早先另查userdata与userdata_mini四个候选路径均不存在，仅是路径存在观察，不作下载判定。SDK二进制包含get_data_dir等ASCII字符串，只授静态字符串存在，不授实际绑定或协议支持。

当前只能确认“RPC可连接，指定历史窗仍空”；当前服务使用的实际数据根、full QMT/外部SDK版本能力及空结果首因仍unknown。未下载/订阅/重启、不切换策略或生产。SDK原输出与首错未读取、未搬入公开证据；公开字段先按固定schema筛选。脚本中账户/交易0计数只记录显式调用范围，不作原生内部副作用保证。

## 下一步与资格

后续先核现行情服务缓存根与公开接口版本；保持正常、空返回和失败分别记录。取得非空且单位明确的样本后再复用QMI→原生DSB→Reader/策略回读，不引入行情数据库。量额单位、分钟标签、ETF及全部2021-11-01起覆盖继续分别验收。两条记录不能授全市场覆盖、持续实时、真实交易或正式发行资格。

## 同窗口v2对照后继

独立静态审查确认安装公开get_market_data走v2，既有get_market_data_ex的1m走v4。007保持000001.SZ、2021-11-01 09:31至09:32、count2、不复权、不填充不变，仅改变公开包装器及有限字段型结果投影。一次实际调用仍connected=true、done/empty、0行，SDK目录分类仍default_relative，33项来源前后核验；未调用账户、下撤单、下载或订阅入口。切换v2不足以恢复这个样本，缓存目录及全QMT接口根因继续未知，累计三次市场读取仍未取得新历史行。

公开结果（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-007/PUBLIC-RESULT.json`）和控制器回执（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-007/CONTROLLER-RESULT.json`）显示child退出0、5.813秒、Job树0、双EOF、join及资源关闭，无强杀。保留身份范围缺口：Node持有的venv启动器PID6700退出0，控制器自报PID1272，两者实际OS父关系本次未采。原ROOT-OBSERVATION中actual_coordinator_exit命名过强，后继限定更正（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-007/ROOT-IDENTITY-LIMITATION.json`）保留原件并分别记启动器句柄与控制器事实；不重跑补成功。独立动态复核（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-review-007/DYNAMIC-007.md`）与范围说明（外部历史/待归仓路径：`../../build/qmt-quote-rpc-small-window-review-007/DYNAMIC-007-LIMITATION.md`）保持该缺口，未读取私有raw。后续新顶层控制器使用已核直接base Pythonw并核Node PID等于回执PID，当前结果不扩大为完整来源或完整进程身份资格。


## 目录getter实测与版本边界后继

2026-10-26：目录诊断002已先在目标Python3.6.8执行六项纯合成回归，6/6通过且无跳过；测试仅编译五个公开函数定义，API与时钟使用替身，不导入SDK。随后只执行一次真实外部目录诊断：显式连接58610成功，get_data_dir和get_app_dir各显式调用一次，均正常返回空字符串；包装层data_dir分类为default_relative。包装器连接时自身还可能调用getter，显式调用计数不代表SDK内部总次数。

这项结果与当前init_data_dir的空值回退逻辑一致，给出了默认相对路径的可复现解释；没有观察到两个显式getter抛异常。它仍未证明行情服务映射到国信已下载的DAT目录，未取得新历史行。累计实际历史查询保持前三次，目录诊断的market/download/subscribe/account/order/cancel显式调用均0；不使用更改Python层data_dir或二进制字符串出现来推断底层缓存已切换。

实际直接base控制器PID58712与Node句柄PID一致、实际退出0，子进程49704退出0，0.407秒；原业务期限未过、源33项前后核同、行情owner代际核对和句柄关闭成功，创建期Job、无控制台、无强杀、整树0、双EOF、join和资源关闭通过。六项合成的控制器PID73772与实际句柄一致，子进程72236退出0、0.391秒并正常关闭。26项受保护框架来源摘要保持。公开根观察（外部历史/待归仓路径：`../../build/qmt-quote-directory-getters-002/ROOT-RESULT.json`）、合成收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-getters-synthetic-controller-001/ROOT-RESULT.json`）及独立动态复核（外部历史/待归仓路径：`../../build/qmt-quote-directory-getters-independent-001/dynamic001/REPORT.md`）分别绑定本次输入；根已复核19份公开raw和允许读取的两份固定JSON。SDK原stdout/stderr未读取。

官方[本地行情接口](https://dict.thinktrader.net/nativeApi/xtdata.html)说明get_local_data可显式接收data_dir；[版本记录](https://dict.thinktrader.net/nativeApi/download_xtquant.html)列出240119加入该能力。当前安装实现仍为return None，两者不能直接等同。为静态比较而下载官方240119b包的一次受控尝试在DNS解析阶段超时（curl28、下载0字节、无HTTP响应），没有取得或运行新SDK；原控制器正常关闭，见下载收据（外部历史/待归仓路径：`../../build/qmt-official-local-reader-research-001/ROOT-DOWNLOAD-RESULT.json`）。后续优先复用已有SHM history_1m/原线程get_market_data_ex(subscribe=False)能力核实真实来源，外部新版SDK仅为待证可选路径。没有修改或重启终端、没有调用setter或使用其他端口。


同轮后继只读GET18017/health再次返回HTTP200、服务status=unavailable、order_ready=false，13ms完成；仅读有限状态投影，未读取私有配对或输出完整响应。此项更新现有来源不可用的观察，不证明其具体错误原因，也未向来源发出历史或账户请求。记录位于build/qmt-quote-directory-getters-002/ROOT-HOST-HEALTH.json及ROOT-HOST-HEALTH-SCOPE.json；SDK原始输出仍未读。


## 当前缓存映射的静态后继（2026-10-26）

只读源码调查（外部历史/待归仓路径：`../../build/qmt-history-cache-mapping-research-001/REPORT.md`）核当前安装xtdata.py：v2/v4市场调用均未传Python data_dir，get_local_data体仅return None；两个getter正常空str可以直接解释default_relative，修改全局变量不能据此证明原生RPC改读下载目录。安装qmttools.ContextInfo仍转同一外部xtdata入口，不借其类名充当真实终端ContextInfo。已知Full QMT的两股票DAT仍为18386184/18429832字节，mtime保持；本次只stat，没有解码DAT。

有限目录元数据修正：D:/software/guoxin/userdata_mini/datadir当前存在，但其SH/SZ及两样本DAT路径不存在；先前“四个候选路径不存在”的观察不代表本次现场。目录存在、文件大小和default_relative均不能绑定native cache根或证明覆盖日期。根核34件封包加manifest共35件，选定31份公开来源，详见元数据（外部历史/待归仓路径：`../../build/qmt-history-cache-mapping-research-001/PATH-METADATA.json`）。

2026-10-26T00:03:53Z单次GET既有18017/health为HTTP200、status unavailable、profile restricted-read-only、reason OSError、order_ready false。只输出白名单字段，未发行情/账户/交易请求，未读私有配置或重启终端/策略，见当前只读观察（外部历史/待归仓路径：`../../build/qmt-host-fix-continue-001/LIVE-HISTORY-HEALTH.json`）。因此本轮没有执行建议的两分钟SHM history_1m窗口；来源恢复后先沿真实策略ContextInfo原线程核该窗口，再接既有WT导入/回读，全部历史/ETF/单位继续待验。
