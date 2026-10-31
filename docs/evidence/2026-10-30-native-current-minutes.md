# 今日采集分钟的原生读取

类型：真实只读运行证据。日期：2026-10-30。结果：三证券的盘中已闭合分钟读取、原分钟通知回放及受管Reader停止通过；自然ticker和完整策略资格继续分别验收。

## 调用链与输入

活动DataKit原Writer → 原rt/min1 DMB → 已安装NMR candidate-002的minute_native → 原WtDataReader → 原分钟回调。盘中路径直接复用[受管分钟Reader](../specs/native-minute-reader.md)，归档历史继续沿18130的source-collected服务；没有新增HTTP服务、行情存储、聚合算法或WT修改。

Reader DLL SHA256为f5f7efecf0648c425d4c7d85f217ea670be372c95465f07081564b5db30da122，原Helper SHA256为50a106a44d7dcaa1c60c0c4f1b766dce69bf1738c86f914d13a240f963986c0f。运行前完整核candidate-002安装清单，使用原活动采集的真实sessions/commodities/contracts只读副本。

原根为E:/workspace/wondertrader-data/wt-live-20261030-001/storage。每证券DMB双读相同后保存单独稳定副本；该取样按证券分别进行，不声明全市场原子快照。私有QA沿冻结build005探针，仅把固定截止11:30/120根改为09:45/15根、119后继改为14；产品及旧QA保持。

## 实际结果

在稳定副本和活动根分别执行相同安装DLL的create/init/read/onMinuteEnd/stop/delete：

| 证券 | 原分钟区间 | 每次读取 | 原后继回调 | 核对 |
| --- | --- | ---: | ---: | --- |
| 510300.SH | 2026-10-30 09:31—09:45 | 15 | 14 | 时间及六数值逐字段等于原Helper |
| 600000.SH | 同上 | 15 | 14 | 同上 |
| 000001.SZ | 同上 | 15 | 14 | 同上 |

09:31预热后显式推进原onMinuteEnd至09:45，收到后续14根；重复相同通知新增0，all-bar更新一次。stop后读取和通知拒绝；删除Reader后原三份独立切片仍保持相同原值，最后release。上述为真实文件的显式分钟回放，未把人工截止写成自然调度验证。

外层PID67772退出0，所有构建/原生子调用经原native.run有界隐藏Job成功返回；其成功条件包含子树归零、输出EOF、reader join和资源关闭。根冷核13项不可变输入全部一致。活动采集PID75000及原控制/配置身份保持connected，Writer计数继续增长至2861767；没有停止、归档或改写原实例。

## 原件与限制

原件目录为build/qmt-live-native-read-20261030-001，包含QA-DELTA.json、INPUTS.json、EXPECTED.json、snapshot.json、actual.json、LIVE-BEFORE/AFTER及ROOT-INTAKE-001.json。RESULT.json SHA256为25f2380d435cd45a2caf4df4edcdf4e650d9ccf596f0b8ba89471ec56b2f5a97。

本片段新增产品代码、来源查询、QMT操作、真实下单/撤单和生产切换均为0。该证据授予这三个样本及这个闭合截止的原值读取，不扩大为全市场完整性、供应商分钟逐值一致、单位标准化、自然CTA持续调度或跨日资格。完整策略由其正式宿主继续组合验收。
