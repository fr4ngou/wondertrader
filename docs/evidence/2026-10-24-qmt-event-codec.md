# QMT 事件页共用校验与真实上下文

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-24。范围：[事件规格SEV-R2的accepted Common切片](../specs/native-qmt-standard-events.md)。实现和下述限定验证通过；Standard事件消费者、完整查询交接与恢复继续proposed，整体目标active。

## 实现与原行为

仅[QmtHostTradeClient.h](../../src/GuanhengCommon/QmtHostTradeClient.h)和[实现](../../src/GuanhengCommon/QmtHostTradeClient.cpp)增加本地页请求边界、独立DOM校验结果及纯validate_qmt_trade_event_page入口。Core与纯入口复用原source/request和正文算法；events原五参、原HTTP/EOF/错误、历史来源诊断、合法gap页及正文原bytes保持。

页尾三个值取同次真实prepare/refresh缓存：read_profile_body、read_result_capacity、admitted_event_page_capacity；完整复制后检查原D才发布。纯入口显式接可信expected/descriptor/实际Hostcap，局部双DOM全部成功后无分配交换提交，失败/异常保持原out。该函数验证形状和关联；来源可信性仍由原实际worker/HTTP链提供，公开DOM不充当认证凭据。

锁定RapidJSON1.1在MSVC没有声明noexcept特征，首次自有无条件trait断言导致拒编；仅在自有层按库声明有条件检查trait，并依据锁定Swap的标量/指针交换实现保留noexcept提交。Vendor、全局特征宏、WT框架和金融mapper均未改。

## 实际验证

最终regression003（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-codec-regression-003/result.json`）重编六个受影响目标，六组CTest全部通过，耗时66.09秒。涵盖v4 codec、实际原生交易客户端、客户端故障、账户投影、73身份场景及原金融映射；受影响的旧实现与新入口共同验证。此组使用既有原生开发profile，不能单独授当前差异树“纯上游框架”资格；固定上游装配另见[标准关闭验证](2026-10-24-qmt-standard-close.md)。

native_v4_codec.cpp（外部历史/待归仓路径：`../../tests/integration/qmt_shm_trading/native_v4_codec.cpp`）新增34次实际validator调用（9正向、25负向）：三种kind、初始/前沿空页、合法gap前缀、历史source、较小实际页cap、错expected/来源/请求/序号/前沿、过期D及失败out全保持；输入销毁后访问独立DOM。原所有向量保留，main断言34且输出event_page_cases=34，原始输出已封存于LastTest.log（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-codec-final-001/LastTest.log`）。

真实HTTP/共享内存原生探针（外部历史/待归仓路径：`../../tests/integration/qmt_shm_trading/native_trade_client_probe.cpp`）在原三事件链核三尾值与原insert receipt的profile/容量、B的profile SHA、可信descriptor及HTTP硬上限相符；没有新增HTTP或SDK调用。全部真实SDK调用0。

独立full及delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-codec-product-review-001/DELTA-001.md`）已关闭编译P2，新增P1/P2=0；38来源根核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-codec-final-001/REVIEW-ROOT-CHECK.json`）一致。Reviewer执行0，动态由根独立提供。两个测试原文按修改前完整SHA恢复并独立diff，未把作者自评作为保持依据。

## 限制与下一步

尚缺分配异常注入、新尾字段的HTTP409/截断/晚D专用断言及真实HTTP Hostcap低于profile的变体；较小cap目前有纯校验场景。支持范围为当前Windows x64受管入口，新加密依赖矩阵不授其他平台资格。regression001的临时driver语法错误及002编译失败均保留，003成功不改写旧记录。

没有接入onPushOrder/onPushTrade、没有实现event_poll_ms调度、金融event provenance/key输出、去重索引或首次cursor。查询/live与跨进程覆盖仍缺共同水位依据，不能以这34场景、源ACK或查询成功宣称持仓恢复一致。旧QMT仅静态参考，生产Factory和终端保持。
