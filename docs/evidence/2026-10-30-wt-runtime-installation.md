# 独立WT离线安装与无SPA发行验收

类型：开发验证证据。日期：2026-10-30。状态：安装模块完成主链，完整WRI组合继续。适用[统一安装规格](../specs/system-runtime-installation.md)与[独立WT规格](../specs/independent-wt-runtime.md)。

## 结果与实现

原普通安装器新增显式wt角色，安装WT运行包及其声明依赖，保持app/host默认角色选择。系统发行v2允许static=null，发行包按原组件清单复制及核验原生行情、历史和HPR材料；v1继续要求原SPA。搬迁包内原CLI从无关工作目录执行离线安装，再由resolve提供已安装WT的模块入口。

最终final002实际安装环境只有guanheng-wt-runtime与guanheng-market-client两个发行，未安装观衡Web包/FastAPI，spa为null。安装时无源码构建、来源查询或业务进程启动。固定源码快照包含同期B的执行文件；这些文件的策略依赖和执行主链另验，本结果仅授安装模块资格。

相关实现：account_runtime_install.py的角色/依赖闭包；system_runtime.py的v2静态可选和WT路径解析；runtime_identity.py的角色模块身份核验。QA曾遗漏WT已加载子模块的来源检查，现统一按角色前缀核验，安装根外及错误RECORD来源两项回归已通过。

## 最终输入与实跑

本地证据根为build/wt-runtime-installation-001。REVIEW-INPUTS-002.json绑定11份实现、QA和文档及6份final002结果；final002/FROZEN-001.json固定37份当时源码。

| 验收 | 结果 | 原始记录 |
|---|---|---|
| 普通WT角色离线安装 | exit0，11.453秒；原依赖声明、wheel、pip check与RECORD身份通过 | final002/RESULT.json，control398 |
| ZIP解压、包内CLI到全新安装根、resolve及WT入口 | exit0，350.016秒；1183文件，无App/SPA，实际--help和隔离探针通过 | final002/SYSTEM-RESULT.json，control399 |
| 原角色安装回归 | 114项通过 | control394 |
| 系统安装兼容回归 | 24项通过，含v1缺SPA拒绝 | control395 |
| 已安装模块身份回归 | 139项通过，含WT加载子模块两案 | control396 |

上述control均在build/guanheng-workspace对应目录，实际passed=true、forced=false、tree_zero/readers_joined/resources_closed=true、双管道EOF且exit0。外层QA协调器只管理本次工具子树，不属于WT产品依赖。

| 制品 | SHA256 |
|---|---|
| 系统manifest | 6b759bce0be7ed4b204817d8e52f4d747a84831b31c33f73e32a107a56412677 |
| ZIP | 7c3db41a93a04a3ef3e4c1c68d6997288d9e4045e5eb57a1f885636875cfea32 |
| 新根SYSTEM-INSTALLATION | bebf5d4d45cb9b53da64f282dcbb5bfcebd42dd6b210ef5e1bfccb3b40c5a315 |
| SYSTEM-PATHS-001.json | 01dc7e4b030dd27eabd1a826940b98282a5d14f71e04b7bdbe9f095600b16cdb |

新安装根为build/wt-runtime-installation-001/final002/installed001。原生组件消费标签沿其冻结历史manifest；实际运行职责以ADR-0016及WRI为准。

## 审查与边界

独立full/源码delta已完成并修正子模块来源漏检，开放P1/P2为0；最终实跑制品身份delta已完成，review/REVIEW-FINAL-003.json SHA为3c018a3b7e44768a6172fc062bfeaddff27bf01156d4ad76d441db8d75a842f8，两轴complete且开放P1/P2为0。逐项核对11当前输入、6结果、37冻结源、三处1182 payload集合及字节；最终安装解释器实际执行两项WT子模块来源拒绝，前后正常身份检查均通过。实际Host晚到/两代、真实历史及只读消费者隔离沿[独立包证据](2026-10-30-wt-independent-runtime.md)；[现场采集](2026-10-30-wt-live-collection.md)保持另一冻结安装，不原地替换。

完整策略执行、真实观衡正常/异常关闭、实际QMT与执行组件组合及生产升级尚待验收。此次未切生产、未改WT核心、未执行真实下单或撤单。

文档检查control400实际exit0、0.781秒、完整回收，结果为PASS: local document navigation and skill manifest integrity；该检查仅验证文档导航及技能清单。

## 新安装的数据主链后继

composition001/DELIVERY-001.json SHA c06ee79dcbe4a083f7c5be9fd9b5e372fc979ebfb4108e6d1106174d8288a009绑定实际新安装的WT角色、新payload HPR Host解释器和新payload原Reader服务。run002实际85.088秒exit0，真实五根分钟与原结果相等；64.344秒晚到、两代各五项SDK替身查询、旧终态200/旧绑定409及只读消费者正常/异常退出后继续均通过。1579项角色/payload/外部输入前后及独立重算一致。所有进程树、管道EOF、线程与句柄正常回收。

11份WRI实现及14份SDK源码与原已验候选逐字一致，复用原full并完成安装/动态delta；composition001/review/REVIEW-001.json SHA b2dcd65e8d4004239f9b3fecb7dc6c6ae8882b048735342b0166e425add8cee7，开放P1/P2为0。产品两套安装保持原字节。采集为协议夹具；真实QMT/原Writer/真实观衡与策略组合仍按各自范围验收。

下一步真实现场历史实例准备沿原source-collected/source-catalog能力，复用原已验目录和自然归档；现有真实采集与ETF/HPR任务保持。
