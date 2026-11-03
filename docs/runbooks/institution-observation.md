# 机构披露与债券重估维护

类型：运行手册。适用范围：IMO-R24独立更新配置及其只读API/导出。当前开发资格见[证据](../evidence/2026-11-03-institution-data-continuation.md)，实际角色部署、自然窗口和版本由Root接收登记。

候选保留原30个来源ID和原基金、大型银行数值生产者；三处空目录检查改用数值适配：pbc.disclosures→pbc_custody只拥有bond.custody，wealth.disclosures→wealth_allocation只拥有holdings_wealth，fund.disclosures→citic_broker只拥有holdings_broker。基金配置与大型银行原生产者继续承担各自事实。新增chinabond.wealth→chinabond_wealth拥有source.chinabond_wealth，并声明派生bond.mtm45，候选共31路。

三类报告使用calendar-day，中债指数使用cn-closed-day；四路window_mode=report_latest、overlap_days=0，报告只追加原游标之后的真实期次。券商max_pages=4，允许1至8；固定URL及数据集归属由原配置校验器核实。保留原计划、总预算、其他来源和必要旧主机，补入www.cninfo.com.cn、static.cninfo.com.cn、yield.chinabond.com.cn的实际所需主机。Source/Data/配置CAS中的候选作为可审阅差异，Root按最新实际配置重放，不整份替换旧路径或发布孤立快照。

在已授权的目标根，复用原显式采集入口；下列变量由该次部署提供：

```powershell
& $AppPython -I -B -m guanheng_app.observation refresh --root $ObservationRoot --config $SourcesFile --config-sha256 $SourcesSha --as-of $ObservationDate --sources pbc.disclosures,wealth.disclosures,fund.disclosures,chinabond.wealth --seconds 600
```

先核回执的源期次、loaded_period、失败码及实际采集时间，再按同一snapshot_id读取series与exports。报告期、官网公布日期、源抓取时间分别看；no_new_observations表示当前游标之后无新增，不能据此把旧报告期改成当天。完整原行保存在历史快照；新增模型说明列在旧行为空，沿模块字段语义解释。

券商季度报告没有附注8债券分项时，保留最近半年/年报数值。理财的产品存续规模、投资资产总额及债券/存单分项分母各自保持。托管余额取全市场，不以中债单机构托管余额替代。报告格式或单位变化时保留旧数值与失败记录，再维护对应数值适配器；目录或新闻链接更新不能代替解析附件。

中债GET返回405时继续使用原官网已核只读POST，不据此判定数值不可取得。指数必须保持原新综合、CFZS、00，不能用全价/净价或其它指数续接。模型基准来自真实股债共同日期；源缺日留空，不重定旧基准、不插值。45自然日假定独立于真实披露时间，历史因果回测资格保持未知。
