# 较早开仓持仓的历史输入边界

类型：模块B接管根因与跨模块接口证据。状态：pending-verification。范围沿[接管方案](../migration/retained-strategy-takeover-proposal.md)及NRT-R24/R25；本项没有修改WT、算法核、行情生产者或金融账本。

用户后继决定：2026-10-30明确采用当前持仓作为新运行的初始库存，旧开仓时间、旧交易及旧周期状态全部不迁入。本文是被取消工作线的历史核证，保留观察原件；下文“必要接口与下一步”的旧周期补齐要求已由[当前初始库存方案](../migration/retained-strategy-takeover-proposal.md)取代，状态为superseded-by-user-decision。本模块后续不继续开发该旧周期恢复接口。

## 原触发和根因

根连续系统main003进入原CTA后返回opening_history_missing。B在普通WT安装python-003中直接调用原evaluate_retained，以同一A窗口、原参数和原数量policy只替换合成周期：空仓成功；510050持100份且2024-04-10上海10:00开仓失败；相同持仓在共同窗口首日开仓成功。完整八证券输入保持，三项共2.04秒，原核SHA为e72eeca05d5539d84b059bf965906d683c46b72f3c58a42aa6a6df7aead4a0d9；原件在build/ms-takeover-opening-history-001。

源端完整原生数据并未缺失。后继QA核原种子、QNA及当前纯核、原INPUTS字节身份，逐项核8,870对raw/front的同日期、OHLC因子倍率、量额不变和末日原价基准。七证券覆盖2024-04-10，510300基准历史亦存在；589000从2025-03-05开始，八证券交集只有401日。现行纯核要求共同矩形窗口，并在该窗口中查实际开仓日，导致已有历史被裁掉后无法恢复实际周期。

“原历史未下载”及“日期转换后原数据无对应日”的预测与本次来源证据不符；实际开仓日对应原数组日期20240410，同基准因子配对完整通过。本结论限定为已冻结来源和合成周期，不证明真实账户当前开仓时间。

## 实际命令、结果与资源

- 最小原核复现入口：tests/integration/qmt_cta_product/opening_history_boundary.py；驱动.tmp/ms-takeover-opening-run1.py，原QA副本及RUN/RESULT保留。Job根31248，exit0，原进程回收、树零、EOF、读线程join和资源关闭均通过。
- 来源核证入口：tests/integration/qmt_cta_product/opening_history_source.py；命令`python -I -B .tmp/ms-bounded-task.py E:/workspace/wondertrader/build/ms-takeover-opening-source-001 30 E:/workspace/wondertrader/build/ms-backtest-completion-001/python-003/runtime/Scripts/python.exe -I -B E:/workspace/wondertrader/tests/integration/qmt_cta_product/opening_history_source.py E:/workspace/wondertrader E:/workspace/wondertrader/build/ms-takeover-opening-source-001/RESULT.json`。0.322秒，Job根56492，exit0，原进程回收、树零、EOF、读线程join和资源关闭均通过。RUN/RESULT和精确文件摘要保留在同根。

所有新增项目产物与TEMP/TMP/依赖缓存均位于E盘。实际账户查询、下单、撤单和生产切换为0。

## 必要接口与下一步

C拥有实际周期规则及唯一纯核，需要交付能消费同基准逐证券历史的公开接缝；B提供原开仓周期和A已有raw/front/因子/来源事实。共同窗口的组合计算口径保持，实际周期历史补齐到相应开仓及预热依赖，510300基准依赖也需覆盖。原数学、角色信号机、持仓天数、参考峰值及退出记忆只保留一个实现来源。具体接口由C确定，需求与固定文件SHA保存在build/ms-takeover-opening-source-001/C-INTERFACE-REQUEST-001.json。

后续先接公开合同并重跑原触发，再用普通安装的Configured预检→同一CTA→原加载持仓→后继目标/差额→同根停止恢复验收。实际当前周期、成本口径与整个模块B仍未完成，其他账户/恢复及报告读取工作继续推进。
