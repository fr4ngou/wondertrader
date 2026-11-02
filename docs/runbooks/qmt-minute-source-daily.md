# QMT分钟来源日线的准备与接线

类型：操作手册。范围：已导入QMT分钟仓的只读聚合与WT来源目录。合同沿[QMD](../specs/qmt-minute-source-daily.md)。

1. 校验当前分钟仓成功收据和原Helper/Reader摘要。显式选择symbol/start/end，有效目标按既有指数发布资料登记；输出父目录需存在。
2. 在已集成本模块的开发源码根，使用Python3.10+执行：

```powershell
python -B -m integrations.guanheng.qmt_minute_daily `
  --configuration '<本次绝对配置路径>' `
  --output-root '<尚不存在的新日仓准备目录>'
```

配置必须包含schema=guanheng.qmt-minute-daily.v1、minute_store、receipt_sha256、native_reader/library/sha256、helper/library/sha256，以及selection数组。库路径和摘要取自已验安装清单；日期使用ISO格式。源码运行的Helper/Reader依赖沿原安装，不加载QMT SDK。失败后核查本次目录，再选择新根重试。

3. 检查RESULT.json、PROVENANCE.json及store/qmt-import.json。逐证券核对目标、首尾、排除日和缺失标签。unknown单位、覆盖及可获知时刻分别保留。
4. 使用原source-catalog注册新日仓。接续已有完整source-collected配置时，先清点原base和supplement的所有日线路由；当前000300.SH/000016.SH已有2004/2005起长历史，保持原owner，只将其它48项的新仓加入base。新旧日仓逐证券互不遮挡，原分钟、9ETF日线、collection和补充仓保持；禁止用短聚合仓覆盖这两个原日线owner。002的source-preserve-existing-final.json给出该接线候选，原较老年份逐值及metadata一致性另有证据。
5. 通过原guanheng_wt_runtime的history/source_market描述启动新隔离WT，核全部50指数的日期/六字段/metadata，以及原股票、ETF、分钟查询。完成后用本代stop.json正常关闭，要求WT exit0及history server/native closed。
6. 生产切换前由集成者核对CAS、当前source配置SHA、完整旧来源闭包及独立审查。固定安装在新目录；按受控发布流程重新绑定source/service/descriptor摘要与新控制身份。候选配置使用隔离端口，其成功记录不能直接作为18136生产上线证明。

观察价格适配变更通过正常App及独立更新角色构建交付。已安装服务源码、当前fd94及调度owner保持原件。新日仓为静态冻结批次，后续增量重新生成新根并按显式配置接收，不回写本批原件。

002提供tool-bundle.zip，含固定Python源码、WT原生DLL/许可证和原50指数分钟DSB/metadata/收据，MANIFEST.json逐文件绑定。解包后用Python3.10+在任意工作目录执行以下命令；入口只导入包内runtime，使用标准库与包内原生依赖，无Root源码和qmt_local_dat导入：

```powershell
python -I -B '<解包目录>/run.py' --output-root '<新的绝对输出目录>'
```

默认处理全部50项，--symbols可选固定清单的子集。入口将配置保存为输出目录的同名.configuration.json并要求它尚不存在。该冻结工具用于显式离线准备，不提供持续调度。

现行8指数replace_tables来源按旧表日期完整覆盖准入。002相对fd94仍有7项缺历史日期，当前8项同一来源批次会保留全部原表。可用路径为独立只读WT价格查询；需要更新原观察表时，应取得完整原表日期的新来源，或在明确来源配置变更和原预算检查后将已通过日期覆盖的沪深300作为单证券批次接收。其余7项继续保留原表；跨来源按日期合并及量窗口分段需要独立规格，当前流程保持原完整替换规则。
