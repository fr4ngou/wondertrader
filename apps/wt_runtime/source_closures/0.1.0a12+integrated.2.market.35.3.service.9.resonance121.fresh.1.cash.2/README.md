# Fresh cash.2固定源码闭包

类型：固定源码与重建手册。适用范围：`guanheng-wt-runtime==0.1.0a12+integrated.2.market.35.3.service.9.resonance121.fresh.1.cash.2`、`guanheng-strategy-v1==0.1.0a9`和`guanheng-native-analysis-core==0.1.0a2+mdphttp.1.resonance121.1`。行为要求由[唯一规格](../../../../docs/specs/etf-role-replacement.md)维护。

## 固定来源

Runtime共43个Python模块，其中30个来自固定Git提交`9a0b3f9a36a991a1bfc74af8d1fa315dbf4798b3`，13个来自本目录的`overlays/guanheng_wt_runtime`。固定提交已有自有Native真实1.2.1 takeover解析；此构建只处理Python三包。

原service.9角色的account_observation_process、backtest_cli、backtest_completion、runtime四份历史原件继续封装在overlay；initial_inventory由cash.1新原点和fresh输入后继取代。其余九份overlay为新角色贯通、实际资金合同和cash.2定义发布的最终原件，其主干实现也同步到canonical runtime供后续维护。initial_inventory的canonical保留完整中文字段注释；版本快照按已交付原字节保存。canonical的通用CLI及其他历史后继能力保持原路径；构建器从固定提交读取base模块，全部13份差异由本目录固定快照提供，未来工作树改动不会进入本版本。

V1源码位于普通`apps/guanheng/strategy_v1`，角色profile拥有策略版本及八证券。QNA的普通入口为`integrations/guanheng/qmt_native_adjustment.py`和`packages/native-analysis-core/pyproject.toml`，其余成员沿`config/source-packages.json`现有映射。固定QNA角色中的models、native_history、price_quality、qmt_minute_import四份历史原件位于`overlays/qna`；当前canonical版本继续保留完整后继通用导入能力。本目录逐成员映射用于重建固定角色，保持各自明确身份。

所有overlay由已交付源码原件封存；构建不读取预编译产品wheel或当前site-packages。真实账户、持仓、行情和原点文件留在受控运行环境。

canonical Runtime的pyproject保留原四项uv本地项目映射，仅更新发行版本及V1 a9依赖。本目录pyproject保持参考wheel对应的发行元数据原件，两者分别承担源码解析与固定制品重建职责。

## 清单合同

`SOURCE-MANIFEST.json`沿既有`wt.runtime-source-closure.v1`，新增伴随包与全载荷核验字段仅由本目录build.py消费。

| 字段 | 中文定义 |
|---|---|
| schema / version | 源码清单模式及本次固定Runtime发行版本；不表示策略数学版本。 |
| base_commit | base模块的不可变Git来源，全部从该提交读取。 |
| installed_wheel / installed_wheel_sha256 | 已交付参考wheel名称和整个制品SHA256；只作身份比对，不作为构建输入。 |
| modules[].name | Runtime包内单层Python文件名，集合固定43个；新增、缺少或重名均拒绝。 |
| modules[].source | `base`表示固定提交；`overlay`表示本目录版本化原件。 |
| modules[].sha256 | 该模块最终产品原字节SHA256；Git换行变化须恢复到精确声明字节。 |
| pyproject_sha256 | 本目录Runtime元数据文件SHA256；含cash.2和其精确依赖。 |
| payload_sha256 | 参考包全部非dist-info产品载荷的相对路径→SHA256；涵盖Python及source_manifest等包资源。 |
| metadata_sha256 | 参考wheel完整METADATA摘要；版本、依赖和描述须逐字一致。 |
| companions.strategy / companions.qna | 固定V1与QNA伴随包；分别拥有自己的参考身份、sources、载荷及元数据。 |
| companions.*.sources | wheel内成员路径→永久源码相对路径及摘要；pyproject/README为构建输入，不直接成为产品载荷。 |
| build_tools | 本构建器和复用的Core打包工具/直接导入源码相对路径→SHA256；构建前后保持同一输入。 |

路径只接受所属源码树内普通相对文件，源成员不能是符号链接或Windows重解析点。缺失和空集合均为构建错误。清单未声明的产品载荷拒绝进入本版本。

## 单命令重建

使用Python 3.12和显式离线`flit_core-3.12.0-py3-none-any.whl`，后端SHA固定为`e7a0304069ea895172e3c7bb703292e992c5d1555dd1233ab7b5621b5b69e62c`。示例路径为构建环境示例，work/output必须全新且互不嵌套：

```powershell
python -B apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.9.resonance121.fresh.1.cash.2/build.py `
  --work E:/build/fresh-cash2-work001 `
  --output E:/build/fresh-cash2-wheels001 `
  --backend E:/build/dependencies/flit_core-3.12.0-py3-none-any.whl
```

普通仓库直接使用所在Git；只有私有源码审查树缺少.git时可显式`--base-repository <含固定提交的仓库>`。该参数只提供不可变Git base，overlay及V1/QNA仍从本目录所属源码树读取。

构建器先核全部源码，再将已验证后端原字节冻结到新work/deps，三次隔离Flit均使用该副本；收尾核原后端及副本保持。清单、Runtime元数据和源码统一沿普通文件入口准入。QNA公开重导出及RECORD沿仓库原`source_packages.append_core_export`。三个wheel的全部产品成员和METADATA核对后，重新核源码与清单，输出`REBUILD-RESULT.json`。receipt包含实际制品路径/SHA、逐包载荷数量、参考身份、工具身份和无产品运行副作用说明；这些输出是构建证据，运行资格沿Root实际来源/Native/页面验真。

本版本从当前真实持仓建立新100万元基准和initial_inventory周期。新鲜输入及券商现金原点归原运行owner提供，旧账和保存报告归档保持；旧retired-plan迁移、旧零目标ABI不属于本版本。
