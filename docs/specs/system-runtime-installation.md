# 系统候选装配与离线安装

类型：功能最终规格。状态：accepted。前缀：SRI。范围：[三会话交付计划](../migration/parallel-system-delivery.md)的统一安装能力；完整M3及实际启用分别验收。

## 目标、现有能力与职责

操作员从同一份候选包安装观衡、独立QMT Host及其明确选择的原生运行组件，从已安装入口启动业务。后续版本安装到新目录，已有运行目录、配置和数据继续保留。观衡与原生组件继续独立构建、版本和发布，统一候选记录其组合身份。

复用[原生能力目录](../development/wondertrader-capabilities.md)中的原Runner/插件、DataKit/Writer/Reader和原生文件存储。WT提供运行与数据能力；系统发行组合、Python角色环境和SPA安装由自有工具承担。复用现有[行情候选](market-runtime-candidate.md)、普通角色安装器及其wheel/锁/RECORD校验；部署遵循[原生部署手册](../runbooks/native-deployment.md)。本功能不改变WT源码、分钟算法、策略/订单状态或账户权限。

安装期只使用明确输入的制品和本机外部工具。WT独立运行入口拥有Host、行情和执行子进程生命周期；观衡独立部署并只读消费WT接口，见[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)。安装器负责文件及环境准备，不拥有运行实例。业务数据、终端缓存、账户资料和配对秘密由WT实例管理，观衡展示偏好由自身实例管理。

## 调用链与输入输出

1. 构建端给出普通安装角色的installation.json及可信摘要、已验行情候选根及manifest摘要、SPA文件清单，以及可选原生组件的文件清单和公开入口。组件选择来自输入配置，工具不按版本文字或目录扫描猜测当前版本。
2. 装配器核验角色wheel/精确hash锁及原组件，复制可分发文件、许可证与安装工具闭包，输出统一逐文件清单和ZIP。App/Host分别保留自己的角色环境要求，原生行情保持自身清单。
3. 接收端按可信外部摘要解压验证，从包内wheelhouse/锁在全新目标目录普通离线安装App/Host；不重新构建产品源码。Python3.12 x64、pip及uv是显式工具前置，实际身份写入收据。
4. 所有角色安装及原生/静态资源核验完成后，最后发布安装收据。解析入口返回App解释器、Host解释器、原生组件公开路径及SPA目录。实际启动沿原App/组件入口及外部实例配置进行。

统一清单使用独立schema，记录development属性、各角色版本/原manifest和锁摘要、原生组件身份、静态文件身份、工具闭包与全部受管文件摘要。安装收据使用独立schema，绑定候选摘要、目标目录、工具、角色普通安装收据及解析路径。路径在包内保存为相对路径，安装收据记录实际绝对位置。业务状态及活动版本指针不由安装收据拥有。

公共工具提供create、verify、extract、install、resolve操作。进程命令复用现有受管run接口；Python库安装入口接受调用方run和同一有限总截止，各子命令使用剩余预算。验收的后台作业在创建时归属隐藏Job，保留命令日志与实际整树关闭结果。代码组织和参数细节在本模块开发时记录唯一公开接口，原普通安装API保持兼容。

## 公共接口与制品模型

WT独立发行后继沿[WRI](independent-wt-runtime.md)：普通角色增加`wt`（来源`apps/wt_runtime`），角色按`app,host,wt`稳定顺序选取非空子集，默认仍为原`app,host`。`host,wt`或单独`wt`安装不要求观衡；本地依赖选择、普通wheel安装、pip check及RECORD同一实现，WT角色拒绝把`guanheng-app`带入依赖闭包。角色实际模块身份核`guanheng_wt_runtime`及其`runtime`；旧app/host的模块及收据语义保持。

新增输入`guanheng.system-runtime-inputs.v2`和包`guanheng.system-runtime.v2`，字段沿v1；`static=null`表示不携带观衡SPA，原v1继续要求原静态清单。v2解析结果为`guanheng.system-paths.v2`，无SPA时`spa=null`；wt角色入口为`-I -B -m guanheng_wt_runtime`。带有app的包仍只记录观衡可用入口，不授予其WT子进程管理权。安装器不自动启动任一角色。

入口为`scripts/native_support/system_runtime.py`和`scripts/system-runtime.py`。create读取唯一`guanheng.system-runtime-inputs.v1`输入：`development=true`、`roles={installation,sha256}`、`market={root,sha256}`、`static={root,files}`、`additional_components=[{name,root,files,entries}]`。目录为显式绝对路径，files为相对POSIX路径到原字节SHA256；entries由组件所有者声明。角色版本、extras和策略闭包取原installation/wheel/锁。

`create(inputs, inputs_sha256, output, archive)`装配候选；`verify(root, manifest_sha256)`核SYSTEM-RUNTIME.json及精确文件集合；`extract(archive, archive_sha256, manifest_sha256, output)`先核ZIP路径/展开额度再搬迁；`install(root, manifest_sha256, target, python, uv, run, *, deadline)`从预建制品离线安装；`resolve(root, installation_sha256)`核SYSTEM-INSTALLATION.json、候选及角色RECORD后返回入口。失败抛异常并保留现场；已有目标拒绝，成功收据最后发布。

