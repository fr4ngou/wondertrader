# 2026-10-22 QMT 缓存读取与分钟量额精度

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

当前来源约束（2026-10-22用户最新决定）：仅使用QMT数据继续真实来源验证，等待其已下载历史数据进入验收；文末TDX对照仅保留研究记录，暂停引用，不用于当前缺失、精度或覆盖判定。

## 后继：已验证共享内存full-tick原件静态核对

对另一对话已验证的`market.full_tick`收据仅作静态读取，原件SHA为`77e58953746404aa85c0f6d50c54922517fecd63e8a34952083fe784fb60a692`，未访问Host、终端HTTP或SDK。单个510300.SH样本的volume和pvolume均为整数，pvolume等于100×volume再加12；以amount和当日low/high检验，100×volume及pvolume均落在区间，原volume尺度不成立。这是该分笔原件的关系观察，不能据此确定所有证券或历史分钟的精确股数、舍入或成交分桶。

数值time按epoch毫秒解释为上海`2026-10-22T16:29:13.083000+08:00`，同一原件timetag文本为`20261022 16:29:13.83`。文本小数位格式未另授精度语义；新C++映射读取明确整数毫秒字段，不能据常规ISO小数格式擅自改写为830毫秒。

[官方内置Python文档](https://dict.thinktrader.net/innerApi/data_function.html)明确full_tick提供最新分笔，不能取历史分笔或用于回测。[官方股票字典](https://dict.thinktrader.net/dictionary/stock.html)把tick volume记为手，并把pvolume解释为未作股手转换的原始量且标为不推荐；[云策略文档](https://knowledge.thinktrader.net/docs/cloud/data_function.html)另有对应说明。产品、接口、终端版本及周期分别核对，网页描述不直接授当前安装版本的分钟精度资格。

可复现脚本、字段类型与限定结论在静态审计（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-full-tick-source-001/result.json`），原件路径和摘要由同目录manifest绑定。本轮保留原量额与既有profile，不自动改用pvolume或新增默认100倍；真实来源映射和历史覆盖继续独立验收。

类型：来源契约核查与只读运行观察。状态：DevelopmentObservation，覆盖保持 Unknown；终端版本已确认，分钟成交量精度待确认。本文补充此前[来源契约观察](2026-10-21-qmt-minute-source-contract.md)，不回写历史结果。

## 已确认事实

运行中的国信 iQuant 为 `1.2.26.150`，构建时间 `2026-06-10 15:28:20`、revision `636290`。18010 的监听进程对应 `D:/software/guoxin/bin.x64/XtItClient.exe`，加载 Python 3.6.8。终端版本、行情 DLL 版本与 ContextInfo 接口契约分别登记，不能互相代替。Gateway 的 deployment_commit 仍为空，当前可见源码与运行脚本的精确身份尚未建立。

通过现有受管 HTTP 操作，单证券 `688076.SH` 的 2026-10-21 09:31–09:33 三根已闭合分钟线可读。`market.market_data_ex` 与 `market.local_data` 按原 epoch 时间键比较，OHLC、volume、amount 数值逐项一致。两接口可能共用缓存，这项对照没有取得独立来源资格。操作未下载、订阅、恢复、修改账户或交易。

当前 Agent/Bridge 转换链及安装自带的公开 ContextInfo 包装代码，均未发现成交量 floor、round、int 或除以 100；离线编码可保留合成的 23.53。当前代码核查与版本识别各有摘要，不能据此推断终端原生实现的舍入规则。

## 量额边界

09:32 的 OHLC 均为 28.28，原 volume 为 23、amount 为 66543。如果同时假设 amount 为元、量额与 OHLC 覆盖同一组成交、volume × 100 为精确股数，所得均价为 28.931739，超过 high。09:33 同样违反这一联合假设。因此，现证据不足以把换算结果标为精确股数，也不足以确定发生了整手截断。

原始 volume/amount 继续保留。基于既有手→股 profile 的数值，只具有该 profile 的开发换算资格；既有 428 行回读证明字段按 profile 一致，不证明精确成交股数。成交均价、换手率及依赖精确量额关系的策略还需来源契约。禁止按成交额反算并补写“真实成交量”。OHLC、时间、存储回读和覆盖范围按各自证据评价。

[内置 Python 行情文档](https://dict.thinktrader.net/innerApi/data_function.html)及安装随附文档未给出该终端版本 1m 成交量的单位、精度、舍入和共同成交集合保证。[官方云策略文档](https://knowledge.thinktrader.net/docs/cloud/data_function.html)的单位说明属于另一产品文档，不能直接转授当前内置终端资格。访问日期为 2026-10-22。

## 复核材料与下一步

独占材料保存在 `build/native/capability-audit/`：

- `qmt-m1-current-contract/20261021T172409Z-090debf9/`：源码契约、health 前后、单次三行缓存读取及请求身份。
- `qmt-volume-audit/20261021T173451Z-7a6a3898/`：两个公开接口逐字段对照、联合假设检查、转换链与官方文档来源。
- `qmt-version-audit/20261021T174157Z-7d710557/`：端口→进程→可执行文件、版本元数据、公开包装代码及文件摘要。

下一项证据应明确该版本的分钟单位、精度及成交集合，或取得同分钟公开高精度来源的受控对照。版本事实已自行查明；当前没有请求用户提供样本或版本，也未联系供应方。已有缓存读取、WT 原生存储/Reader 与其他字段验证继续推进，整体适配目标保持 active；生产资格未授予。

## 后继：428行直接HTTP正文复核

2026-10-22北京时间07:26完成一次有界真实读取。沿原HTTPBrokerTransport签名和BrokerClient提交，health前后及capabilities各一次，market.market_data_ex一次；四个响应均200，市场POST在2.545秒即时返回终态，无轮询、重提、下载、订阅、账户操作或终端变更。请求原归档日2026-10-20 09:30–15:00，period=1m、count=300、dividend_type=none、fill_data=false、subscribe=false。

300308.SZ取得239行，688076.SH取得189行，510300.SH返回空数组。原Agent HTTP entity body为48,405字节，SHA256 `c3df2b16cf3bfd6c802b88f858dfcf27c8d687e0050bac8d8abcc87038b7b1fb`。采集点在BrokerClient JSON/DTO解析之前；HTTP分块和压缩解码仍由httpx完成，此材料不包含TCP原字节或原DataFrame。两股票428行的顺序、时间、OHLC、volume、amount与旧归档逐值相等；本次原正文data与DTO投影也全等。全部volume是浮点JSON token且数值为整数，不能据此断言native DataFrame dtype。

在金额为元、价格为元/股且覆盖同组成交的联合假设下，对425根正量记录用`low × V ≤ amount ≤ high × V`检验：原V尺度0根通过；100V尺度295根严格通过，增加金额敏感性容差后296根通过，仍129根偏离（128高于上界、1低于下界）。另有3根volume=0、amount>0。±99股敏感性可包容全部记录，但它不证明舍入算法或精确股数。两个股票返回窗口均有缺口，请求覆盖完整时段不授完整日、停牌或全市场覆盖资格。

直接HTTP正文已复现偏离，当前DTO及WT消费之前已有这些数值；这缩小了待查范围，仍缺运行中Agent加载代码身份、原DataFrame值/dtype及该版本供应商分钟量额单位、精度和分桶。health前后来源身份稳定，deployment_commit仍null；本地Git HEAD只证明客户端源码身份。100倍profile继续保持未核准精确量资格，原DSB、sidecar及历史证据均保留，不按amount反算补写成交量。

复核材料：离线逐行及来源谱系（外部历史/待归仓路径：`../../build/native/qmt-minute-unit-audit/research-001/research.md`）、直接HTTP复核（外部历史/待归仓路径：`../../build/native/qmt-minute-unit-audit/live-001/research.md`）、实际收据（外部历史/待归仓路径：`../../build/native/qmt-minute-unit-audit/live-001/receipt.json`）及文件清单（外部历史/待归仓路径：`../../build/native/qmt-minute-unit-audit/live-001/manifest.json`）。根任务已独立回读清单的15个文件及5个分析输入，长度及SHA全部相符；以原正文Decimal算术独立重算（外部历史/待归仓路径：`../../build/native/qmt-minute-unit-audit/root-verification-001/result.json`），428/425/295/296/3及原正文/DTO/旧归档相等结论相符，无新增网络请求。研究报告SHA `003df98b29af6182f33c95ccc5bd9dffa4da63b7f8d37f232f99bb6646be9a88`，收据SHA `d062f19cafd16e607678e589152cd530716c1b300d5cc8c5a27419cc287d94db`。实际命令、输入和逐行边界在上述独占目录，凭证/签名header及账户事实未保存。

## 后继：安装文档与公开离线入口

静态研究002（外部历史/待归仓路径：`../../build/native/qmt-minute-unit-audit/research-002/research.md`）新增安装自带PDF证据：`D:/software/guoxin/HTML/国信iQuant策略交易平台_Python_API_说明文档.pdf`共213页，物理第208页K线表列volume为int、OHLC/amount为float；该表仍没有定义手/股、金额币种、二进制宽度、舍入或共同成交集合。PDF SHA `d94ead8f5575596606f5e0a1a68be143535c8132f82cdd2e3041f552f735aaad`，生成元数据为2024-09-12，不作为当前终端API兼容声明。网上内置表、安装表及HTTP token的表示层次分别保留，不能据int推断整手截断。

安装ContextInfo公开包装直接取原生get_market_data2后构造DataFrame；本次已静态回读，该段没有额外量单位换算。安装xtquant.get_local_data函数体仅return None；既有归档官方SDK的data_dir/server=False路径仍需get_client连接，部分导入还有初始化/版本检查副作用。因此没有取得可直接用于当前DAT、无需连接的公开纯离线读取资格。先前三行market.local_data对照已有证据，继续重复同缓存读取不能补全精度契约。

该研究只读20项本地文档/源码与既有归档，读取前后相同，零新增现场请求，未导入QMT/SDK。报告SHA `024ec141a7c20775ae12ce66e006a269fa36716e6d8457b5f8dd83d3c720a571`。下一最小缺口是该版本供应商分钟量额定义，或以后在原策略线程返回点、原编码之前提供经审查的dtype/精确原值及加载身份诊断；当前公开协议没有这些元数据。该诊断尚未设计实施，既有数据、代码与运行实例保持。


## 后继：同日通达信缓存对照

[7月20日双客户端观察](2026-10-22-qmt-tdx-minute-comparison.md)新增454条QMT真实分钟与TDX逐时间键对照：453条OHLC在0.0001元内一致，127条TDX量比QMT原量×100多100，其余相等；双方量值仍缺精确逐股资格。QMT省略的26个股票时间键在TDX中为零量零额，收盘OHLC另有一处来源差异。原数据不变，不能据此将所有日历空位判为缺失或将辅助源量补写为精确主源量。

## QMT公开文档后继复核（通达信对照暂停后）

2026-10-22再次核对迅投[内置Python行情函数](https://knowledge.thinktrader.net/docs/python/data_function.html)：`subscribe=False`用于读取本地已有数据；分钟字段表将volume列为float，仍未定义该字段的手/股或二进制精度。[内置数据结构](https://dict.thinktrader.net/innerApi/data_structure.html)分别列出Tick与Bar，Tick的单位说明不直接授予Bar精度资格。

新版[云策略换手率示例](https://knowledge.thinktrader.net/docs/cloud/code_examples.html)明确其日K示例使用手并乘100换算。该页面属于云策略、示例周期为1d；当前国信内置Python的1m来源仍需按自身版本契约核实，保持原值，继续不根据比例或其他周期推定精确股数。本次只读官方网页，现场请求、导入、订阅和下载均为零；通达信材料继续暂停引用。
