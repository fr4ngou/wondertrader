# ETF及50常用指数分钟历史准备

类型：开发与实际数据证据。日期：2026-10-30。状态：completed_with_source_limits。规格：[EIH](../specs/qmt-etf-index-history.md)。操作见[维护手册](../runbooks/qmt-etf-index-history.md)。

## 清单与来源事实

QMT实际“沪深ETF”板块返回1758个当前成员。与旧清单相比，`158078.SZ`新增、`512390.SH`退出；退出项目继续保留原终止证据。旧逐项分类中的22个认购代码和22个认购现金代码从下载范围排除，当前候选为1714只ETF。板块、逐证券资料和选择分别保存原件及SHA；资料只保留证券名称、代码、市场、上市日、状态和ExtendInfo允许字段，未读取账户、委托、持仓或凭据。

指数候选按宽基、规模、风格和行业冻结50个具名代码。真实下载后，`000919.SH`、`000925.SH`、`000988.SH`、`000994.SH`、`000995.SH`仍无一分钟DAT。替补探针随后实际下载`000932.SH`、`000933.SH`、`000934.SH`、`399396.SZ`、`399441.SZ`和备用`399998.SZ`；六项均为58,593行、无负量额，首尾为2025-10-28 14:31至2026-10-29 15:00。最终50项采用前五个替补，选择SHA为`ce51e40d0f9129881be848734b29c15053e9022587d4ac92afb056fa5d7f5810`。没有分钟数据的五项及其原请求继续保留为淘汰证据。

最终50项的名称、代码、实际首末分钟、行数、已知边界缺口、DAT/DSB身份和原Reader状态见[50指数覆盖表](2026-10-30-qmt-index-50-coverage.md)。`INDEX-50-DELIVERY.json`逐项重新绑定57个原准备请求：请求ID均唯一，结果体SHA、窗口参数、终态和`call_returned`全部一致；50项DSB均与冻结源逐时间和六字段相等。交付收据SHA为`3b63000399b091d44ce1ba6c1e604ddbc0cf2ffcf30c8dac8450ed967482f6a6`，50项合计2,872,496行。

请求计划中的`remaining_windows=[]`只表示原请求已经执行完，不代表目标范围完整。50项最终DAT的首条记录都晚于2021-11-01 09:30，因此每项均登记从目标起点到实际首分钟之前的无记录区间；缺少权威交易日/停牌日历，观察区间内部完整性继续为`unknown`，完整覆盖证明数为0。旧`INDEX-50-COVERAGE.json`继续作为来源输入保留，SHA为`ff17a5906ea0a33b482661d40500ba89c2ceb5e045ecc705c336cede17d953e0`。

