# 独立观衡账户页根集成核验

类型：限定开发证据。日期：2026-10-30。状态：固定 a42 的 SDK 账户 HTTP 模块已接收；真实 QMT 和完整系统仍待验收。

## 输入与接收范围

- 交付：`build/native-account-page-001/DELIVERY-001.json`，固定 App `0.1.0a42`、install-004、SPA003 与 main004。
- 根收据：`build/native-account-page-001/ROOT-ACCEPTANCE-001.json`，SHA256 `980185c590f3a52636291c89d2cc37a234ae53da2cf443e0829298edcbf86fa4`。
- 22 项交付证据重新计算摘要均一致；wheel 和 installation 身份一致，wheel 中五项账户消费 Python 源文件与交付固定摘要一致。
- 当前 13 项源码中 12 项一致。`apps/guanheng/pyproject.toml` 已由后继任务升为 a43；根核对固定 a42 副本及解析后 TOML，差异仅为版本号。a43 沿后继组合独立验收，本记录保留 a42 的资格。
- 共享证据索引与 C 交付文档已继续更新，原报告和冻结副本保留。沿原 Standards002、Spec002/003 的独立审查复用本模块结论。

## 根复算的实际行为

根使用固定安装的 `pythonw.exe -I -B` 调用包内原 `project_publication`，分别复算两轮成功、失败保留、恢复为空四份 NAP 发布帧，与保存的实际 HTTP 正文逐字段完整相等。HTTP 包装层写入的实例 scope 单独保持原值。脚本 `build/native-account-page-001/root_http_recompute.py` 及结果 `ROOT-HTTP-RECOMPUTE-001.json` 保留；进程退出 0，stderr 为空，启动服务及来源查询均为 0。

两轮可用资金为 82000、82100；失败保留原成功数据和原查询时间；成功空结果清空持仓、委托及成交。停止后的 HTTP 保留最后成功数据和时间。App 重启前后 WT/Host 身份保持，来源查询计数均为 4，App 新增查询为 0。原 main004 共 18 次 SDK 查询，真实下单、撤单为 0；1357 项运行输入前后一致，WT 和 App 正常关闭、资源回收成立。

浏览器证据沿作者实际 CUA DOM 结构记录复用；根本轮没有重放浏览器，也没有本地截图制品。账户查询结果属于账户总量，原策略归属展示继续保持独立来源。

## 后继与限制

开发者2正在把该独立观衡接至 HPR、交易 Host、账户 Host、NAP、历史及采集六组件的正式 WT 候选，并验收观衡独立更新、回退和退出。真实 QMT 的同候选账户/行情仍由根统一现场验证；唯一保留策略的状态恢复和稳定退出由开发者1完成。

本记录证明固定 SDK HTTP 模块及其消费边界。完整目标继续 active，真实 QMT、a43 组合、策略执行和生产资格分别保留待验收。当前实际数据 WT/Host/历史/采集四进程经 OS 查询均存活，临时探针原文 SHA256 `35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae` 保持。