普通角色安装器新增stage_artifacts、verify_artifacts和install_artifacts；其角色制品schema为qar.role-artifacts.v1，包含原installation、wheel/精确锁/local-projects及原QA/runtime-generator；安装结果schema为qar.artifact-runtime-install.v1。复用原wheel/METADATA、pip check、RECORD与模块owner算法，prepare/source_inputs保持兼容。

各角色独立发行时，构建端可用`scripts/compose-role-artifacts.py`组合已验的`qar.role-artifacts.v1`。输入`qar.role-artifact-selection.v1`包含按`app,host,wt`顺序选择的`roles={角色:{root,sha256}}`及显式`runtime_tools={root,sha256}`；每项指向原角色制品根和可信manifest摘要。输出仍为`qar.role-artifacts.v1`，各角色wheel、精确锁、extras和local-projects保持原字节；工具来源明确选择，原manifest及来源收据保存在`origins/`。组合来源使用`qar.role-artifact-composition.v1`，明确记录各发行身份，不宣称来自一次共同构建。工具不重建、不安装和不启动业务。

系统create的`roles`输入同时接受显式`{artifacts,sha256}`，直接复制并验证上述预建角色集合；原`{installation,sha256}`及其默认行为保持。其后ZIP、解压、普通离线安装、pip check、RECORD及resolve沿同一实现。验收须选择来自独立发行的App和WT，保留其不同版本依赖，在同一系统包中普通离线安装后通过公开入口确认实际版本与独立环境；原installation输入的回归仍须通过。来源身份错配、缺少所选角色及来源/输出重叠应在复制前失败，失败保留新现场，不覆盖旧制品。

系统候选上限为20000文件、单文件256MiB、总1GiB、40000枚举项，ZIP中央目录8MiB、配置4MiB；覆盖当前预建依赖、32MiB行情包及SPA。超限失败，后继容量扩展按新规格和输入验收。角色沿原20000文件/256MiB边界；每次制品安装至多16命令，输入哈希之后、紧邻run取得原剩余D；后置校验和pending完整收据也消费原D，最后发布成功名。全部输出与来源及彼此互不包含，在mkdir前拒绝重叠；新根规范化后贯穿角色和安装收据身份。文件准备同受创建期外层Job总预算约束。中文步骤见[系统安装手册](../runbooks/system-installation.md)。

## 要求与验收

| ID | 要求 | 实际验收 |
|---|---|---|
| SRI-R1 | 固定制品组成统一包，App/Host依赖及extra选择沿原声明和精确锁，唯一正式策略保持1.1.2 | 当前已验角色制品装配，包内无退役策略wheel，原组件/锁/许可证逐项对应 |
| SRI-R2 | ZIP可在新根解压，从包内wheel和工具安装到另一个新目录 | 原仓产品源码不参与、无网络安装，pip check/RECORD/模块owner通过 |
| SRI-R3 | App与Host分别安装，原生组件/SPA保留原字节与组合身份，入口可解析 | 新根解释器与公开路径存在并核摘要；附加组件按声明组合，不以同版本代替同内容 |
| SRI-R4 | 已安装App实际读取已有真实分钟和正式ETF日线 | 原历史组件→同SDK→App HTTP，日期/OHLCV一致，其他未配置能力不阻断历史读取；原页面接收资格由C组合验证 |
| SRI-R5 | 同一包能在第二个新目录再次安装，失败保留现场，已有实例与数据保持 | 两个不同根安装/启动/停止，原包只读；失败不生成成功收据，不替换活动版本或删除数据 |
| SRI-R6 | 输入身份、文件路径和工具异常有明确失败结果，命令有界且关闭可核实 | 主路径完成后覆盖摘要错配、缺wheel/锁、安装命令失败/超时、目标已存在、包路径越界；正常与失败均回收所属资源 |
| SRI-R7 | 中文操作材料说明安装、入口、独立发布、更新和回退的实际边界 | 按包内材料完成离线安装；更新并排安装、实际切换/回退沿实例授权和状态兼容另验 |

先完成装配→ZIP搬迁→离线安装→实际App历史链，再验证失败、独立审查及交付。只读历史链可先验；完整M3仍需B最终执行/账户组件、C真实浏览器操作及真实QMT组合，不能由本模块的安装结果替代。

## 兼容、风险与后继

构建安装与离线制品安装均显式使用`uv pip install --link-mode copy`，角色代码与安装缓存保持独立文件实体。缓存重用继续由uv管理；产品文件的原摘要及Host单链接核验保持，调用方无需设置环境变量才能得到可运行安装。

普通安装器的原prepare/source_inputs调用保持，新增制品安装能力复用同一角色校验。MRC原清单/解析保持；包内已经安装的历史HPR环境若依赖外部Python锚点，须如实登记，其重新绑定资格单独验证。额外组件入口仅来自其声明，安装器不自动启动账户或执行通道。

当前执行组件仍由B完成正式入口和退出验收，后续将其固定交付作为显式输入组成系统候选。C的新App及SPA按冻结版本选择；并行开发的新字节需要新的候选身份。正式发行继续从干净集成提交和受控标签构建，开发包保留development性质。生产切换和真实委托/撤单按用户单独授权，现有采集和QMT运行状态保持。