北证50单列来源边界。北京证券交易所的[北证50页面](https://www.bse.cn/market_data/bse_indices/bse_bz50.html)和[发布公告](https://www.bse.cn/uploads/6/file/public/202211/20221120115441_f8xaps28xy.pdf)确认指数代码为`899050`。本次QMT元数据原件存在`899050.BJ`详情；`D:\software\guoxin\datadir`下BJ、SH、SZ三个候选一分钟路径均无`899050.DAT`，当前HPR准备合同和DAT导出合同只接收`.SH/.SZ`。因此北证50登记为`unavailable`，没有伪装成已覆盖项。最终50项中的`932000.SH`中证2000作为当前可回读的小盘A股宽基观察代理，成份范围与北交所不同。机器边界收据为`build/qmt-etf-history-001/INDEX-BJ50-BOUNDARY.json`，SHA为`a2eb5c415186e27e7a547672ce2aaddda6d3cc2dd3850600d111e776f4c6906d`。

目标起点为2021-11-01，最新完整交易日冻结为2026-10-29。实际长窗调用成功后，多只证券DAT最早时间仍为2025-10-28附近；对`510010.SH`单独请求2021-11-01至2022-01-31也未增加旧记录。当前证据只证明“旧范围未观察到”，覆盖保持`unknown`，没有把它解释成完整历史或永久供应限制。

## 原请求、缓存和来源修订

实际调用通过受控QMT策略线程执行内置`download_history_data`。请求ID在调用前持久化；丢回复回归证明同一ID恢复只执行GET，不产生第二次下载。资源范围扩大只改变HPR日历窗口和任务/结果容量；行情设置、映射名称、quote secret和HPR凭据与原部署逐字节一致。

下载前保存稳定DAT副本及SHA。新DAT与旧快照按分钟标签比较OHLC、volume和amount，不合并、不造分钟、不改写源值。三个旧负量额指数重取结果如下：

- `000001.SH`：新DAT 58,503行，旧16,294行全部保留，777个重叠分钟发生实际字段修订，负量额归零；
- `000300.SH`：新DAT 58,301行，旧分钟全部保留，1,056个重叠分钟发生实际字段修订，负量额归零；
- `399001.SZ`：新DAT 58,592行，旧分钟全部保留，760个重叠分钟发生实际字段修订，负量额归零。

早先“新下载减少旧分钟”的临时判断经完整标签集合复核后撤回；范围校正保存在`CACHE-RANGE-CORRECTION.json`。正式实现直接转换供应商当前原值。若后续版本出现`previous_only>0`，状态明确为`source_range_reduced`并阻止冻结替换。

## 已跑通的真实主链

缓存复用主链用`510010.SH`原DAT，经原Exporter、QMI Importer/WtDtHelper、NativeHistory Reader逐时间和六字段核对，再与完整旧目录组装；公开SDK同时读到新ETF、旧ETF`510300.SH`和旧股票`000001.SZ`。

下载主链实际准备并转换`510010.SH`、`159001.SZ`和`000016.SH`，合计约17.5万行；原Reader完整逐行核对通过。另从实际SHM读取三只证券首尾各5根，共30根，与DSB全部时间和六字段一致。

正式`qualify`入口由同一拥有线程创建和关闭原NativeSourceMarket及单线程HTTP服务，公开MarketClient查询新ETF、新指数、旧ETF和旧股票四类共5项。用例固定精确条数、首末分钟及完整六字段序列SHA；用例文件路径、文件SHA和规范化内容SHA同时写入收据，重复证券响应使用带序号文件名，临时Bearer未持久化。

严格收据版本的真实闭包样本随后完成。`510010.SH`、`159001.SZ`和`000016.SH`属于同一旧store，另加入`000300.SH`、`399001.SZ`形成5只转换清单。只读准备发送0个下载请求；`frozen-sample005`连续两次冻结得到相同输入。评审加固后的最终复验为`converted-sample005/RESULT.json`（SHA `077f2f743b2faeb2afc578c3106b8a5da73b55893fbbe4a08d392b2745463bfb`）：转换前后逐一复核冻结DAT字节数和SHA，并绑定选择、冻结完成收据、冻结快照收据、Helper、Reader和逐行回读SHA。`assembled-sample005`解析原生导入收据并逐成员核路径、条数、首末时间及DSB SHA，按完整旧store闭包装配5,343只证券，结果SHA为`ae43d89249bf84f9f3c42cae070974f1f24ec8eae2517ce0b91874a7df4f01f3`；`catalog-sample006`注册5,343只；最终公开查询复验位于`build/qmt-etf-history-001/qualify-main008/RESULT.json`（SHA `e46458c39d5dc086569d1c61c4ccfa56cc8f37289eca214000fba20a1eeacf22`），5项均通过。只包含三个指数的先行装配会漏掉共store ETF，资格查询按预期失败，从而证明闭包门实际生效。

## 实现与恢复验证

产品入口为`integrations/guanheng/qmt_history_batch.py`及`qmt_cache_snapshot.py`，提供：

- 清单校验、全行DAT审计、上市日起点和显式缺口窗口；
- 原请求持久化及同ID恢复；
- 下载前快照intent、完整孤儿副本恢复、部分副本恢复事务及移动前后重放；
- 来源范围/六字段修订比较和`source_range_reduced`阻断；
- 同根可恢复地冻结转换输入；冻结前将准备批次`RESULT.json`、逐证券状态和manifest逐SHA绑定，既支持早期内嵌状态收据，也支持当前状态引用收据；
- 原Helper转换、原Reader全量回读，并发布具名schema和全部输入/验证身份；
- 完整旧store闭包、旧股票保留、混合来源目录准备；
- 原统一HTTP和公开SDK资格查询。

当前专项和既有DAT/Importer回归覆盖未知结果、负量额、来源缩短、晚上市、闭包、旧股票、全部负值日期、完整/部分孤儿快照、恢复期间供应商文件换代、superseded移动事务重放、严格准备/冻结/转换收据绑定、文件截止时间/字节预算、导入收据成员不一致阻断、只读闭包冻结和显式剩余缺口重试。当前19项专项回归通过；连同DAT、分钟Importer和日线Importer共65项通过、5项按环境条件跳过。1,764只容量回归分别验证准备和审计：完整观察保留在逐证券文件，总收据均小于2 MiB。

第6轮独立源码复审绑定`qmt_history_batch.py` SHA `a7af4f4dec0003ed31e99e52d5463d51ce2ac8eb16232923aacc5a200ada970e`及`test_qmt_history_batch.py` SHA `7cbf5e9b74f37110e87101b244c2decb0b1e286f2f9ba3a1a72e8723fbad7907`，结论为无可复现P0/P1/P2/P3。复审逐项确认外部文件预算、转换前后冻结输入复核、同批字节解析/SHA和导入收据成员全集校验已闭合。`python -B scripts/project.py check`通过文档导航及skill manifest完整性检查；该检查按工具声明不覆盖应用构建、运行验收、UI或发布。

第四批转换和恢复收据写入后，再次执行批量模块、DAT、分钟Importer和日线Importer四组相关回归，结果为60项通过、5项按环境条件跳过；随后`python -B scripts/project.py check`再次通过。

## 运行过程与已解除阻塞

前四批各240项和六个替补探针已经完成。第四批240只证券产生243个有意准备窗口：237只各一个窗口，`159919.SZ`、`159995.SZ`、`510010.SH`各包含前缀和尾部两个严格不重叠窗口；243个请求ID均唯一，结果体SHA、请求身份、窗口参数和终态成功逐项一致。`COHORT-004-AUDIT.json` SHA为`73e6751d5807118c9c9b0db343d9a8432b429fc485d0a8031f46df4cce29b596`。generation-002 Journal共有987条且全部终态，在途0、剩余容量37；第四批受控进程退出码0、未强停、进程树归零、Reader已join、资源已关闭。逐证券保存计划、请求、快照、前后观察、修订和剩余窗口。WT实时采集仍由独立统一数据实例持有；下一批请求须先完成受控代际轮换。

第二批随后冻结并完成原生转换。`frozen-cohort002-001`绑定240只选择、准备结果和实际DAT；`converted-cohort002-001/RESULT.json` SHA为`01ecdbecf76526def6dcb643efb4f5020fef31209fdcae2ecf0ff0b008e8f5ab`。原生导入收据状态`passed`且包含240名成员，原Reader逐时间和六字段完整回读13,251,478行，`VERIFIED.json`登记`all_times_and_six_values_equal=true`。转换完成后再次核对240份冻结DAT及来源SHA全集，成功收据才发布。

早期第一批状态由收据门完善前的版本生成，235个有效状态缺少后来增加的`source_range_preserved`字段，正式冻结按预期阻断。没有改写早期证据；`cohort-001-readonly-final001`对剔除五个无数据指数并加入五个已验证替补后的240只最终集合重新执行全量只读审计，下载请求0、质量拒绝0、范围缩短0。`converted-cohort001-final001/RESULT.json` SHA为`f675e5419ad609a4334ab129d47037247ad9c36035bb78a72818ad9713f6af85`，原生收据240名成员全部通过，原Reader完整回读7,969,291行且时间和六字段全部一致。

第三批240个请求全部终态成功，质量拒绝0、范围缩短0，受控批次进程树完整回收。`converted-cohort003-001/RESULT.json` SHA为`1812008e45d86c961f9e9508e72887a04bde4815362af3eddf79630e142c0143`，原Reader完整回读14,048,111行且时间和六字段全部一致。前三批累计720只完成冻结、原生DSB导入和逐行回读。

第四批随后以2 GiB显式输入预算冻结240份实际DAT，选择、准备结果、逐证券状态和来源快照全部绑定。转换前后再次核对冻结DAT，240份冻结副本及当前QMT源SHA全集一致。`converted-cohort004-001/RESULT.json` SHA为`2d7a827e765570de64d2357d1f51d20cc391a04418977bab2adee4f0edd8dfc9`，原生导入收据包含240名成员，价格区间不一致0；原Reader完整回读13,736,846行，验证收据SHA为`82970ca9d5a8aafa14a744138ee2be6a3ffffc35fe3434a45955a305c90ac920`，时间和六字段全部一致。

旧目录闭包额外识别45只成员并以只读方式准备，`store-closure-prepare001`下载请求0、45项全部合格。`converted-store-closure001/RESULT.json` SHA为`681a198007ec943fb17ce15b6bd7ca96d6dbb16d7a706439c8ea9e0ea4d791bf`，原生导入收据包含45名成员，原Reader完整回读7,836,726行且时间和六字段全部一致；验证收据SHA为`fbcff3d916dea21f4de614a7143a3c7ead9e19be051366551580b4ad0ec36bef`。最终装配仍须同时包含后续批次中属于原store的成员，提前只装配前三批与这45项会被闭包门阻断。

`CONVERSION-PROGRESS-002.json`绑定前四个主批次、旧目录闭包共五份转换结果和五份原Reader验证收据，SHA为`aaa3b7456b9eed580695e80898e730639112d5488fd5778e9457ec9ad69bc94d`。当前1,005只证券代码互不重复，累计56,842,452行，五份`all_times_and_six_values_equal`均为true；状态仍为`in_progress`，剩余005至008批。

`PARTITION-VALIDATION.json`重新按当前文件验证最终清单和批次划分，SHA为`d74da9eb05d749e3b83ca48055835e92a04757295d377c5551176db6d81091bb`。八批数量依次为240、240、240、240、240、240、240、84，合集恰为1,764项且无重复；45只旧store闭包与主清单不相交；1,809项导入清单恰为主清单加闭包。

`ASSEMBLY-EXPECTATION.json`从当前旧目录和最终导入清单重新计算装配不变量，SHA为`ad045b337ecc70c8e9d7c87b6c3082333a18bb165a4853a32b8a5a3fd1c1d295`。旧目录5,341项、导入1,809项，其中67项重合、1,742项新增，最终目录应有7,083项。导入触及5个旧store、共67个旧成员；导入清单包含这67项全集，闭包缺失数0。

第三批后按WT统一运行方的安全交接门暂停新请求。`HPR-HANDOFF-001.json`登记Journal 743条全部终态、未知/在途0，原owner正常关闭结果为退出码0、进程树归零、资源回收完成；pair、Journal和QMT策略保持原身份。新WT三组件复用同一pair/Journal启动，Host、历史和采集状态均为`ready`。第一次交接后只读检查的新请求在短轮询内返回pending，随后严格使用同一请求ID GET恢复为终态；实际源区间返回14:56、14:57、14:58、15:00四根，原数据缺14:59，未补造分钟。`HPR-RESUME-VERIFIED-001.json` SHA为`46cd838ff9f6129533bb9d7cbcd6e09a71150bfb6b6653b850c68ae2525ac517`，同时证明交接前原请求GET结果字节一致、Journal 744条全部终态。第四批首个请求已在新Host实例上终态成功，未更换pair、Journal或原请求身份。

第四批后generation-002实际达到987条且全部终态，剩余37条不足以容纳下一批。`HPR-ROTATION-HANDOFF-001.json` SHA为`7515a824724437f6195219a1d61214f94e03697abddf4bcc2f8ac1300fcc7124`，绑定第四批审计、旧运行身份、Journal identity、QMT实际策略、回滚原件及generation-003新配对。旧统一WT随后通过原control正常停止，`closed.json`证明三组件完整关闭且四个原PID退出。执行到QMT单策略停启门时，computer-use清单连续只暴露浏览器，未暴露仍在响应的国信原生窗口；因此未改写QMT策略、未启动generation-003，也未绕过可见停启门。为保护既有历史查询和采集，使用同一generation-002配置、Journal和数据根，以新control身份恢复三组件ready；恢复后Journal仍为987条全部终态且无新请求。`HPR-ROTATION-DEFERRED-001.json` SHA为`4b5d77ffde79b198e89bf2bfcfa33a81d30a77bd6c632f058d29cf5725b60af9`。当前owner PID为45216，Host/历史/采集PID分别为28008、55392、66224；QMT策略仍为generation-002 SHA `2d94a5ac6b8c10d051bb7d7e0989f2fbeedc7c7b2f985b092d77f0ce2e6e2a62`。

原生窗口控制缺失随后连续三个目标轮次复现：系统进程仍显示国信窗口句柄14422594且客户端响应，Computer Use清单持续返回`apps=[]`，无法精确定位、停止并可见确认唯一的`GH_WT_MEMORY_VERIFY`策略。`HPR-ROTATION-BLOCKED-001.json` SHA为`c7e28c5a07c958cd2b13c0a3d3e3df89d532ee5766fabdd771aff4e6ab598b82`，绑定当前可恢复状态。恢复实例继续ready、Journal 987条全部终态、QMT策略文件保持旧SHA、新代运行未启动、下单及撤单为0。继续动作需要在QMT中只停止`GH_WT_MEMORY_VERIFY`并保留其他策略；随后可原子安装generation-003，核SHA，再启动同一策略和新WT运行。

上述原生窗口控制缺失随后由统一运行方解除。实际旧实例按原control正常关闭，generation-003策略原子安装并核对SHA后重启同一策略；新WT统一实例通过续租验证，历史、Host和采集组件均保持ready。generation-002数据库冻结为987条全部终态且未迁移，generation-003最终813条全部终态、在途0；整个批次准备和验收没有下单、撤单或账户变更。

## 最终交付

八个主批次依次完成240、240、240、240、240、240、240、84项准备、冻结、原生转换和全量回读。连同45项旧store闭包，本次转换共1,809个唯一证券、98,927,423根一分钟记录；所有批次的`VERIFIED.json`均为`all_times_and_six_values_equal=true`。最终转换进度收据为`build/qmt-etf-history-001/CONVERSION-PROGRESS-006.json`，SHA为`4913456077223bf14ab6e464e6aa1a4bc15c145102f4c7dea03b5e60c3bd4123`。

ETF交付共1,714只、88,218,201根。391只从`max(2021-11-01, QMT ETF open_day)`对应交易日开始有记录，1,323只存在实际首日更晚的来源受限前缀缺口；观察区间内部完整性继续为`unknown`。65只与旧目录重叠的ETF逐只比较后，没有发现旧目录首分钟早于新冻结源，装配未缩短旧ETF历史。逐只机器正文为`build/qmt-etf-history-001/ETF-FINAL-COVERAGE.json`，SHA为`515ff54002944b37bd4e2757daeb1177a6b3fae7b5b018796c847288d895f410`；中文汇总见[ETF最终覆盖](2026-10-30-qmt-etf-final-coverage.md)。

50项指数共2,872,496根。QMT为全部50项返回相同`open_day=19901219`，该字段是市场级默认值，未作为指数发布日期。官方资料确认中证2000、科创100、科创200、科创综指在2021-11-01后发布，分别按2023-08-11、2023-08-07、2024-08-20、2025-01-20起算；其余46项从2021-11-01起算。83份既有本地目录证据均未提供更早记录，原历史准备请求从有效目标起点发起并全部终态成功，最终DAT仍从更晚日期开始，因此50项均登记来源受限前缀缺口。逐只机器正文为`build/qmt-etf-history-001/INDEX-50-FINAL-COVERAGE.json`，SHA为`ac743c574f3029eca87249d4ce77377dff4e040f636d0a856ddb622b3094362d`；代码、名称、选择分组、有效起点、实际首末分钟和条数见[50指数最终覆盖](2026-10-30-qmt-index-50-final-coverage.md)。

最终目录以旧目录5,341项和本次1,809项装配：67项重合、1,742项新增，结果为7,083项且代码唯一。5,274项未替换旧证券的路径、收据、条数、首末时间和文件SHA逐项保持一致；67项替换条目逐项等于新转换结果。最终目录共1,481,191,964根，目录SHA为`81e04fe4fcd3e070c68109c4d255c3f1858df6bbe2eb94b2216b9eed61b8febb`；装配审计`FINAL-ASSEMBLY-AUDIT.json` SHA为`ea57516bd414482efbbdd8f9512551a8e1a850c3eecab68877ab21361842d4a3`。

`catalog-final001`为7,083项生成10个来源分组、340个store的统一只读配置，配置SHA为`ec6f95839460122526b9f10e724c470698e1b37d7f750c7e0045f34472ee1b8c`。首轮资格查询沿用了10月28日尾部基线，`510010.SH`和`510300.SH`已更新到10月29日，因此严格哈希门拒绝旧基线。最终目录原生直读生成新固定基线后，`qualify-final002`通过新ETF、新指数、旧ETF和旧股票5项公开查询；临时HTTP服务关闭、查询线程回收，结果SHA为`e010ccb3e2eca3ebb587845d369d324bd3a6c5d21c18a03867ff882427385649`。
