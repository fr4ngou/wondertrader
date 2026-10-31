# 原生构建与制品工具链

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。所有者角色：构建与验证维护者。范围：SDK-independent 开发构建、测试与开发候选包，实际支持矩阵和通过结果见 CURRENT/证据。

## 入口与调用链

[native.py](../../scripts/native.py) → 工具链发现与固定依赖 → 独立 CMake（外部历史/待归仓路径：`../../cmake/native/CMakeLists.txt`） → 上游原生目标 → CTest/流水线测试 → install stage → [制品清单与 ZIP 校验](../../scripts/native_support/artifact.py) → 搬迁后冒烟与回放。

入口使用显式 profile。默认 `native` 沿通用目标与制品；`qmt-readonly-fixed` 由同一 owner 调用 [固定输入](../../scripts/native_support/qmt_readonly_fixed.py)、[阶段编排](../../scripts/native_support/qmt_readonly_flow.py)与[自有 CMake 子工程](../../cmake/native/qmt_readonly_fixed/CMakeLists.txt)。后者从固定 Git blob 和自有快照 fresh 编译原库、插件与宿主，生成普通插件开发包，验收边界见[最终规格](../specs/native-readonly-package.md)。两类配置/CMake缓存和制品资格分别绑定，跨 profile 复用构建缓存会失败。

依赖权威定义为 [native-dependencies.json](../../config/native-dependencies.json)，上游集成身份为 upstream-baseline.json（外部历史/待归仓路径：`../../config/upstream-baseline.json`）。构建逻辑不读取任务方案文件或账户配置。

## 状态与持久边界

生成目录保存依赖归档/源码、构建缓存、阶段日志、配置输入摘要、built-source 身份、CTest 报告、阶段 receipt 及开发包。独立 build 会重新 configure，覆盖上游 GLOB 源文件的增删；编译资格同时绑定 CMakeCache 与 bin/lib 输出。配置或编译输入改变时复验对应阶段；失败回执不能授予后续通过资格。

依赖归档固定 SHA-256，期望源码文件映射摘要同时固定在 lock，缓存 marker 不能改写期望内容。固定 `qmt-readonly-fixed` profile 每次通过同一依赖 owner 重算内容摘要；可变的文件大小、mtime和缓存 metadata不授予固定内容身份。默认 `native` 保留既有元数据缓存与显式 `--audit-deps` 全量内容校验选项。Boost 仅裁剪不参与本 profile 的文档/例子/测试目录，参与构建文件仍按固定归档内容验证。

开发包使用唯一目录及名称，逐文件清单与外部包摘要分别核验，运行状态和私人配置独立。清单明确 `release_type=development`，正式发布仍需适用的源码、标签、审查与环境资格。

固定 profile 另外记录实际头依赖、已生成对象/库/二进制和链接命令；配置过而未生成对象的 TU 单独列出。普通与测试门控 DLL 使用独立目录，门控 DLL/CNG故障探针不进入 ZIP。固定 QMT 私有源码只作外部合成 HTTP 验证输入；无私源的独立 verify 执行归档/二进制资格，完整 all 要求外部固定来源的 HTTP 搬迁通过。

## 验证与边界

原生默认用例选择、回放链和包级测试在[构建手册](../runbooks/build.md)说明；脚本测试覆盖子进程错误/超时、坏依赖、包内容变化与路径攻击。测试环境具有固定容量和超时，输出放在指定生成目录。

工具没有部署、账户登录、下单或撤单入口。回测集成通过只证明原生回放链；完整业务/柜台 E2E 由对应实现另验。


## 账户测试运行安装

`scripts/native_support/account_runtime_install.py`拥有双角色测试安装的装配：从本地项目声明生成wheel与完整角色依赖锁，经注入的受管run执行普通安装和pip check，再以实际Distribution/METADATA/RECORD及模块来源生成收据。App与Host各自拥有venv、wheelhouse、锁和收据；解释器、backend、源文件和生成输入摘要归同一安装manifest。原始Flit元数据文件与wheel元数据分别保留摘要，只对CRLF/LF规范后比较完整内容和依赖字段。

本地包选择只固定App/Host角色入口；依照角色根pyproject的tool.uv.sources与递归基础依赖求闭包，实际name/version须与声明精确一致。无source的历史冻结输入可以从原uv.lock的directory/editable或调用方显式local_sources取得映射，来源冲突与缺失拒绝。当前支持无marker/extra的本地精确基础依赖，registry marker归uv/pip。未引用映射与未选角色不构建；同一算法适用当前App、旧候选与host-only。闭包、来源选择及已安装模块归属进入固定安装收据，策略集合随项目声明生效。

prepare的可选extras映射按角色选择根项目声明的optional-dependencies，默认空；所选组的本地包仍由同一闭包解析，public要求原样交uv。export/compile与最终name[extras]的hash安装共同固定选择，防止只下载extra而未以原包要求验收。额外能力的名称和依赖均以角色pyproject为准，选择进入源身份、角色local-projects/local-imports和installation收据。

外层构建使用公开`source_inputs(root, roles, *, extras=None, local_sources=None) -> dict[str, str]`纯接口取得同一原字节输入指纹；路径相对所给绝对root，统一为POSIX。接口不建进程、不写文件，复用闭包与实际_inputs；prepare亦直接消费它，外层只核摘要并保留原字节。

生命周期、总截止、输出容量与隐藏console由调用方执行器拥有；本模块不创建进程，不修改正在运行的终端或全局环境。收据消费复用`tests/integration/qmt_shm_account/scan/runtime_identity.py`；安装资格不授原生场景或真实账户资格。操作和测试入口见[测试手册](../runbooks/testing.md)。
