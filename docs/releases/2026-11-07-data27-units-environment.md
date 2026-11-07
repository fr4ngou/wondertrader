# Data27单位接续与正式读取采用

日期：2026-11-07。状态：数据程序、004发布及正式HTTP消费已采用；自然09:00轮次另验。金融策略与新版双策略页面采用分别登记。

## 根因和实现

原数据维护请求没有携带已核QMT单位证据，价格可读仍不能授予策略所需量纲。Data27把固定单位证据接入原任务、捕获资格、原价及前复权；旧INPUTS保持原选择。SDK21只在已审证券域和真实来源连续分段全部符合时解释单位；旧指数原价及金额未知保持原样。

完整归档处理曾重复解码同一Native原档，并把相同条数当作前复权旧文件复用依据。现在由实际Source首层owner提供固定文件、范围和来源身份，合并仅复用完全相同的已核行；不同首层仍走原查询。Helper继续逐WTSBar核对，原期限和取消保持。

正式发布后，单证券Native读取曾返回固定IoError，服务ready不足以证明业务可读。独立对照在相同程序/配置/请求下只改为存在的物理E或D临时目录，两组均通过。部署现在显式绑定已存在的D盘TEMP/TMP；原17代实际继承值未由活进程直接取证，不能归因为某个C盘故障。最初启动命令还使用了不存在的E盘QA临时路径，该路径后已创建并留证。失败记录均保留。

## 已采用内容

- 普通Data27发行`0.2.0a1+unified.27`，正式源码提交`2d3fcf09a84c3472ec75004ec413f7eab9d43735`；27轮子离线构建，181声明源码成员核同。
- 安装`E:/workspace/wondertrader-data/unified-daily-20261104-001/program-history27-20261107-001`。
- 原GenerationPublisher采用004，CURRENT SHA `3d37118ffd4848df117679628cd86e4c5d1df01f11fdcfaad308c02b06683d78`，snapshot `59b0af7a205d839ffac388f7b6734a4a75c4a7e200c7d8128dd4e9ca3a92d099`，市场日期11月6日。
- 原16代正常关闭，17代采用后完成读取故障核查，18代受控环境采用；稳定CURRENT和原Runtime实例保持。当前服务`daily-service018-history27-env/service.json` SHA `e152138ce07e8d9d557c588015ee4d432609358ab9209e93d8c8899dd8afdea3`，Runtime36752、Source5548。
- 正式临时根`D:/wt-data/runtime-temp/data27-20261107-001`；任务根`D:/wt-data/daily27-20261107-001/tasks`。原16请求/15输入、Source连接、全局20260701起点、10证券20190101长窗及7200秒总期限保持。
- 四角色组指向18代，历史补齐、证券资料、日更批读三角色保持原配置和进程，四项均ready。

## 验证和限制

普通安装实际prepare_price_update用1140.469秒完成原7200秒同一总期限，raw7948/front7895，10目标可读，Source请求0。测试主链使用真实已捕获缓存、资料、日历和Native；没有声称重新采集全市场。所有DSB与其主链起点003一致，前复权2307个派生source_rows_sha256按本轮Native回读重算，未宣称所有entry原字节相同。

004单位bootstrap另含19个实际Helper写回（9原价、10前复权），未选条目保持，旧raw指数5305行保持。589680原价存在2个六字段差异（一个浮点低价及一个单位未知的amount），来源原件/比较留证；没有把未知金额改称同维度。原003及所有原始证据保留。

正式Source HTTP由普通Runtime/SDK21消费者完成11查询、5.75秒，20包29648记录与直读004相同。ETF价格CNY/share、量lot、分析指数index-point已核，指数原价保持unknown。该验收覆盖真实入口，Source采集与金融动作均0。

原版纯计算`0.2.0a2`已普通安装，以正式HTTP事实完成九路模型。SH50合法缺份额时的原因文本错误仅在已核原因赋值中修正；97064历史字段及全部交易结果精确保持。159780/159352当天份额、当天成交额及融资缺口仍可见，没有填零。数据和信号可读与另一服务器全输入一致、PIT完整性、金融实际委托资格分别判断。

当前金融Runtime/Native保持退出，旧状态与56原命令责任保留。原版新增100万元、零持仓并行已确认；两策略初始化已独审，实际采用仍须当前P/A与原恢复责任核查。时点及589680处理待用户选择。双策略展示及收益估值的正式安装另验。

## 证据

受控证据根为`E:/workspace/wondertrader-qa/original-live-readiness-20261107-001`：`DATA27-FINAL-DELIVERY.json`、`qmt-units/data27/ACTUAL-INSTALLED006-RESULT.json`、`UNITS004-PUBLISHED.json`、`DAILY27-ENVIRONMENT-PREPARED.json`、`DATA27-ENV-ADOPT.log`、`DATA27-ENV-GROUP-POSTFLIGHT.json`、`source004-read-environment/FINAL-REVIEW-v2.json`、`ORIGINAL-A2-INSTALLED.json`和`original-a2-ordinary-main/VALIDATION.json`。代码合入、普通安装、数据采用、金融采用分别保留状态。
