# 真实行情与正式CTA混合组合开发验证

类型：验证记录。状态：完整限定主链开发验证、独审与本地搬迁交付通过。范围：[QRC规格](../specs/qmt-real-market-cta.md)。本轮产品/WT/SDK/B核心及已有QA源码保持原字节。

## 主链与身份

`build/qmt-real-market-cta-001/main006`实际普通安装Appa10/BUILD005受管Python入口，加载Runtime `241cdba18271b4c9a3800efdb97a2750b30326c571554fb3cf86125a5445ffcd`、Reader `f5f7efecf0648c425d4c7d85f217ea670be372c95465f07081564b5db30da122`、Parser `2d422159b21647fa18feed0e3020c735033502e8bbf40bd346b9c53c7bf6c059`。真实GH090正文SHA `6be3b6e5d9b41fc6861b40972192e31d7aae72bc73933ca65bddad7ed0a9b89b`保持，137/140继续原唯一采集。HPR e独占新pair/Journal，仅full_tick；无独立报价流消费者、UI操作、真实账户/交易/下载或生产切换。

原ticker自然14:36、14:37调用两个configured策略，真实原价格进入原NSQ，A/B各1700股，原组合净额3400。原执行器拆2000股@4.115与1400股@4.114；独立SDK账务替身按原入口原数量/价格回报成交，累计成本13989.600，18次查询及后继原调度收敛。新QA没有固定700/1400或10.01通过条件。

源码、输入和全部原件由该目录`INPUTS-main006.json`及最终`DELIVERY.json`绑定；原运行版本QA快照与SHA一致，停止后的验证修正另有新源码身份。实际安装位于main006/installed，实际宿主closed/ok、父closed/pending=false/forced=false，采证源及原生进程全部终态。

## 事实对应与离线验收

原停止后Helper读取的六份初始化/闭合bar与同次回调逐date/time/OHLC/量额相等，完整Helper副本和trace各有SHA。原上下文主m1闭合价也会成为策略原价；main006首轮510300 basis为真实闭合bar close 4.118，原报价终态为4.114/4.115/4.116。原QA强制全部basis来自full_tick，因此业务与停止成功后，外层exit1；该原件完整保留。

停止后的`verification-001/RESULT.json`沿同一运行原件完成离线正确核验：策略basis分别对应真实full_tick或同次Helper主m1 close，原执行入口价格对应已经完成的full_tick终态；完整经济核与NSQ outcome独立重放完全一致。56项引用检查含前代投影重复，其中52项tick、4项main-bar；不将引用次数写为独立报价数量。离线Job exit0、tree0、EOF、join、资源关闭，新增来源请求0。

`verification-003/RESULT.json`以只读原件完成最终离线复核：冻结首次时钟换算，输出到新目录，逐字节重现原`quote-basis-proof.json` SHA `7650c524b8efa3b035b86a3d3fca08832887def0d2b90730690c25d16212e0d8`；另独立核实10个唯一请求全有成功终态、每个原生终态的SHA及逐证券quote-values由原生正文重建完全相等。原B投影的价格source文字仍沿原替身夹具，真实来源归属由该逐项市场原件证明明确标注；原投影保留原字节。

真实读取累计21次（main004 11、main006 10），其余失败在实际请求前结束；最终Journal容量13、8秒轮询/每轮一批三证券、100秒运行预算，来源原profile的准备任务上限32保持。每条原ID、原请求/终态SHA均保留，真实操作集合仅full_tick；Unknown沿原实现认领，新增POST重发0。

`BOUNDARIES.json`独立纯模拟账务验证拆单/查询/成交数量与金额，拒绝重复ID、错误手数/负值/NaN/资金不足/方向/标的/错误线程八类输入且状态保持。边界测试不构造Host/CTA/Agent，不调用来源或真实SDK。

`relocated-001/RELOCATION.json`核实实际普通安装清单51项逐字节搬迁相等，Runtime/Reader/Parser导出加载及卸载成功；工厂/运行入口调用0、来源请求0，独立Job exit0且资源关闭。该证据覆盖搬迁文件及加载身份。

独立full审查`REVIEW.json`的Standards/Spec及QRC1～4均complete，未解决问题0。审查定位并关闭一项P2：原QA在源线程启动并完成ready/secret解析后才注册关闭责任。最终`start_owned_source`在start前登记原owner，以输出根下独立stop-file支持ready前停止，并在stop写入失败时仍沿原ThreadOwner取得join；未知join保持失败。`SOURCE-BOUNDARIES.json`七个纯owner窗口通过。审查者用最终源码在`review-output/verification-final`完成新增来源0的独立离线复核，exit0、tree0、EOF/join/资源关闭，basis证明SHA完全相同。该修正的真实Host/CTA运行次数0，原main006事实和退出码保持。

## 证据边界与后继

main001解释器core版本声明、main002/003/005有限Journal联合配置准入以及main004原QA事件页512上限的失败原件保留。main004也形成1700+1700及两笔真实价格入口的模拟成交；main006将独占QA采证上限事先声明为有限8192请求/2048页，生产额度保持。

日线125天、预算、券商资金/成交与费用仍为显式替身；价格原生上下文与实际主m1数据分别标注。实际原生closed成功与外层QA exit1分别登记，离线修正验证不伪造新的真实运行。真实日线、柜台现金/T+1/费用、当前完整App组合与全真实策略资格继续由根集成验收。

最终源码/规格/依赖/原件清单及两个本地包由`build/qmt-real-market-cta-001/DELIVERY.json`绑定；QA包保留明确白名单，原private凭据/pair/Journal/运行配置及原市场正文留在本地受控原件。实际普通安装的51项文件另有搬迁包。当前`python -B scripts/project.py check`通过；共享索引由根集成，本模块保持只读。15:05原归档及15:18原关闭界限保持，后续验收继续只消费已保存原件。
