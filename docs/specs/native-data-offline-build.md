# 原生数据组件固定源码构建

状态：已实现并通过本模块主链验收。范围是最终 004 已选非交易原生入口；交易执行由独立发行管理。

构建沿 `scripts/native_support/reader_product.py` 增加显式 `--data-components`，同时要求 `--writer-lifecycle`。原 Reader 缺省选择及其期限保持原合同。固定 Git 08b230、原批准覆盖、锁定源码依赖和工具身份复用 Reader 声明；增加 WtDtCore 同批静态库。所有目标在新工作目录由源编译。

`config/native-data-sources.json` 声明 account006、parser_v6、collection004、analysis001、quotes_hpr3 五个自有源码版本。每个版本保持自己的 Common 头及实现；构建前后校验 SHA。来源晋升记录属于本次交付证据，正式构建只读取永久声明源和固定 Git。B 的标准交易实现保持其独立所有权。

普通安装产生 native_account、native_qmt_history、native_analysis、native_bar_file、collection、parser_v6 六个原生组件切片，各有入口、许可证、构建来源及逐文件身份。native_bar_file 切片内的 NativeBarFile、Helper 和 HPR3 ShmQuotes 属 qmt_data_v2 原生依赖；DataKitSession 属 market/collection。Python 服务及 Host 角色发行边界保持原样。native_analysis 显式选择原 NRC Reader；collection 同时提供原缺省 Writer 和原批准 WLC，调用者继续显式选择。

验收从全新目录实际编译并搬迁普通组件，执行合成历史读取、插件创建/删除、DataKit 初始化/正常关闭及相关失败边界。既有实际只读主链（989 项冻结输入）与 Reader31 证明按未变源复用。验收只写独占合成目录，不连接 QMT，不操作现行数据服务，不授金融或生产资格。

构建示例（仓库根；调用者提供已锁定归档和工具身份）：

```powershell
python -B scripts/native_support/reader_product.py --work build/<fresh-directory> --archives <archive-directory> --toolchain-lock <toolchain.json> --writer-lifecycle --data-components
```

工具和归档合同沿[Reader 离线构建](native-reader-offline-build.md)。输出位于本次工作目录的 `installed/components`；每个切片有 `INSTALLATION.json`、`app`、`licenses` 和 `provenance`。`native_bar_file` 与永久 Python `qmt_data_v2` 切片组合，`collection` 与既有独立采集入口组合；其他切片沿各自已声明的 EXE/DLL 入口使用。历史未选 HPR 部署仍保持原 disabled 声明。

采集活动关闭验收明确选择既有 `WtDataStorageLifecycle`。缺省 `WtDataStorage` 继续按原合同提供；本工作不改变它的线程或停止语义。新的产物资格覆盖离线重建、普通加载、合成读回、原匹配 SDK 的短报价链及正常释放；真实账户、行情及历史业务的既有证明按对应源码身份复用。
