# 来源三包源码构建与验证

类型：运行手册。范围：永久 Host/Agent/Core 源码构建及合成 SDK 验收。要求见[来源包规格](../specs/source-package-builds.md)。构建命令不启动 QMT、Host、通信存储或真实账户操作。

## 构建

使用已固定并记录身份的 Python 3.12+。在仓库根目录执行：

```text
python -B scripts/source_packages.py build --work <新构建目录>
```

backend 取自 `config/python-build-dependencies.json`。已有锁定工具时可离线构建：

```text
python -B scripts/source_packages.py build --work <新构建目录> --offline --backend <锁定Flit-wheel>
```

输出为 `BUILD.json`、三个独立构建日志和 `wheels/`。`BUILD.json` 固定全部永久输入、解释器及 backend，记录三个 wheel 的实际 SHA。工具不读取历史产品 wheel 或临时源码快照。失败保留输出目录及日志；下一次构建使用新目录。

Host/Agent 直接从各自项目构建。Core 只组装成员映射声明的 namespace，保持基础 market-client 元数据独立；公开回放重导出按原 Core 标准 wheel 映射发布。修改模块成员时同步映射；版本和依赖继续由各自 pyproject 唯一声明。

## 普通安装与模块回归

新 wheel 经角色装配进入完整 wheelhouse，并更新角色的 SHA 锁文件。使用隔离解释器，沿已有安装流程执行离线、无索引、require-hashes 安装及 pip check，再核实际模块和 RECORD。禁止将新 wheel 原地覆盖到运行环境。Host 最小角色和 SDK 完整客户端角色分别保存安装收据。

在安装了 Host/Agent/Core 和基础 market-client 的验证环境执行：

```text
python -I -B tests/integration/source_packages/run_checks.py --work <新验证目录> --backend <锁定Flit-wheel>
```

该入口验证真实 HTTP 和 Windows 快照行为，并从永久源码重复构建三包。`RESULT.json` 与 `REPRODUCIBLE.json` 分别记录回归结果和两个独立输出的相同 wheel SHA。Windows 发布合同在其他操作系统中明确跳过，不能据此授 Windows 资格。

## 六通道 SDK 短主链

该入口使用测试 Context，不接入真实 QMT。显式提供目标 Python 3.6.8、其 SDK 身份、标准库许可和两份验证安装收据；安装收据包含 pythonw 路径和已安装文件的 SHA。

```text
python -I -B tests/integration/source_packages/run_sdk.py --work <新SDK目录> --host-installation <Host安装收据> --coordinator-installation <完整客户端安装收据> --source-build <BUILD.json> --sdk-pythonw <Python3.6.8-pythonw> --sdk-manifest <SDK身份JSON> --stdlib-license <CPython许可>
```

夹具在新目录生成独立六通道，所有账户和数据均为合成值。正式 Agent/Host 配对及共享内存代码保持实际安装身份；外部夹具读取配置文件，QMT 正文不使用这份测试配置。三证券准备、两个 v8 批次、失回执原 ID 恢复及持有旧快照时的提交均须完成；五 Host、Source 和 CLI 的终态核实原树为空、读线程结束、管道 EOF 和资源关闭。

长时间验证由独立进程或受管 Job 拥有，使用隐藏窗口和有限截止。界面操作工具只负责界面。实际 QMT 运行、数据覆盖、金融操作和生产发布分别沿对应现场授权及收据验收。
