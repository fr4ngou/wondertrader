# 日线发布滞后与行情连接恢复

类型：运行与根因验证记录。核实时间：2026-11-05北京时间凌晨。范围：独立WT的数据角色及观衡18143；交易角色保持原运行代。

## 用户症状与根因

300308.SZ日线停在11月3日，股债差已到11月4日，叠加的上证指数11月4日缺值。当前时刻尚未开盘，最新闭合日应为11月4日。

上一轮Source维护后的采集、日线角色尚未恢复。恢复外部服务后，QMT原GH_WT_MEMORY_VERIFY实际界面显示停止；本轮仅启动该原策略，QMT_METRIC_GATEWAY及原交易策略保持。WT随后建立第1代采集连接，收到7579证券及持续心跳，实际报价尾时刻为11月4日收盘。

日线任务的5612项HPR调用均已返回。后续批读已完成278批，原capture的binding仍固定到旧Host/运输代。认证当前metadata后确认仅host_instance_id和transport_generation变化，完整业务身份相同；原严格检查阻止尚未创建的下一槽，因此11月4日迟迟未发布。

## 实现与实际采用

自有DailyBatchAnalysisSource复用原分片、SDK请求及manifest，在SDK实际取得新槽metadata时核同一业务来源并先保存read-generations。原REQUEST、BINDING、slot、已知结果与未知身份保持；已有槽同时核binding/profile/limits。普通股票和全类别价格的cache/readback均接入，通用SDK及WT框架无新增修改。规则见[UDI-R49](../specs/qmt-source-daily-history.md)及[ADR-0027](../architecture/adr/0027-daily-batch-transport-generations.md)。

- 采集：minute-adoption-20261104-001/program007、configuration007、data-owner005；WRI ae4b004a，PID26572，collector37204，history44000，HPR15564。
- 日线：同根program009、day-code-update008；WRI 8c517e76，PID4932，history444。程序清单SHA728bd9b36a5f0b5f024aabd5b21d54cb5227e30bff35fc25463aad5cd12dcc06；service SHA8fe47d4b72b5bd0073f59c18751e61a1c6db1a38363c4bdd97443d51c38cfa23。
- 原daily配置SHA2d4388473eb782a53960e2ce04d166b30e75d3e3046460cb484202b3ffd9c67f、原11月4日任务与REQUEST保持。
- 观衡App110/SDK17保持，只更新只读实例目录并按同profile正常重启；最新Web PID67260。交易WRI25080/Native49784及报价角色40572/48952保持。

## 验证结果与边界

实际原任务批读从278推进至287，最终508批全部完成，manifest已生成。转换产生941910行、139602857字节输入，原生11154项输出随后全部完成（11142写入、12复用）；任务已进入prices阶段。该结果证明股票回读及原生落盘恢复；11月4日正式CURRENT发布及页面尾日仍待ETF/指数价格阶段和后继实际结果，不能据此声明当天已可见。

真实红绿回放BATCH-RESUME-REAL008：同一旧BINDING与两笔已consumed原槽，原BatchAnalysisSource在下一新槽复现绑定变化拒绝；新适配完成4批、跨2通信代，read_capture完整校验通过。旧BINDING和两笔原结果字节摘要保持，未产生金融命令。原始证据在E:/workspace/wondertrader-qa/minute-adoption-20261104-001/BATCH-RESUME-REAL008.json，源码SHAa03ae20429eaf7e9be1842c3843e0ef078c0210a8232f45305c712f8eb519e43。

独立delta审查两项发现已修正并静态复核complete；真实接口验证与静态审查分别登记。既有HPR预检与实际准入间限额变化的窗口未由本次批读修正改变，当前5612项均已返回；后继按实际风险单独处理。两项分钟指数公开读取、北交所分钟范围、统一日常启动及确认无引用清理继续保持未完成状态。

既有模拟下单、查询、成交、撤单验收见[原实际记录](../releases/2026-11-04-source-reference-and-clean-stop-live.md)。唯一1.2.1策略当前仍等待开盘市场输入，自有策略分析已到11月4日；其首次自然计算与执行结果继续按实际发生登记，不重复宣布整条交易通道尚未验证。
