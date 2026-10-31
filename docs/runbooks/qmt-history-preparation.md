# QMT历史补齐产品的安装与托管

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

运行所有权以[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)为准：HPR Host和缓存补齐由WT独立运行单元管理，观衡只读查询。[WT运行手册](wt-independent-runtime.md)说明统一入口，当前运行资格沿[WRI](../specs/independent-wt-runtime.md)及实际证据核实。

类型：运行手册。适用范围：[HPR5](../specs/qmt-history-preparation.md#hpr5-独立产品离线配对和系统托管)独立产品候选；真实终端启用沿操作者具体授权。

## 独立候选与身份

`scripts/history_preparation.py build`复用现有锁定Flit后端、角色安装器及native.run隐藏Job，只选择Host/Agent角色。产品自己的Windows CPython3.12依赖锁（外部历史/待归仓路径：`../../connectors/qmt_shm/history-preparation-registry.lock`）先按SHA取轮子，再由原安装器离线普通安装；App/C SDK锁保持。候选包含Host完整venv、所有轮子/许可元数据、requirements.lock、历史发行中的六文件薄适配及INSTALLATION.json全文件摘要，不包含私有凭据。

```powershell
./.venv/Scripts/python.exe -B scripts/history_preparation.py build --work <新的E盘候选目录> --python <CPython3.12绝对路径> --uv <uv.exe绝对路径> --backend <已核Flit3.12轮子> --seconds 600
./.venv/Scripts/python.exe -B scripts/history_preparation.py verify-install --source <候选>/installed --sha256 <INSTALLATION原SHA>
./.venv/Scripts/python.exe -B scripts/history_preparation.py relocate --source <候选>/installed --sha256 <INSTALLATION原SHA> --target <新的E盘搬迁目录>
```

离线构建额外给`--offline --wheel-cache <已有已核wheel目录>`。全部预算与工具绝对路径显式输入，构建不启动QMT。venv依赖其声明的CPython基础运行时；安装中记录运行时anchor，安装包不声称携带另一份独立Python标准库。搬迁按完整文件集合和摘要核验，保留原安装；新路径重新离线配对，旧pair的路径/配置身份不会被静默改写。

## 离线配对与核验

在实际安装解释器调用专用HPR工具；旧guanheng-qmt-shm CLI/v3配对继续服务其原只读合同。

```powershell
<安装>/host/Scripts/python.exe -I -B -m guanheng_qmt_shm.history_preparation_cli pair --config <私有Host配置> --quote-settings <QST配置secret省略> --quote-secret-env <QST独立IPC环境角色> --memory-sdk-manifest <目标3.6.8元数据> --stdlib-license <PSF许可> --reconnect-seconds <显式间隔> --output <新的E盘私有pair目录>
<安装>/host/Scripts/python.exe -I -B -m guanheng_qmt_shm.history_preparation_cli verify --directory <pair目录> --installed-agent <安装>/host/Lib/site-packages/guanheng_qmt_shm_agent
```

Host配置中的ipc_secret_env/http_secret_env指定原两种凭据角色：HPR IPC环境值沿原Host合同为十六进制，HTTP值为原字符串；QST第三个独立IPC角色沿原生成器合同为UTF-8字符串。两种IPC解码后均至少32字节，三个角色分开。值只在私有材料内出现，命令行不放凭据。目标SDK元数据含实际3.6.8解释器/DLL、Lib路径及builtin列表；配对/核验在QMT外读取这些声明原件和许可，不执行SDK。生成策略完全使用冻结内存及两个SHM映射。QST-only旧脚本仍可用，产品始终选择显式组合。

正式部署使用qmt.history-preparation-limits.v2，省略symbols；按来源支持的沪深证券接收单标的请求。周期、窗口、max_rows、max_tasks/max_queued、max_records及结果/控制字节额描述实际资源。既有limits.v1配对保留原签名范围，切换到新版时由产品配对工具生成完整新正文及Host配置。产品核max_journal_bytes完整预留max_records×(实际准入max_request_bytes+max_result_bytes+16384)，拒绝小于声明容量的配置。一次SDK调用及完整往返分别计时；io、queue、native和control期限应按已验场景配置，工程配置与真实资格分开。本模块不把16条、300kB或10行之类夹具值作为产品默认。

## 系统进程owner

父部署schema为qmt.history-preparation-process.v1，字段精确为schema、pythonw/pythonw_sha256、pair_directory/pair_manifest_sha256、installed_agent、control_root、startup_seconds、stop_seconds、max_output_bytes。pythonw来自该安装，控制根为已有私有E盘目录；配置本身也以原字节SHA准入。

```python
from guanheng_wt_runtime.history_preparation_process import HistoryPreparationProcessConfig, HistoryPreparationProcess
config = HistoryPreparationProcessConfig.from_path(config_path, config_sha256)
owner = HistoryPreparationProcess(config)  # config=None为disabled
owner.start(time.monotonic() + owner.startup_seconds)
state = owner.status()  # ready仅HTTP监听；来源另读认证binding
owner.request_close()
closed = owner.close(owner.shutdown_seconds)
```

薄适配只管理自己创建的隐藏Job和真实Host PID。HPR专用ready/stop/closed schema绑定控制ID、manifest/config SHA与监听；全部资源确认后才授正常关闭，未知资源仍由原owner持有。Host常驻等待来源，来源晚于60秒不触发整体退出。认证失效、正常断开与重新认证沿原恢复边界，未知补齐保留原ID，先回读核查，禁止自动重发或换ID重试。

独立WT实例在components.host选择kind=qmt_history_preparation，descriptor及sha256绑定上述部署。WT负责启动和停止Host，观衡按[只读观察手册](history-preparation-app.md)消费公开状态。历史组件中app_adapter等目录名属于其冻结安装身份，不表示观衡拥有运行生命周期。真实下载、账户、委托、策略切换及生产启用按实际授权和候选资格执行。
