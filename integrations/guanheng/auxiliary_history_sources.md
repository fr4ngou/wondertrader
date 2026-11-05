# 历史辅助来源缺口适配

类型：独立模块说明。状态：已实现，现场采用由运行owner执行。合同沿 [SDO](../../docs/specs/strategy-data-and-observability.md)；实现为同目录 `auxiliary_history_sources.py`，有限QA入口为 `scripts/auxiliary_history_gap.py`。

## 职责与来源顺序

本模块补充外部历史事实读取和原件校验，复用WT-D11来源适配边界、AWP官方解析及策略唯一辅助派生。行情存储、原生Reader、持续采集、策略规则与金融状态继续归原owner。

优先核国信QMT内置数据及既有缓存：`get_market_data_ex`的已核日线amount属于对应证券；`get_etf_info`出现在本机API索引，当前证券资料的`TotalVolumn`/`FloatVolumn`属于快照。ETF历史总份额、全市场股票成交额及全市场融资余额的字段、单位、日期参数和覆盖仍由Root的官方API/现场只读核验给出。当前资料不授这些历史事实资格。原已下载股票数据保持只读。

旧QMT工程有交易所历史原件归档，可以离线复用；其来源仍为交易所。`import_legacy_archive`只复制当前种子缺少的深交所原件，核v3封套、固定官方URL、统计日、HTTP状态、正文SHA及原字段，不加载旧服务和旧交易模块。旧项目的09:25等历史知晓假设保持原位，本模块使用新的实际导入上界。

当前来源优先级为：已有AWP官方缓存 → 旧工程已核官方归档 → 显式提供的官方年鉴。后续经Root验证的QMT原生来源由所属采集owner接入。第三方材料单列研究流，默认官方事实包过滤全部`research_only`。

## 接口与单位

- `read_official_capture(root, source, day, symbols)`：只读核AWP回执和压缩原文，复用其唯一解析器。
- `import_legacy_archive(root, seed, days, output)`、`read_legacy_manifest(manifest)`：独立导入与后续无旧工程依赖的原件回读。当前种子和旧根均保持只读。
- `read_yearbook_facts(bundle)`：核官方PDF与坐标提取身份，主板和创业板每日股票成交额相加。各分表精度0.01亿元；与官方总表可有0.01亿元尾差，已有接口值保持优先。
- `load_facts(..., legacy_manifest=..., yearbook=..., research_margin=...)`：按来源/日选择事实；当前官方缓存的同日异值修订要求owner解决。
- `publications_from_facts(facts, days, research=False)`：返回`PublicationBundle`；其`publications`为原`AuxiliaryPublication`，由开发者1对接唯一派生和AWP发布。

`SourceFact`声明旁有各字段中文定义。份额为亿份，成交额/融资余额为亿元，保持十进制文本；`received_at`为当前owner实际取得上界，`origin_received_at`单列旧工程原采集时间。日期、单位、数值、原件及两个时间共同参与身份。旧原采集时间不把新WT的可知时间提前。

## 验证与消费边界

有限作业输出逐来源/日期的应有、种子/补齐可读、规范值、原件SHA、知晓时刻、公开事实和数值派生可用性、真实缺口。原五来源齐全天数与逐来源覆盖分别报告。原公式由`guanheng_strategy_v1.auxiliary`执行，适配器不重写信号规则。

补采发生在历史收盘之后时，原历史行继续为空。原始统计值、可计算的分位以及真实逐时点可用性分别记录；历史首次未知始终保留未知，不填零、不推定历史首次发布时间。

年鉴PDF和第三方响应的原文保存在受控QA目录，不随源码提交或对外分发；数据展示的可读性与重新分发许可分别登记。第三方融资余额即使与官方重叠期一致，也保持研究资格。采用、历史研究重建和当前WT交易输入由各自owner声明。

## 操作与回退

`python -B scripts/auxiliary_history_gap.py --help`列出离线入口。运行时显式提供已固定的辅助包目录`--dependency-root`，其余参数为原种子、窗口和独立输出目录。`--import-legacy`只读复制旧原件，`--build-yearbooks`由具备pdfplumber的独立工具解释器执行；运行消费者仅需标准库及原辅助包。

完整重现命令、真实覆盖、各原件摘要、固定安装及限制放在任务专属QA交付；Root合入时维护公共导航与现场配置。采用使用新安装及独立数据参数，原数据根/运行源码保持。回退撤回新增适配及来源参数，恢复原固定组合；保留原件与金融状态，不覆盖旧窗口或历史报告。
