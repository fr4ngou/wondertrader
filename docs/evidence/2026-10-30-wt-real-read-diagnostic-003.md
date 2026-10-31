# 真实四连接只读诊断003

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证证据。日期：2026-10-30。状态：真实请求失败；根因unknown，原件及回收已核实。

## 输入与现场

沿 [真实四连接后继](2026-10-30-wt-four-connection-real.md)，使用原candidate004安装、正式单个QMT正文四连接及仅观测的Host QA包装。准备冻结55项；SDK固定入口713输入、11.110秒通过，65事实/30ABI及正常关闭保持。SDK首OSError在停源后，不能用于解释实机。

实机临时SHM_READ_PROBE正文SHA aafae3ecc4ac42be5dda9d6629271512ffe01314b2c1a8008a8c852cf96f1088。QMT公式日志确认本地06:39:37开始、06:40:02停止；逐字原文35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae已恢复。

## 有效发现

真实结果（外部历史/待归仓路径：`../../build/wt-real-four-connection-diagnostic-003/real/RESULT.json`）：第一组position请求terminal/operation_interrupted，未获得结果数据；其余三组未进入后续读取。原生扫描3936ms、exit3/source。712份真实执行输入前后保持。

请求边界（外部历史/待归仓路径：`../../build/wt-real-four-connection-diagnostic-003/real/FAILURE-BOUNDARY-001.json`）：全局首Runtime OSError发生在UTC22:39:42.015，stop_requested=false，栈落在原session.receive；来源SDK进入/返回均未被本版观测，因此保持unknown。

逐代冷读核对（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/ORIGINAL-GENERATION-BOUNDARY-001.json`）：失败请求22:39:48.133630受理、22:39:50.008350派发、22:39:52.014249终态。该请求的受理/派发/协调器binding摘要一致，但全局首异常早于本请求派发7.992438秒，而且旧trace缺Runtime/代际身份。因此当前证据无法将首异常归因到本次请求；旧首异常很可能属于其他运行代际的说法也仍属待验证假设。

## 资源与剩余

外层结果（外部历史/待归仓路径：`../../build/wt-real-four-connection-diagnostic-003/control-real/RESULT.json`）：63.171秒业务exit1；强制false，整树0、EOF、读线程join、句柄释放完整。内层WT/QST exit0；原生业务exit3亦正常回收。

停源和恢复（外部历史/待归仓路径：`../../build/wt-real-four-connection-diagnostic-003/real/PROBE-STOPPED.json`）已确认。原Journal摘要159b8746882b522f6329e8384f469c6fd38476069be9ab735c31b0065ac4adb1只读审计前后保持。真实下单/撤单0，其他策略变化0。

下一项为双端按每代Runtime、transport generation、binding及请求UUID摘要关联首异常、SDK进入/返回和显式close。新QA诊断在SDK普通主链及注入反馈中区分正常停源、Host本地断线、来源关闭及SDK报错，再独审后进行一次真实只读复现。当前不修改产品/WT框架或业务预算，不把后继成功写成旧故障已解决。

## 后继final1在启动来源前取消

新诊断准备final1已启动外部WT/Host及QST等待。模块自查随后发现入口context/thread保护的调用帧未被旧过滤器收录，决定在final2补齐；QMT临时探针始终未运行。根逐字恢复原文，再沿本次WT控制身份正常停止外部组件。

取消记录（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/final/real/root-operations/CANCELLED-BEFORE-SOURCE-001.json`）及只读Journal计数（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/final/real/root-operations/ZERO-BUSINESS-REQUESTS-001.json`）确认三库read_operations均0、交易库trade_commands为0。WT/QST均exit0、无强制终止、树0/EOF/join/资源完整；外层业务exit1与ConnectionRefusedError由根主动正常停止等待中的WT产生，不属于新增产品故障。原件保持，控制器终态（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/final/control-real/RESULT.json`）已核实。

下一次使用final2全新输入，不在final1已有Journal上重复启动。此次没有QMT策略启停、真实查询或委托，现有采集保持。
