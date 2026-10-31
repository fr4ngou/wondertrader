# 真实HPR换代与采集恢复

类型：开发运行实例的现场交接证据。日期：2026-10-30。状态：真实来源认证、原生历史读取及持续采集已恢复；全量ETF/指数历史覆盖继续由数据模块验收。

## 触发点及完整链

原历史通信Journal已保存987条终态，剩余37个容量；前四批下载/冻结/转换已完成，后四批需要按原产品合同建立新代际。已下载的分钟文件、原生成果和旧请求身份保留。源材料由数据模块冻结generation-003；根统一操作QMT及WT生命周期。

现场复核发现最早的WT72824已在此前正常停止；真正仍运行的是composition-001-resume001的WT45216、control556a8276-add2-4ff0-8ae8-d81757f35ac2。此次先确认新prepare暂停、原987条全部terminal、输入/原策略/备份SHA一致，再只停止GH_WT_MEMORY_VERIFY；界面及Formula stop success确认后按原控制身份正常关闭该WT。原closed的components_closed=true，实际8个相关进程OS均不存在，未强杀或删除旧运行资料。

随后将已冻结b045353cd87ac671a91856644c92d6254ae3208a165e6cc46233c33f1d71ead7正文放入同一策略，在独立WT三组件ready后启动。原QST设置/秘密、统一数据根及18130服务地址保持，旧Journal留在generation-002，新业务继续generation-003。该交接没有真实下单、撤单或WT核心修改。

## 当前实际身份及验真

| 项 | 现场值 |
|---|---|
| WT PID | 33636 |
| Host / history / collection PID | 46288 / 60964 / 75000 |
| 配置SHA256 | 5aad18a557c29e74bf5d8c4fcb8c413c35f7ece9069ff772ca90ea061f98d453 |
| 实际control_id | 65844eee-6869-4b64-bb3f-b6adf70f5203 |
| generation003 pair SHA256 | 2a4dea83c92a118f4f323119f21ac597120bf9ae638ca95e7c01adcb680e19b2 |
| 已冻结旧Journal SHA256 | 912c3c2931b740b72d1645c67b67c2a018e695370f0720ee5cf6036ac9b54ac3 |

实际认证profile为v6。只读分钟请求d69eafbf-8e2a-483b-b417-ebd6437e175d返回4根（max5，fill_data=false），没有触发下载或补零；原生统一历史查询返回5根，与换代前完整原值相同。首次有限GET观察窗口得到SourcePending后，后继沿原ID查询终态，没有重复POST或重启来源。Control431退出0、树/EOF/join/资源关闭通过。

同一采集进程收到6929条来源快照，connected=true，心跳112→160，溢出0、队列0。writer_processed=0处于本次闭市观察范围；该结果证明连接及流持续，不扩大为本轮新交易分钟落盘。原有交易日落盘/归档证据保持独立资格。

## 原件、交接和剩余

build/wt-live-host-data-composition-002的PRESTOP-CHECK-001.json、OLD-STOP-REQUEST-001.json、SOURCE-PLACEMENT-001.json、RUN-002.json、POST-READ-001.json、RENEWAL-RESULT-001.json及ACTIVE-READ-CONNECTION.json保存实际身份。原PREPARED中的5111…控制目录此前已空目录存在，首个launcher没有获得实际启动资格；该材料保留，新运行使用全新控制身份。wrapper exit0与实际WT PID/ready分别取证，不据wrapper退出推断实际服务运行或正常关闭。

已将新代际、当前连接文件和上述结果交回《杂役》，允许恢复cohort005–008。完整ETF/50指数目标仍从2021-11-01开始，实际来源覆盖与全量装配分别报告；换代成功不表示历史已补齐。原generation002保持只读，generation003继续正常业务写入，不要求活动Journal字节固定。

本文状态按本次实际运行核实，后继停启以原控制目录和OS状态为准；准备文件和旧PID快照不能代替运行事实。独立delta核对另记录于本目录REVIEW-001.json。

独立delta审查REVIEW-001.json（SHA256 6a29696bb9e49fbedcbd40bd6b007e7d196bc945de61ebb6e6fd783e5514ebaf）确认实际换代通过，P0–P2为0；一项非阻塞P3指出RUN-002继承的previous_runtime_pid=72824是最早准备引用。已追加PREDECESSOR-CORRECTION-001.json明确本次实际停止45216及其closed摘要，原冻结记录保留。新运行实际身份见ACTIVE-READ-CONNECTION与RENEWAL-RESULT，不使用旧准备PID作为停止对象。
