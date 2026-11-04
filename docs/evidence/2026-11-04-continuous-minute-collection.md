# 2026-11-04 持续分钟采集候选

类型：验证记录。结果：partial。关联MCC-01至09。正式角色/Source尚未采用，当前记录只授以下实际构建、隔离及原运行只读事实。

## 输入身份

工作树`E:/workspace/wondertrader-worktrees/minute-collection-20261104`，基线`f8b90bdfcd8ee7db39e63739ed01eb2ece154862`。旧程序与当前原件保持；新产物在`E:/workspace/wondertrader-data/minute-collection-20261104-001`，QA根`E:/workspace/wondertrader-qa/minute-collection-20261104-001`。

唯一资料owner原件REFERENCE SHA为`e2b2e423b4cc2f2ec9f4c3ea937a0d3d157a987ff37f4bc841a2665494776fd2`。动态current消费实际得到同8013成员和原日历；source_as_of保持null，BJETF分母保持未知。当前SH/SZ已知7647；原6982中2项未在当前名册，缺667项。候选保留原2项，共7649；366个已知BSE成员在现有分钟准入外，单列不支持。

## 步骤与观察

| 实际步骤 | 结果及受控记录 | 证明范围 |
|---|---|---|
| 原标准Reader读取今日股票及ETF | 上午10样本120/120；后继公开形状读取最新30根 | 原活动Writer根的标准读取，不读取DMB字节 |
| 昨日缺口与源值核对 | 样本198至203/240；510300缺41根，恢复边界量额显著不同 | 仅补空白标签会重复计量，采用完整闭合日来源版本 |
| 原保留客户端→Importer→Reader | `mcc-final-001`实际240根、原ID重启接续、跨日470根/无重复 | 新构建DLL及同一原恢复机制；全市场尚未补齐 |
| 独立原服务HTTP | `http-readonly-001/RESULT.json`五样本今日最新、昨日240及正常关闭 | 查询不加载来源密钥、不提交来源请求 |
| 完整原生重建 | `E:/workspace/wondertrader-build/mcc003/BUILT.json`，212目标/79安装文件 | 原固定Git/依赖/19项既有批准覆盖；新桥不改框架行为 |
| 原15:05自然归档 | `NATURAL-ARCHIVE-20261104.json`，marker为20261104；11样本标准Reader与DSB文件ABI逐字段一致 | 多数238/240，159780为239，000001.SZ为240；完整性与归档分别记录 |
| 7649原生注册/QST/维护同运行 | `E:/workspace/wondertrader-qa/mcc-service004/RESULT.json` | 真WinSHM/原Native；SDK替身股票、ETF、双指数可读，正常关闭，原实例未改变 |
| 完整Source冻结与目标SDK冷验 | `complete-source003/SDK36-COLD.json`；完整正文SHA `75c19b3158aa553f17a5a9091d728dab7f580177facdfd833d691ed73900338d` | 真实3.6.8冷加载；单timer/四owner、启动失败及停止失败均回收；SDK调用为0 |
| 原HPR产品工厂配对 | `source001/hpr-pair`，完整Source的QST/HPR字段与原产品片段一致 | 配对/联合额度准入；原HPR/SDK未切换 |
| 原WRI独立角色 | `role-smoke002/RESULT.json`实际启动、HTTP分钟、正常角色/管道/进程树关闭；停止原子发布修正后的003另行复验 | 自有薄启动适配；原WRI/ManagedLocalProcess继续负责监督 |
| Source采用与回退 | `source-adoption-regression001/RESULT.json`，一次采用、幂等、回退及冲突保原件 | 隔离文件测试，实际GH正文未改变 |
| 根因回归 | `tests/integration/minute_collection`九项通过，原生fixture为`mcc-final-001/producer.json` | 完整日排除累计量重复、逐段metadata、日历摘要、合法float毫秒/坏批次不部分更新、停止文件关闭后发布 |
| 部分/空→完整、未知读取重启 | `test_partial_recovery.py`首轮200/240和0/240两场景，真实Importer及Reader最终均240条；原准备UUID不变、实际准备一次，未知读取重建后同UUID续核 | Source传输为可控替身；持久收据/Importer/Reader/最终选择为正式实现；不授真实断线现场资格 |

## 边界与后继

完整Source保留QST/HPR/v7/v8，移除无消费者旧交易owner/回调；独立账户交易/v9未修改。HPR新profile的rows2000/data262144与frame/result/control联合额度同批验证，原300000ms保留与prepare30秒保持。正式现有Source/Host仍未采用。

当前日原归档可读；原HPR分钟读合同拒绝当日，缺口由采集owner在该日期进入可读范围后接续。原HPR/来源、分钟存档、整日完整性、价格单位与正式运行分别验收。Source参数、覆盖与恢复对象属于自有适配，不新建金融账本、行情数据库或系统定时任务。

首次full独立评审分别发现部分来源停止后继、停止文件提前可见两项P2；当前修正复用原有界follow_up，控制收据先关闭临时文件再原子换名，delta复核继续。原生fixture回归用锚定CPython3.12执行`-B -m unittest discover -s tests/integration/minute_collection -p 'test_*.py' -v`，显式`MCC_NATIVE_FIXTURE`；省略fixture时原生场景跳过，跳过不授通过资格。

本工作树`project.py check`报七个基线缺失链接：股票资料覆盖材料及security-search六个UI文件。它们未由本模块改变，最终主线合入后需再核完整正文。最终源码提交、固定最终包及Root正式切换/公开18136与页面验真继续，整体目标active。

诊断输出事件及整改保存在QA根`DIAGNOSTIC-OUTPUT-INCIDENT.md`，Root已接收无值说明；凭据和运行处置由原维护者统筹，工具记录与本地文件管理分别核定。
