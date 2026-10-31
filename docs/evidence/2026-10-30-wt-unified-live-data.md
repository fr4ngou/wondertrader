# WT独立采集与历史查询使用同一数据根

类型：实际开发运行及交付记录。结果：数据装配主链pass，完整WRI仍partial。对应[WRI-R1/R3/R5/R6/R7](../specs/independent-wt-runtime.md)。本次新增产品代码和WT框架修改为0，真实委托/撤单为0，生产切换为false。

## 实现及输入

WT独立入口同时拥有历史查询和行情采集，Writer与历史Reader指向同一外部数据根，后续原生归档无须再人工搬入另一份查询目录。原335个分钟store及9只ETF日线继续作为已有历史来源，335表示store数量。实时分钟读取仍由原实时Reader负责；本次HTTP历史服务查询已归档DSB。

使用已验的SRI普通WT安装，WT环境仅包含运行包和SDK，不安装观衡Web或SPA。Python为3.12.14，原生组件及QST配对材料保持原身份。同步Writer的`async=false`和显式`WtDataStorageLifecycle`选择保持。

| 输入/原件 | 身份与范围 |
|---|---|
| `build/wt-live-data-composition-001/DELIVERY-001.json` | SHA `e8ce9337a2b498f21b38c0a7d7faabba939cc5a92725ea433b02509191680425` |
| 最终SRI `SYSTEM-INSTALLATION.json` | SHA `bebf5d4d45cb9b53da64f282dcbb5bfcebd42dd6b210ef5e1bfccb3b40c5a315`；基础两发行不授策略执行资格 |
| `COPY-001.json` | SHA `6710010b3c296dc811cbc2f7f972fdaef61bf79821698c64c6f569fabb120e88`；6930文件、25,495,669字节 |
| 新WT配置 | SHA `6b60b88bb1099907b3dd33fbf5015955845685ea3721c76e159b87b781169b9a` |
| `review/REVIEW-001.json` | SHA `5ca040d5d066b1c61e22f3642e483b64b08e44e1fa48f5d9de1bf4d71319e609`；双轴delta开放P1/P2为0 |

复制范围是原采集根的`his/min1`6929文件及`his/snapshot`1文件，没有日线归档文件；原件复制前后摘要一致。新根使用普通独立文件，无硬链接，原目录及历史证据保留。新根为`E:/workspace/wondertrader-data/wt-live-20261030-001/storage`。

## 实际交接与观察

1. 向旧开发实例原控制目录发布身份绑定的停止请求。旧实例取得正常closed及组件关闭收据，实际旧WT、采集和启动包装进程均已消失。旧父进程句柄没有保留，未宣称测得其OS退出码0。
2. 2026-10-30 01:59:59 +08从新普通安装原CLI启动同根组合。WT实际PID74964、历史PID27980、采集PID30588；实例`192f7216-da36-4026-a4db-6983ee86aa3f`，控制ID`b54f9d05-9dee-41a6-9853-9a0a1d941df9`。
3. 原QMT全推重新认证至generation1，收到6929条报价、35批，真实来源连接成功。该时段闭市，Writer处理0；不以进程ready推定开市分钟已落盘。
4. 原公开SDK查询三证券各240根当日归档和241根混合历史，以及9只ETF各5根日线，原值保持。只读消费者没有构造或停止运行owner；消费前后上述三个实际PID保持。

根原件为`build/wt-data-handoff-001`的`OLD-CLOSED.json`、`STARTED.json`、`ACTUAL-COMPOSITION-001.json`及`READ-PROBE-002.json`。后者实际三证券各241根逐值一致，control405为7.062秒exit0及自身进程树、管道、线程、句柄完整回收。前次QA摘要使用错误字段`time`，已按SDK的`minute`字段另存后继探针；产品源码没有因此修改，失败原件保留。

组合主验收control-verify003为12.426秒exit0、1191输入保持；常驻实例只读复验control-live001为2.608秒exit0、1199不可变输入保持，15次历史查询和1次能力读取通过。动态DSB是采集输出，不作为永久不可变输入冻结。

## 运行与限制

当前常驻实例保持运行。只读地址`http://127.0.0.1:18130`，接线材料为同根`READ-CONNECTION.json`；该文件发布时的`prepared_without_start`描述准备阶段，当前实际启动状态以本记录及原ready/status、OS进程为准。读取凭据只在受控文件和进程环境中使用，正文不包含凭据值。

该配置声明history和collection两个组件，尚未包含账户Host、执行和自动补齐。已有HPR下载Host及QMT策略保持原状。开市后新增分钟、新自然归档自动可读、观衡实际页面和完整执行组合分别继续验收。本记录不重复授予全市场覆盖、所有日期完整性或实盘资格。

后继停止与回退遵循[WT独立操作手册](../runbooks/wt-independent-runtime.md)及制品内`DEPLOYMENT-001.md`。沿当前实例原stop身份关闭；新启动使用新控制目录。已产生的新数据保留在统一根，恢复时继续消费该根，避免退回旧根导致后续数据分离。旧实例的现场观察见[前序采集记录](2026-10-30-wt-live-collection.md)。
