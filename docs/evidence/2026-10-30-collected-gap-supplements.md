# 独立补齐来源进入统一历史查询

类型：验证证据。范围：CNH-R5候选，自有采集历史适配器；WT框架、活动采集和原归档保持。

准备、配置与统一查询的操作顺序见[独立补齐来源手册](../runbooks/collected-history-supplements.md)。

实际发现：2026-10-30的510300.SH、600000.SH原归档各239根，均缺13:01；000001.SZ为240根。原QMT缓存已导出记录包含两个缺少标签。当前证据确认来源导出存在与归档缺少的差异；对应原tick未留痕，实时来源延迟、接收或聚合触发原因保持未知。旧003报告的固定full240文案不适用于两只239样本，原失败保留。

新根 `build/qmt-minute-gap-repair-20261030-001` 仅筛选两个缺口的原CSV行，原schema2 profile/unknown单位/分钟边界保持，原Importer+同包Helper写新DSB，再由原NativeHistory逐浮点位核值。原归档和重叠记录未重写。

自有CollectedSourceMarket新增显式可选supplements；原base341目录保持，原select_sources按分钟合并并保留分段metadata。统一公开call两只239→240，控制证券240保持；718条原记录及来源信息精确，4320字段浮点位精确，原三个DSB SHA保持。普通安装WT管理候选SourceMarketProcess，公开SDK三证券各240根与原call完整响应同值；WT/服务/Job/EOF/join/句柄正常关闭。

必要回归覆盖缺省与空列表、同值去重、异值冲突、补充来源未登记证券、缺归档及部分创建释放，六项通过。初次QA的source-store空预载和Path参数不符均留原件，修正只涉及QA接线。

固定组件只在原已安装组件基线上替换collected_history.py，Native/协议/角色与其他文件保持，具体SHA与命令沿该根交付清单。候选未切入活动WT，来源查询/QMT操作/真实下撤单0；全市场覆盖、来源授权标准化、自动准备和生产分别验收。独立审查由根会话统筹。

根接收的后继独立审查见同根 `REVIEW-ROOT-001.json`，178项接口/组件/源码及QA输入当前0漂移。Standards/Spec限定通过：原来源商店准入、原Native读取、原值去重/冲突和线程/关闭归属保持。结论覆盖显式本地 supplements 候选；后继 SRI 同包启用、自动在线准备、全市场完整性及未知原tick触发原因分别保留。上述旧证据正文新增本段登记，不回写原冻结收据。
