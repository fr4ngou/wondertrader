# 市场组件兼容源码

这些目录保存已选市场组件的确切Python合同，成员身份统一见[组件表](../../config/market-python-components.json)。目录名区分原组件版本，保留原许可证和模块正文；历史包的版本标签可能相同而个别协议成员不同，构建时按所属组件选择。

`projects/`为历史Host、Agent和SDK的普通Flit项目。源码从原组件及准确的历史自有wheel成员归档，构建期间只读这些永久文件。`hpr-market-scope001`的第三方成员从锁定wheel重建，原内嵌venv和解释器不进入源码树。

现代通信角色的永久源码仍由`connectors/qmt_shm`及`packages/native-analysis-core`拥有。维护兼容合同需同步版本化成员表、构建回归及实际消费者选择。构建和组装步骤见[运行手册](../../docs/runbooks/market-python-sources.md)。

[HPR控制拒绝兼容闭包](hpr-control-rejection001/README.md)固定原marketdaily.4 Agent与既有HPR Host，仅接入已审控制拒绝修正及直接关闭前置，采用独立正常wheel，不随交易SDK升级。
