# 系统候选的原生账户组件闭包

类型：开发安装证据。日期：2026-10-30。状态：安装闭包已验证，真实只读组合准备继续。规格：[系统安装](../specs/system-runtime-installation.md)、[账户发布](../migration/native-account-publication-proposal.md)。

## 根因与范围

`build/root-source-wait-001/release002`的公开解析只包含execution、qmt_data_v2两个附加组件，包内没有GuanhengAccountScan.exe和TraderQMTReadOnly.dll。原七组件SDK主链使用了另行提供的已验账户工具；其运行证据保留实际范围，release002的离线安装结果只证明包内声明的组件，完整账户运行闭包尚未成立。

根因在SRI装配输入：遗漏已交付的native_account附加组件。原SRI已支持完整显式组件声明，本轮沿原create、extract、install和resolve接口补齐输入，不修改产品行为或WT框架。

## 固定输入与验收

后继根为`build/root-source-wait-001/release003`，原release002保持。角色仍使用A8安装manifest `a4ae8ac41236fc74de48dc8b714067eef16fab2d8c12396c058c51c0b720a250`，原行情和execution/qmt_data_v2声明保持。

native_account取自已接收的`build/wt-trade-system-candidate-004/installed001/payload`原组件清单，逐项核13文件及精确集合。Scan SHA `5dae69603377ef7d88dde3e2d82dbc4e111c5b3002b10a456c07c528a700ad44`，Trader SHA `27e92a99437771432e5d0af97731dc80b94b445a5a47e1fc70bf9a696a095c42`，许可证、原组件INSTALLATION和编译来源记录一并保留。机器MSVC/UCRT仍是该组件声明的外部前置条件。

`INPUT-AUTHORITY.json`记录原输入及制品清单身份，新INPUTS SHA `b7e8d07a4de13bbab2e4a6c91bfac8e02146d5913d9ea09cf2007a4491b077d0`。验收顺序：新ZIP及新根搬迁→离线安装→独立resolve→异根-I实际导入→包内六组件只读材料生成及check-only。安装、解析采用各自有限QA预算；业务请求和关闭截止保持原值。

当前未启动新QMT来源、账户扫描或交易，不改活动实例、原策略和生产指针；真实只读主链及完整交易恢复继续独立验收。

## 后继实际结果

原create/extract完成1403成员ZIP及新根搬迁，110.329秒exit0。ZIP SHA `6a58a653f49ef27321c65fbd2c75037124fa44f77c831544f60ec00684151cfb`，manifest SHA `5b688760a064e0b4902ef8b2b2228b89cc508638f51cb52e054335a7018d0566`。与release002原manifest逐项比较，原全部文件相同，只增加native_account的13份文件，roles/market及原两个附加组件保持。

由搬迁目录包内原CLI在另一个新根`release003/installed001`离线安装host/wt，197.515秒exit0；SYSTEM-INSTALLATION SHA `057752dbae580caf3ba9769f582fd318b8e27069db944a291e4ee917cc60ff81`。随后独立原resolve完成全角色/RECORD和组件校验，44.547秒exit0，公开解析实际返回execution、qmt_data_v2和native_account，两个账户入口的路径及SHA均绑定本次安装根。

异根`-I`实际使用新WT解释器导入A8及source-wait模块，0.296秒exit0，模块均在新安装内，未导入观衡、未构造owner或发起业务请求。各阶段由隐藏native.run Job及有限QA预算执行；此处分别验证装配、安装和解析，原release002的300秒合并驱动失败结论保持。

根沿`finalize.py`核对四阶段收据、旧文件原值及13新增文件，将限定接收写入`ROOT-PACKAGE-ACCEPTANCE-003.json`。本轮产品代码和WT框架修改0，原A8及账户组件的源码/二进制身份保持，复用对应既有审查；新结果只授安装组件闭包。完整六组件只读准备已交原owner沿同包入口继续，真实QMT业务及整套恢复仍待验。

## 同包六组件准备与现场边界

后继`build/wt-final-real-read-001/ROOT-READY-001.json` SHA `2b03639a3516bd8b7bd656e9245ed6836ee386e355d6c7698220f776d3c90c70`已固定新配对、正式正文、包内账户/行情/历史组件及独立a45入口。原隐藏check-only exit0，owner_started=false、source_queries=0；真实配置不含execution，双端writes=false。

根沿`release003/intake.py`只读核对9372固定输入及packet全部9397文件的当前SHA，全部相同；原Probe SHA仍为`35d020…9546ae`。接收范围与零业务状态保存为`ROOT-REAL-PREPARATION-INTAKE-001.json`；现场协调器未启动，这份材料只授准备及预检。

