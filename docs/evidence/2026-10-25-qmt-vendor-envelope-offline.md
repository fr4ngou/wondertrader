# QMT供应商原回包离线观察

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：阶段A隔离开发通过；真实BSON、运行函数家族和R8首次/重连交接尚未验证。

## 范围与实现

按测试规格（外部历史/待归仓路径：`../../tests/integration/qmt_vendor_envelope/README.md`），仅编译SHA固定供应商源码中两个原函数的AST，使用明确合成JSON-BSON与无I/O client，保留同一次RPC原回包及callback的type/data/error。没有导入SDK、读取callback cache、额外查询、终端变更或真实委托。固定源码12204字节，SHA fc0ac79e94ad19a7e2ddac07e437965aeaaab342a1189553c4ae6c8af3f6cb0a。

独立full发现observer.capture失败后其可覆盖fail方法再次异常，会逸出callback边界。修正由Observer基类统一持有粘滞失败状态，内部直接调用基类fail，完整emit入口受异常边界保护；双故障仍保留原查询行和合法callback一次转交。

最终probe SHA 260ec1be791a86d4ba262427212ad890de8f71557d86f99d86d2b7e9c95dd6b8；测试SHA a282e85744375627066aa261b4f935dc96cfca206232dd4f591fa27d6eac57ce。原22项正文保持，新增2项。四文件冻结见INPUTS（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-vendor-envelope-frozen-002/INPUTS.json`）。

## 实际结果

| 输入及解释器 | 结果 | 原件 |
|---|---|---|
| 最终修复，Python3.12.14 | 24/24、无skip，CLI同次query/callback通过 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-vendor-envelope-runtime-312-002/result.json`） |
| 最终修复，国信自带Python3.6.8 | 24/24、无skip，CLI通过 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-vendor-envelope-runtime-368-003/result.json`） |
| 原版观察器，两个解释器 | 各22/22及CLI通过，范围不含后发现的双故障 | 初版封存（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-vendor-envelope-verification-001/VERIFIED.json`） |

初次3.6驱动在22项通过后访问不存在的subprocess.CREATE_NO_WINDOW属性失败；后继驱动采用Windows常量0x08000000，探针源码保持。失败原件保留，未把该次CLI称通过。所有最终运行均沿创建期Job、原截止、隐藏进程及实际tree0/EOF/readers/resource关闭取证。

独立full（外部历史/待归仓路径：`../../build/qmt-vendor-envelope-independent-review-001/REPORT.md`）及修复delta（外部历史/待归仓路径：`../../build/qmt-vendor-envelope-independent-review-001/revision002/REPORT.md`）已封，delta开放P1/P2=0、执行0；根逐字核四份原件，见复核（外部历史/待归仓路径：`../../build/guanheng-workspace/migration-slice-verification-20261025-001/VERIFIED.json`）。

## 后继资格

本片没有取得券商查询包含哪些实时回报的证明。后继阶段B准备（外部历史/待归仓路径：`../../build/qmt-vendor-envelope-stage-b-preparation-001/PREPARATION.md`）限定同一真实查询局部观察，不修改SDK全局，不增加查询/callback登记或消费cache；当前仅方案，未接入终端。production_qualified持续false，完整迁移目标active。
