# 系统候选离线安装

类型：运行手册。范围：development系统候选的装配、搬迁和并排安装；状态：已实现，具体运行资格按对应候选收据登记。功能规格为 [SRI](../specs/system-runtime-installation.md)。

## 前置与输入

使用 Windows x64 CPython3.12（具备pip）及显式uv可执行文件。Python和uv由接收机器管理；安装收据记录实际摘要。原行情包的HPR环境保留其声明的外部Python锚点，重新绑定另验。

构建端使用 `guanheng.system-runtime-inputs.v1` JSON：`development=true`；`roles`提供普通安装的`installation`绝对路径与`sha256`；`market`提供候选`root`与原manifest的`sha256`；`static`提供SPA的`root`及`files`相对路径→SHA256；`additional_components`为显式组件数组，每项包括`name`、`root`、`files`和`entries`（公开入口名→相对路径）。组件版本与发行集合取自原制品，不维护目录猜测或策略名单。

```text
python -B scripts/system-runtime.py create --inputs <固定JSON> --inputs-sha256 <SHA> --output <新候选目录> --archive <新ZIP>
python -B scripts/system-runtime.py verify --root <候选目录> --manifest-sha256 <SYSTEM-RUNTIME的SHA>
```

create提取预建wheel、精确hash锁、许可证与安装工具闭包。包内`tools/scripts/system-runtime.py`提供同一套公开操作。原角色安装manifest作为来源原件保留，其中历史绝对位置仅为来源证据；实际装配路径均由系统清单的相对目录解析。

## 独立发行角色的组合

观衡、通信Host与WT分别发行时，使用各自已验的`ROLE-ARTIFACTS.json`。构建端给出固定选择JSON：`schema=qar.role-artifact-selection.v1`，`roles`按`app,host,wt`顺序列出所需角色，每项为`{root,sha256}`；摘要指向该根的`ROLE-ARTIFACTS.json`。`runtime_tools`同样显式指定一份角色制品，提供普通安装收据生成工具。

```text
python -B scripts/compose-role-artifacts.py --inputs <角色选择JSON> --inputs-sha256 <SHA> --output <新角色制品根>
```

组合保留各角色自己的wheel、精确锁、extras和本地项目清单，因此观衡和WT可以使用各自发行绑定的依赖版本。`origins/`保留各原发行清单及来源收据；组合本身有独立来源类型，不表示所有角色曾经共同构建。此操作只整理制品。

将系统输入的`roles`写为`{artifacts:<新角色制品根>,sha256:<组合返回的manifest摘要>}`，随后使用同一套create、ZIP搬迁、离线install及resolve命令。原`{installation,sha256}`输入仍适用于共同构建的普通角色安装。来源身份或所选角色不符时停止并保留原制品；已有输出目录保持，重试使用新目录。

选择原生账户观察时，`additional_components`须包含账户组件的完整制品声明：`name=native_account`，`entries.scan=app/GuanhengAccountScan.exe`、`entries.trader=app/traders/TraderQMTReadOnly.dll`，`files`沿该组件的固定发布清单包含程序、插件、许可证和来源记录。安装后使用`resolve`返回的`components.native_account`接线；实际运行路径位于本次安装根。MSVC/UCRT等机器前置依赖仍按组件自己的`INSTALLATION.json`核对。

## 接收端操作

普通角色的构建安装和离线安装均由工具显式选择`--link-mode copy`，安装后的代码与uv缓存为独立文件；操作员沿原命令安装即可，无须额外设置链接模式。这样清理或复用缓存时，已安装角色保留自己的文件身份。

先通过受信渠道取得ZIP SHA256和SYSTEM-RUNTIME manifest SHA256。使用已信任的工具核ZIP并解压到新根；新根中的工具可继续安装：

```text
python -B scripts/system-runtime.py extract --archive <ZIP> --archive-sha256 <ZIP的SHA> --manifest-sha256 <manifest的SHA> --output <新解压根>
python -B <新解压根>/tools/scripts/system-runtime.py install --root <新解压根> --manifest-sha256 <manifest的SHA> --target <另一个新安装根> --python <CPython绝对路径> --uv <uv绝对路径> --deadline <调用方原单调时钟绝对截止>
python -B <新解压根>/tools/scripts/system-runtime.py resolve --root <新安装根> --installation-sha256 <安装命令返回的SHA>
```

`install`须由调用方在启动前纳入隐藏创建期Job，设置同一有限总截止、输出/内存上限并回收整树。命令执行复用native.run，安装库接受`run(argv, cwd, log, timeout)`与绝对`deadline`；子命令在摘要检查后按原剩余量派发。所有写目标与来源及其他写目标互不包含；成功收据经完整pending原件及原截止检查后最后发布。安装仅从包内wheel/锁普通离线安装所选角色，无产品源码重建或下载。失败保留新目录现场。

## 入口及实例边界

独立WT候选采用v2输入，原安装可选择`wt`或`host,wt`，`static`写为`null`，观衡服务另行安装。`resolve`只返回所选角色：单角色候选使用`roles.wt`；双角色候选还包含`roles.host`。WT从`roles.wt`公开模块入口和独立实例配置启动，观衡通过WT公开只读接口连接。v2无静态资源时`spa=null`。原v1及app/host候选继续可读取，其历史包中的App托管表述由[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)取代。

单WT角色承担Host运行环境时，其精确依赖须明确包含Host及Agent发行，配置绑定该环境的解释器和Agent目录。模块导入、配对生成和实际来源连接分别核验；安装成功只证明发行文件与环境身份。选择独立Host角色时使用该角色自己的公开解释器，两种组合的Host生命周期均归WT管理。

resolve验证候选、角色安装收据及RECORD所绑定文件，再返回所选角色解释器与模块参数、可选SPA目录、原行情公开入口和显式附加组件入口。启动观衡时可将非空SPA路径传入其`--static-directory`参数；WT拥有Host、历史、采集和执行进程，独立负责关闭流程，安装器只准备文件/环境。

实例配置、账户资料、业务数据、令牌及活动版本指针保留在实例边界。安装工具不启动QMT、执行或采集通道，不切换生产实例。历史只读资格、页面真实浏览器资格、完整M3和实际账户/交易授权分别登记。

## 更新、失败与回退

同一个候选可安装到第二个全新根；新版本同样并排安装。已有目标目录、摘要不符、路径越界、缺少wheel/锁、安装命令失败或超时均停止，不发布成功收据。保留原包、日志和失败目录供定位，后续重试使用另一个新根。

实际切换和回退按实例授权、状态兼容、关闭及数据连续性单独验收；安装成功只授予本轮制品和角色环境资格。development候选保持开发性质，正式发行沿干净集成提交和受控标签流程。
