# 市场组件Python永久来源

状态：accepted。类型：功能规格。范围：已选择市场组件的Python源码、历史兼容发行及其组装；原生库、服务启动和交易能力由所属组件承担。

## MP1 来源与版本

`config/market-python-components.json`声明每个组件成员的永久相对路径、SHA和历史版本。`compat/market-python`保存准确的兼容源码；`qmt_data_v2`、`market/history`、`market/hpr`分别保留自身文件布局。Host、Agent和SDK的历史独立发行项目具有独立元数据。

相同版本标签下已有的实际源码变体也须逐成员保留。历史HPR的两处行情协议文件与采集组件存在差异，使用各自固定成员。现代Host/Agent/Core独立角色继续沿[来源三包规格](source-package-builds.md)构建。

## MP2 构建与组装

`scripts/market_python_components.py`从永久文件表组装新Python切片。第三方Python成员、许可证及发行元数据从已固定整包SHA的标准wheel取得；旧venv和旧C盘解释器仅作为历史制品记录。组装工具验证输入前后SHA，输出成员表、来源身份和实际第三方wheel身份。构建无需读取历史build路径；配置中的原安装路径用于溯源。

历史Host、Agent和SDK沿锁定Flit普通构建，保留包成员字节、名称、版本、依赖、extras、许可证声明、入口和描述正文。新wheel拥有新的构建SHA，原wheel身份保留在收据中。Python切片包含源码与数据契约；解释器、第三方原生扩展和市场DLL由原普通安装及原生构建入口提供。

`scripts/source_market.py --python-component market/history`显式选择兼容历史查询源码，缺省选择保持当前仓库源码行为。采集组件的Python切片交给其原生组件装配入口。组装服务只选择已声明的合同，保持原生ABI、文件格式及数据目录所有权。

## MP3 调用与验证

分别核实公开安装解析、实际消费者配置及导入路径。最终004组合中`market.enabled=false`，其旧App消费者和旧内嵌HPR解释器属于未启用的历史声明；独立WT和当前Host使用固定E盘角色。`qmt_data_v2`的查询及采集入口显式引入自身随包的历史模块，保留该闭包。

验证从永久源码重新组装全部成员，核对原选择制品，再由固定解释器普通角色导入实际查询、采集入口。导入验证禁止业务调用与服务启动。已验真实账户、行情和分钟主链按未变模块字节复用，单独说明覆盖范围。纯Python切片的成功只证明源码及导入闭包，完整原生安装、现场启动和生产资格由对应证据确认。
