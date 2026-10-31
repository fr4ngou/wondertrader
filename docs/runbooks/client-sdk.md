# 独立行情客户端发行


## 0.15 来源分钟的最近N根与部分范围

0.15.0支持[RS13](../specs/qmt-source-history.md#rs13-最近n根选择有限尾窗与分段来源)的来源选择响应。原source_history_query请求保持exchange/code/from/to/limit；from/to是允许选择的闭区间，limit选最近最多N根，补数预算由显式source-preparing服务配置拥有。离线source-store/source-stores/source-catalog继续只读已有数据，SDK自身不增加下载循环。

成功data可能带observation，调用者读取state、source_window、selected_rows及preparation_state，区分已有库存、实际回读与Partial。Ok表示返回值通过契约验证，coverage=Unknown仍不证明完整范围；原download返回CallReturned也不能作为数据已补齐的证明。

跨根选择的data.provenance按offset/count连续覆盖每根bar，各段metadata保留原source、内容身份、单位与边界。集合metadata.source的kind=SourceSelection，只有provider和selection_id；不要假定它有统一instance_id/session_id/generation。单根响应和旧日线/canonical接口保持原形状。SDK校验分段与内容摘要，业务展示和策略仍须保留这些来源事实、部分范围与未知单位。

含observation/provenance的新服务须配套支持该响应的SDK及应用依赖，旧严格客户端会拒绝未识别字段。安装核对wheel摘要、声明版本和消费者依赖；包版本与guanheng.market.v1协议名分别记录。当前可用候选与资格见[模块A交付](../migration/module-a-delivery.md)，全系统激活和交易资格沿各自验收。


0.14.0新增显式源日线查询，详见[DSH4合同](../specs/qmt-source-daily-history.md#dsh4-统一公开查询与目录)。调用已构造的MarketClient：

```python
result = client.source_daily_history_query({
    "exchange": "SSE", "code": "510300",
    "from": 20211101, "to": 20261027, "limit": 2000,
})
```

日期/证券均为示例，实际范围由调用方提供。先检查status再读data；成功返回metadata.period=1d、timestamp_semantics=source_date及原source/单位，bars使用YYYYMMDD整数date。coverage=Unknown和空missing_dates不代表区间完整；00:00来源日期不授当时可获知完整收盘数据。原source_history_query仍读取12位minute分钟标签，两种接口分别选择。

同一SMP服务的source-catalog显式配置可绑定分钟及日线成功store，按证券+周期路由。目录预载使用symbol/period对象列表；原source-store(s)配置与字符串分钟预载保持原合同。能力页的目录集合身份与逐证券原始source分别使用。日线来源/单位/完整性及生产配置切换按独立实际证据准入。


0.13.0新增标准库本地运行状态模块`guanheng_market_client.runtime_status`。`read_status(path, max_bytes=65536)`保留原JSON返回；`read_status_snapshot`同时返回同一只读句柄的JSON值与文件修改epoch纳秒，Windows共享读/写/删除和原子ReplaceFileW继续沿唯一实现。`guanheng.collection_status`仅兼容转发到同一模块对象；App0.1.0a4精确依赖SDK0.13.0，采集组件同时携带同字节SDK闭包。模块读取本地受管状态，不查询证券、不启动服务；调用者负责实例身份、发布时间时效、原业务截止及当前owner运行状态，见[OPS规格](../specs/operations-workspace.md)。

0.12.0按照[网络截止规格](../specs/client-transport-deadline.md)增加`connect_ip`关键字。HTTPS域名必须提供显式数值连接地址；原域名继续用于Host/SNI和证书校验。旧域名配置缺少映射时在构造阶段拒绝，数字回环HTTP原配置兼容。TCP、TLS握手、发送和读取共享绝对剩余预算，SDK不运行后台DNS。同步SSL信任材料初始化和本地CPU工作只能前后判超时，不能抢占任意OS阻塞。

0.11.0沿原`MarketClient.history_query(request)`增加[NQW窗口选择器](../specs/native-history-window.md)。调用方显式提供from/to、period_minutes和可选limit，服务端原Reader/Factory负责最多根数和周期；客户端只校验选择器回显、时间、数量与来源。图表最多N根与原策略精确覆盖窗口分别使用，不能把短历史响应当成策略完整输入。该SDK的安装及实际原生服务资格见对应证据，版本升级本身不代表生产生效。

类型：运行手册。适用范围：观衡独立消费者安装与构建，无账户或交易操作。

客户端的唯一实现为 `integrations/guanheng_market_client`；旧导入路径仅作兼容转发。独立 wheel import 为 `guanheng_market_client`，基础客户端使用标准库，无 WT DLL、wtpy 或 QMT 源码依赖。0.5.0 新增[权威分钟计划消费者](history-calendar.md)，保留 0.4.0 的受管 history_worker；MinIO 证据适配使用可选 storage extra，基础导入不加载第三方 SDK。接口遵循[HTTP 行情](../specs/qmt-http-market.md)、[历史生命周期](../specs/history-lifecycle-and-service-adapters.md)、[证据存储](../specs/history-evidence-storage.md)、[独立执行](../specs/history-worker.md)和[日历消费](../specs/history-calendar-projection.md)规格，包版本与协议版本分别核实；实际资格与制品身份见 CURRENT。

在具备受管 Python 的开发环境执行：

```text
python -B scripts/client_sdk.py
python -B scripts/client_sdk.py --offline
```

首次构建下载 `config/python-build-dependencies.json` 固定的 Flit backend wheel 并校验 SHA-256；backend 在隔离解释器中从已验证 wheel 运行，不安装到全局环境。默认依赖缓存、临时文件、制品与收据在构建根；offline 缺失缓存或摘要不符明确失败，生成物不覆盖既有发行目录。

源码文件由同一 lock 的 client_sources 显式登记。构建前后完整枚举客户端目录，拒绝未登记材料、链接和构建期间增删改；wheel 内源码和许可证逐字节比对，生成元数据范围另作校验。receipt 保留源码、backend 与 wheel 摘要，发布 owner 核对这些身份后才能选择安装制品。

0.8.0增加[历史部署工厂](history-deployment-factory.md)，由受管环境配置组合原Operations、行情、日历和MinIO证据客户端。运行入口沿既有history_worker，作业状态/CAS和来源事实所有权保持。构造零请求、实际调用链及发行资格以对应验收记录为准。

0.9.0增加[受管分钟worker](minute-worker.md)：`minute_owner.py`、`minute_worker.py`、`minute_factory.py` 随显式清单发行，基础模块仍仅依赖标准库。来源扫描具备独立until边界，空权威范围可以确认；MarketData负责持久收据和游标，worker按公开HTTP恢复。分钟工厂复用storage extra获取原日历存证。SDK wheel安装、实际业务接纳和生产部署分别取得资格。

storage extra 复用观衡已锁定的 minio==7.2.20、urllib3==2.7.0；构建仅允许 lock 中显式登记且带对应 extra 条件的 metadata 需求。任何无条件依赖或未登记 extra 均拒绝。部署方从受管索引/制品库安装并锁定完整运行环境，例如对已校验的 wheel 使用 `python -m pip install "guanheng_market_client-0.9.0-py3-none-any.whl[storage]"`；此操作由部署环境执行，原生打包不修改开发全局环境。

采用 PyPA [Flit 标准 PEP 517 backend](https://flit.pypa.io/en/stable/pyproject_toml.html)，固定版本/摘要来自[第一方 PyPI 元数据](https://pypi.org/pypi/flit_core/3.12.0/json)。公开发行前仍需发布 owner 确定索引与发布身份；当前分类 Private、没有上传操作。

原生 `native.py all` 会为最终源码生成独立 SDK，将 wheel 放入包内 `clients/`，在全量/搬迁包链中安装到独立目录，再以 `python -I -S` 的独立进程实际调用行情服务。该进程不加载仓库、私有 QMT 模块或原生 ABI；源树/搬迁包输入与 SDK 内容均由清单/收据记录。

观衡独立服务安装经制品摘要验证的 wheel 后使用：

```python
import os
from guanheng_market_client import MarketClient

client = MarketClient("http://127.0.0.1:8765", os.environ["GH_MARKET_TOKEN"])
status = client.capabilities()
```

地址为示例；跨主机入口使用受管 TLS 及网络验收。客户端拒绝未知版本/字段/缺项响应，保留明确 Pending/Unavailable 与来源资格。新任务动作包含创建实例 queue_id 和临时 task_id，恢复先查 DSB，任务编号不进入持久业务账本。

HTTPS配置示例（虚构地址，须由部署所有者替换）：

```python
client = MarketClient("https://market.example.invalid:8443", os.environ["GH_MARKET_TOKEN"],
                      connect_ip="192.0.2.10", timeout=4)
```

同一`connect_ip`关键字适用于ReaderClient。history_factory的market及minute_factory的sources[]允许可选connect_ip字段；它们的Operations/Calendar/MinIO等独立传输继续按各自规格验收。IP变更由部署配置更新，不在SDK内部自动解析或重试。

## 可选的原生逐日回放能力

需要[原生逐日窗口](../modules/qmt-native-adjustment.md#每个交易日的回放窗口)的部署闭包同时选择 `guanheng-market-client==0.15.0` 和 `guanheng-native-analysis-core==0.1.0a2`，使用 Python 3.12+。发布方锁定两份 wheel 的摘要；保持基础 SDK 原件，core 提供原回放实现及薄公开入口。单独安装基础 SDK 继续使用原行情能力。

构建 owner 调用 `scripts/native_support/native_replay.py` 的 `build(...)`，显式提供旧 core wheel、原回放源码、公开转发源码及各自摘要和独占输出目录。构建器核对既有代码原件并产生新的 a2 wheel，不改写已发行 wheel。安装方把两份校验后的 wheel 放入离线 wheelhouse，使用受管 Python 安装固定版本并执行 `pip check`；实际候选身份见[安装证据](../evidence/2026-10-30-replay-installed-api.md)。

```python
from guanheng_market_client.qmt_native_replay import ReplayCatalog

# 目录及摘要由该次冻结回放目录的交付清单提供。
catalog = ReplayCatalog.open(catalog_directory, manifest_sha256)
window = catalog.window(catalog.dates[120])
```

`open` 校验目录并持有纯值；后续 `window` 返回独立容器，读取期间不启动 Host、QMT、网络或原生子进程。该安装资格覆盖回放资料接口；逐日策略执行、回测比较和最终运行包分别验收。
