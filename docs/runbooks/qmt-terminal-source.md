# QMT只读HTTP连接包历史构建与验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

状态：历史保留，当前交付路线已退役。以下终端HTTP构建、配置和运行步骤只解释截至2026-10-22临时验证的旧来源；后续不新部署、不优化、不作为共享内存回退。当前受支持的终端操作见[国信QMT操作手册](guosen-qmt-operations.md)，新连接包见[SHM说明](../../connectors/qmt_shm/README.md)。终端外Host提供的认证HTTP属于新SHM接入的外部接口，沿其独立契约；它不恢复终端内HTTP。原历史正文及证据保留各自来源资格。

类型：操作手册。适用范围：本仓库拥有的`guanheng-qmt-connector`分发、隔离验证和显式终端接线。行为要求见[QTS规格](../specs/qmt-terminal-readonly-source.md)，来源、线程和状态见[模块说明](../modules/qmt-terminal-source.md)。

## 构建与输入检查

在本仓库开发环境执行：

```powershell
python -B scripts/qmt_connector.py --work build/qmt-connector
```

构建机使用现代Python和仓库锁定的flit_core。工具核对分发白名单、逐文件来源摘要和全部祖先的symlink/Windows reparse状态；拒绝未登记资源、来源摘要漂移和目录重定向。构建前后再次核对输入。终端实现按3.6语法和标准库导入检查，wheel元数据声明Python 3.6.8及以上、零第三方运行依赖。

每次构建写入新的`artifacts/<唯一标识>`，保留wheel、源ZIP、构建日志和`receipt.json`。核对wheel实际文件与声明逐字节一致；源ZIP包括策略入口、手册及来源清单。`python36.runtime_verified=false`只描述构建阶段，真实解释器证据由后继验证单独提供。缓存已准备后可加`--offline`构建。

## 分层验收

1. 使用本仓库测试环境运行`tests/integration/qmt_terminal_source`的runtime、operations、packaging和HTTP测试。传输测试使用真实回环TCP，供应商对象是明确的合成替身。
2. 从新安装位置或wheel运行`python36_probe.py`，显式传入`--package-root`和`--output`。实际3.6.8解释器使用`-I -S -B`；验证实际导入位置、签名HTTP、owner调用、原ID认领和关闭。该探针仅调用合成SDK，独立解释器成功不授予QMT策略装载资格。
3. 对原生整链，向`run_native.py`显式提供`--probe`、普通生产`--library`、`--cwd`和新的`--work`；源码模式另传本仓库`--source-root`，安装模式从已安装包导入。必须使用匹配的原生制品身份。实际DLL/QRT/原Adapter及v2值接口与模拟SDK的资格分别记录。
4. 真实终端接线另核账户环境、现有监听、安装位置、配置与凭据引用、策略线程和关闭入口。读取真实已下载缓存以及真实账户数据后，分别核对字段、空值、时间与来源；安装或切换动作采用具体操作方案。

验收记录包含当前产品、测试、构建工具及制品摘要。仅复用输入匹配的证据；源码改变后重验受影响层。测试中的临时端口和合成账户不能复用为生产配置。

## 终端配置与运行

配置结构和示例以包内README（外部历史/待归仓路径：`../../connectors/qmt/README.md`）为唯一正文。由操作者显式设置`GUANHENG_QMT_CONFIG`绝对路径与签名秘密环境变量；包不搜索旧业务仓库、`.env`或账户配置。策略入口为`GUANHENG_QMT_HTTP.py`，其导入只注册回调；`init`创建服务并注册有限pump，`stop`由原策略owner结束资源。

服务仅绑定IPv4回环字面量，默认端口18010。端口占用使初始化失败；配置新的受管监听或切换现有监听须明确双方owner。构建工具不会安装、加载策略或重启终端。

停止时先关闭准入，再失效策略绑定和排队请求，最后核实HTTP线程join与监听回收。`close=false`表示资源仍在关闭，调用者保留实例与依赖并按同一owner再次关闭。客户端超时后用原ID取得结果；源重启丢失的内存身份返回未知，不能据此推导交易是否发生。

本包只读，当前提供账户四查询、快照和已下载1m缓存。共享内存、交易和连续push分别按其功能规格验收。
