# 共用特征与信号轨迹验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-22。范围：[SST规格](../specs/shared-signal-trace.md)的V2无实际持仓周期注入纯信号生产。状态：a1独立full发现两项P2，a2根因修正及开发回归已完成，独立delta进行中；完整V2及执行尚未完成。

## 复用与行为

新包`guanheng-strategy-signals`固定依赖已验a5的公共特征、模型和八角色信号函数，保留原数学实现。两profile分别从完整特征前缀或完成特征后的评估范围切片启动状态机，保留不同上市起点、辅助缺项、CSI证据去重和其他角色重复证据。不会短窗口重种EMA、裁剪证据凑适配上限或注入外部持仓状态。

返回完整有界不可变信号轨迹，收盘available_at为派生知识边界，真实来源、历史实际生产和执行资格均为false。NFA输入域交集、V2数量/执行规则和实际WT链仍须后继验证。

## 首轮独立full

正式报告（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-signals-review-001/FULL-REVIEW.md`）SHA为`1eb1b6675370bdf4d06cd7a2e2810d096a0db10ad000e4fbc51901dac474f7e0`，结论gap、2项P2：

1. 入口信任精确typed预算曾经过构造器校验，伪造或改动后的预算可扩大硬限或令NaN期限失效；计算和两个序列化入口同受影响。
2. 精确typed请求/历史/行/预算缺少必要公开属性时，字段读取泄漏AttributeError，违反固定领域错误契约。

这是明确“不可信typed值”的输入契约问题，不宣称能隔离同进程任意恶意Python代码。非slots dataclass的字段仍可正常解析到类默认值时，该公开属性仍存在；不能仅因实例字典缺键认定输入非法。

其他独立矩阵包括新Flit安装、原22项、126个自主正常/负向、12个自定义对象零调用、40个资源/期限观察及两profile204条决策对照。根任务逐项核对765原件和5份外部运行文件身份相符；清单SHA为`6e1ba92594a741698df6e7081a958780ca0e97ba9e3958994851c49107a90c08`。这些通过不抵消两项缺口。

## a2修正与待验

`_typed_snapshot`先核精确类型及全部公开字段，再构造本次独占dataclass。预算重新运行原硬限准入，后续计算、to_dict、to_json只读该快照；请求、历史、日线先完整取值再使用，缺属性返回固定领域错误。a5和应用锁保持。

修正源码SHA为`c57b82a94aedceddd16e24cd5f29ab2250f3ee449efa5ff324adff7096483721`，新非editable C:/Python314安装wheel SHA为`a5fb5aee94078b776a733a844b4f8c726d97aa8b39e2bd5e480d3c59887a6185`。原285公开入口反例在旧安装全部未满足预期，在a2全部满足；原22组和8容量场景通过。4096条密集证据输出4,541,909B，当前机器约1.650秒；10ms收紧预算约10.018ms拒绝。时区依赖仍绑定tzdata2026.3/IANA2026c及393B上海数据。

冻结审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-signals-admission-002/final-001/review-inputs.json`）SHA为`fd0882a1432e12b69f5c9816e4521932aad8bc9542987dc6c9fcc69bdf888e57`，725项清单SHA为`b76fd4bccce3ec49d57cc8b25e716da4c102c38c2974b6f977403ee4ea54e59a`；661安装文件、wheel成员及20源码/规格文件已核。独立delta尚未返回完成结论，当前不关闭两项发现或授完整迁入资格。

## 后继：a2独立delta完成

以上待验状态由本节更新。独立delta报告（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-signals-review-002/DELTA-REVIEW.md`）结论complete，SST-F1/F2关闭，开放gap为0；报告SHA为`db05ed28ae25cf073f2e0350862467e8230f4d7d10ea9ba59dd85d1643c92b5e`。独立从冻结源码重新构建安装，wheel容器SHA与作者构建不同，逐成员字节完全相同；661项安装文件前后保持。

独立实际重跑22组及285个公开入口反例，另347个自主准入、5个快照后修改隔离、126个正常/负向和12个恶意对象零调用案例通过。两profile共204个决策与固定a5公共函数精确一致；旧a1与新a2四组完整规范结果及身份一致。14阶段单截止、50ms收紧预算、4096日容量和线程/句柄保持分别验证，时间仅为本机观察。

根任务逐项回核745项原件清单（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-signals-review-002/artifact-manifest.json`）及5项外部运行文件；清单SHA为`00fd32329946b991de29c33168be9b54bf0815df358b434378b70694b91c1473`。当前20项SST/core/规格源码身份与冻结值相符，完整性回核收据位于`build/guanheng-workspace/v2-history-pipeline-001/sst-delta-integrity.json`。

此结论授SST a2限定纯计算范围。NFA组合由[NVT](2026-10-22-native-v2-history-pipeline.md)另验；原生数量、回测/实时接线、真实历史来源及完整系统资格继续保留。
