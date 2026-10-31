# Reader 产品构建入口

以仓库根运行 `python -B scripts/native_support/reader_product.py --work build/<new-directory> --archives <locked-archive-directory> --toolchain-lock <toolchain.json>`。
显式需要批准的 Writer 生命周期变体时加 `--writer-lifecycle`。默认安装目录是本次 work 下的 `installed`。

`toolchain.json` 是对象：键为 `cmake`、`ctest`、`ninja`、`cl`、`link`、`lib`、`rc`、`mt`、`python`、`git`，每项有 `path` 与 `sha256`。使用固定工具和完整 Python 发行准备此文件，构建器核对实际 VS 环境解析得到的工具。仓库须预先拥有声明的 Git 对象；离线构建禁止缺失对象的延迟下载。

归档文件名与摘要见 `config/native-dependencies.json`。归档可由离线媒介提供；源码快照和全部 WT 库由本次构建产生。调用者用既有受管 Job 宿主运行长构建，实际编译命令沿 `native.run` 隐藏窗口、有限截止和进程树回收合同。

安装 `app/GuanhengRealtimeReader.dll` 保留原配置；`app/WtDataStorage.dll` 是原版，`app/nrc/WtDataStorage.dll` 是明确选择 NRC 的读取变体；可选 `app/WtDataStorageLifecycle.dll` 是既有 WLC。调用者选择并记录实际加载文件。此次入口不替换 B 的交易或 CTA 执行发行。

规格：[原生 Reader 离线构建](../../../docs/specs/native-reader-offline-build.md)。
