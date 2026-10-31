# 观衡a76公开来源增量接收

类型：源码接收记录。日期：2026-11-01。状态：固定23文件已接入集成工作树，制品独立交付继续；现行服务保持。

## 实际结果

Root按交付清单逐项核对157份交付文件的长度及SHA256，核对源码ZIP及23个选定文件的原工作树SHA和交付SHA，再应用精确文件增量。没有删除文件或覆盖其余共享改动，WT框架源码没有新增修改。两份限定范围的独立审查 findings 均为空。

本次复用开发者已完成的同版普通安装、实际公开来源采集、失败保留及恢复、原09服务补跑、HTTP/CSV和桌面/手机页面验收。当前新版完整沪深北序列仅覆盖2026-10-30，历史缺口保留；自然09未来运行资格继续按实际运行结果登记。观衡独立交付不等待交易恢复功能。

## 输入与记录

- 固定交接：`build/observer-ashare-producer-001/ROOT-INTAKE-014.json`，SHA256 `95c22ed49f822a63f63bb92a3a60488b94f41b1b4978e5f09d63c6fb24ce8607`。
- 原源码包：`delivery-014/SOURCE-013.zip`，SHA256 `f988362bd5ace4dc9fdfd6f548355309ed13d3e3b74bf9d98af9ea5c10fee30b`；仅使用SELECTION列明的23个文件。
- 独立App制品：`observer-0.1.0a76+public.1-windows-x64.zip`，SHA256 `3b6ced72bfa9c6068107c061428d9d31e97d3fbb128341443c9bdb47ecf63d6e`。
- Root实际接收脚本及结果：`build/root-a76-source-intake-001/intake.py`、`INTERFACE-001.json`。该运行逐项校验并应用文件，没有启动QMT或切换生产。
- 新数据根接收：`build/observer-market-data-intake-a76-001/READY.json`。沿原内容对象库和原发布入口接收67项数据；新根保持空调度状态，QA运行状态未复制。

构建目录属于本机交接证据，未随源码分发。公开来源实现与行为沿[唯一规格](../specs/observer-public-ashare-producer.md)；独立部署沿[观衡运行手册](../runbooks/observer-runtime.md)。

## 后续与边界

Root继续独立交付制品及实际启动入口，公开来源配置按同id合并并保留其他来源。制品接收、源码合入、用户交付与生产启用分别记录。用户暂时关闭QMT期间，真实终端查询和界面操作保持暂停。
