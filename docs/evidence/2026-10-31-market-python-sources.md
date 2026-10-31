# 市场Python永久源码及构建验证

日期：2026-10-31。范围：[MP1–MP3](../specs/market-python-sources.md)的永久源码、历史发行及显式组装接线。

## 结果

三个Python切片已从`compat/market-python`及固定第三方wheel重新组装：`qmt_data_v2`147个Python/JSON成员、`market/history`146个成员、历史HPR430个Python成员。逐成员对应最终004选择制品；HPR另随附13个第三方发行的26份原许可证及METADATA。历史HPR的`quote_stream.py`及Agent的`quote_stream_contract.py`与采集组件存在版本内变体，均按原内容分别保留。

Host 0.1.0a4、Agent 0.1.0a3、SDK 0.15.0从永久项目沿Flit 3.12.0构建，两次独立输出的三个wheel SHA一致。模块成员、元数据、依赖、extras、入口及许可证核对通过；新构建wheel与原wheel分别记录SHA。构建使用固定E盘CPython 3.12.13，未执行旧内嵌venv。

固定E盘普通Host角色导入重组的查询与采集入口，实际加载切片自身的兼容Host/Agent。历史HPR自有模块通过同角色已有依赖导入，原历史包的C盘base未执行。公开resolve中的旧`market.enabled=false`与独立WT角色选择分别核实，保持其原声明。

显式`source_market.py`选择验证包含数据合同补齐及重复核验。审查复现过“组装后修改收据成员表，安装仍通过”的P2问题；最终实现以单份收据字节核原SHA、组件及输入，核所有冻结成员后安装。删除数据合同的收据在输出目录创建前拒绝。缺固定wheel、改源码身份、路径越界及复用输出目录的必要边界均通过。

## 证据与范围

本地收据：`build/root-market-python-source-001/main006/RESULT.json`，其`build1/BUILD.json`与`build2/BUILD.json`记录准确输入、工具及普通Flit命令，三个`*-import.json`记录实际路径、模块SHA及零业务调用。最终RESULT同时固定测试入口和原生Python安装接线版本；旧失败尝试及审查复现原件保留，最终资格对应接口中固定的输入。

已验最终004普通三角色及989项真实只读链按未变产品字节复用；本轮只核永久来源和组装闭包。QMT调用、账户查询、共享内存连接、服务启动、原数据操作均为0。Python切片包含源码，第三方原生扩展及市场DLL由其普通安装/原生组件负责；本轮未重编原生库、未切换现场或授生产资格。