本轮重新定位唯一QMT窗口并成功读取状态，激活返回`failed to activate captured window`；刷新窗口绑定后的单次恢复仍同错。依Computer Use指引停止重复输入，未替换正文、未启动或停止策略，未保存含其他窗口的截图。去敏结果在`FIELD-AVAILABILITY-001.json`。实际只读组合等待可靠的QMT界面控制；既有来源和数据实例保持原状，完整目标继续active。

### 准备001的后继资格更正

独立审查发现1项P2：准备001的history-source外层native_reader已指新包，`base.native_reader`仍指旧final002安装，且该旧DLL没有进入9372固定清单。根沿包内CollectedSourceMarket第66行核实实际会构造`NativeSourceMarket(config['base'])`，并核对两份Reader路径及相同SHA，确认该问题。原根核收证明的是所列文件哈希一致，缺少实际嵌套依赖路径检查；准备001因此不授现场使用，原packet/收据保持，追加`PREPARATION-QUALIFICATION-002.json`说明。

修正由准备owner在独占`wt-final-real-read-002`生成：同时绑定外层和base Reader到同一release003安装，重新配对、冻结、check-only；产品和WT框架保持。后继根核验须沿实际历史配置检查每个native_reader均为包内公开history_reader，并出现在固定输入中。实机从未启动，原策略保持；release003包内账户组件安装资格继续成立。

002已完成：packet SHA `d45126f13acd8e095788420acb22b0dc3c754c8a2d95ce4df63c9d7a6e280bdc`，独立delta SHA `5b090b49122ffd70d42b9660e1161487dd17c4fafa63d3bf60a090f4e3484d47`关闭原P2，开放P0–P3为0。根沿实际WT配置→history descriptor→service→source追到两层Reader，两者同包且进入固定输入；9372运行输入及9392交付文件当前一致，见`ROOT-REAL-PREPARATION-INTAKE-002.json`。

### 实际数据选择后继

根使用002配置实际构造包内CollectedSourceMarket并读取历史，首个000001.SH请求没有返回Ok，finally已关闭Reader，进程exit1，失败日志及`HISTORY-FALLBACK-FAILURE-001.json`保留。按336份收据核对，该配置登记5347项，包含600000/510300分钟，未登记000001分钟；此前完整真实股票/ETF/指数链使用的`root-history-observer-005/source.json`有341份store声明。该差异属于验收配置的数据选择，Reader路径修正继续成立。

准备owner在独占003使用上述已验完整数据声明、同release003 Reader及原配对/关闭预算重新生成；002保留其较小历史范围。根继续以新准备实际读取三证券240分钟，并与原真实结果逐根核对；产品、解码及WT框架保持，真实QMT尚未启动。

003结果已取得：packet SHA `35a3e256929ce2c1d29056c18a89a9398b49c8465ba635a67c20ad8177f44453`，原隐藏check-only exit0/零owner零查询。根独立沿实际descriptor读取配置，核base与上述完整341-store数据声明逐字段一致；9387固定输入及9412准备文件当前SHA全部一致，见`ROOT-REAL-PREPARATION-INTAKE-003.json`。原001/002及各自收据范围保持。

根随后在新包Host解释器以003原history-source配置实际构造原CollectedSourceMarket，原采集目录没有DSB，因此三次请求走真实base历史读取。000001.SH、600000.SH、510300.SH各240分钟全部成功，与`root-history-observer-005`原真实SDK结果的bars逐根完全一致，尾部日期分别为2026-10-29、2026-10-27、2026-10-29；不将这些尾部声称为当日最新行情。finally关闭Reader、输入前后不变、子进程exit0，见`HISTORY-FALLBACK-002.json`及`history_read002.stdout`。该结果只授新包内原生历史直接读取，不替代HTTP、六组件实际QMT账户、页面或生产资格。

当前主线余项为完整真实QMT组合及整套恢复/最终策略报告集成。窗口激活阻塞保留，现场协调器、Probe和交易均未启动；新包与已导入数据的独立只读验证已完成。

003完整交付SHA `bc59debfd5c5f9fe6616bf22d19125e62901ae6f72ca57a470b87b664afc8dc9`、必要数据delta SHA `d28368e0f0f3c0888d676f5f2a78f893a771a6e254d7cef80e75001aa7808b37`已由根核实，独审无新发现。341份收据登记7083分钟证券及9日线证券/周期；登记、实际样本读取、历史覆盖质量和当前来源新鲜度分别表达，完整覆盖不由目录数量推定。
