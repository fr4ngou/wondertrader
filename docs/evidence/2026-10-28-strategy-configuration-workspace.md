# 策略配置版本、共享文件IO与V2发行profile

类型：开发及隔离安装证据。日期：2026-10-28。状态：主链及专项回归已验，统一独立评审由模块C执行。范围：[SCW](../specs/strategy-configuration-workspace.md)、[NVB-R5](../specs/native-v2-backtest-session.md#nvb-r5-受管安装及验收)。使用隔离合成输入，未访问旧QMT、真实来源或交易入口，未发布。

## 根因及实现

原策略入口只组合回测，保留策略参数缺少App配置版本所有者及用户保存链。新增StrategyWorkspace配置tab、封闭DTO、正式HTTP路由及StrategyConfigurationOwner：选择resonance-regime-v1@1.2.0 configured，查看预算、预热、有效期及信号/执行映射，调用唯一核校验，保存版本/CAS回执并重读。回测tab组合原BacktestWorkspace。

core a6公开validate_configuration委托原_config唯一约束，算法1.2.0、数学和evaluate_history实际截止准入保持。内部结构合法性与当前有效期分别显示；2024年合成示例由用户主动加载。保存只产生App版本，运行激活及回测部署session另有所有者。

原PWL安全文件IO提取LocalDocumentIO，复用WindowsLease；WatchlistOwner继续拥有启动、串行线程、CAS、业务检查及恢复。helper只承接目录/文件身份、有限读取、临时写入/fsync/replace及自身残留处理；原_open_file/os/Path故障注入接缝保留。配置owner复用同一IO实现。

SST a3 pin core a6，NVT a2 pin SST a3/NFA a3，trace/pipeline仅同步发行常量，数学保持。Python和SPA消费同一v2_package_profiles.json；运行只接当前完整组，旧归档保留a5/a2/a1整组。strategy_session跨日稳定元组绑定core版本、真实core wheel SHA及完整dependencies，混代和同会话切代拒绝。

## 字段及持久语义

[SCW-R2/R3](../specs/strategy-configuration-workspace.md#scw-r2-dto与身份)是唯一DTO正文。HTTP前缀/v1/ui/strategy-configurations：GET工作区、POST /validate、PUT版本、GET /requests/{request_id}?store_id=…。写入沿ui_origin同源校验。浏览器仅提交业务configuration、store_id、expected_revision、request_id。

状态持久store_id、revision0..32及不可变回执；回执绑定request_id/request_sha256/configuration_sha256/configuration/saved_at。相同请求返回原回执，同id异内容或CAS失配409；未配置、维护、满额503。JSON/纯核错误固定中文，内部路径及异常留在私有原因。replace后结果未知503，跨tab保留原store/request，GET核查；absent继续未知，不自动重发。关闭在途保留原OS锁。损坏/残留原件保留并暂停编辑，32版本完整保留。

## 匹配验证

以下路径相对仓库根；日志、result.json及junit.xml保留实际输出。各组有重叠，不汇总为独立总数。

| 入口 | 实际结果 |
|---|---|
| build/strategy-configuration-main-001 | 正式路由及真实文件，空库→唯一核→保存/查询→关闭同根重启；1 passed |
| build/strategy-configuration-backend-003 | 568 passed /15.09秒；SCW规则/CAS/未知/容量/关闭，原PWL文件/OS锁/HTTP及core/SST/NFA/V2；早于profile扩展，SCW/sharedIO之后保持 |
| build/strategy-configuration-profiles-001 | 208 passed /11.59秒；新旧整组、混版/混SHA/混依赖及跨日切代，原V2软件层、报告和回测工作区；替身资格单列 |
| build/strategy-configuration-frontend-004 | 6文件81 passed /8.22秒；SCW API/组件/路由及原BacktestWorkspace/V2；私有缓存/单worker，模拟HTTP |
| build/strategy-configuration-typecheck-003 | 全console tsconfig.app通过，专有tsbuildinfo |
| build/strategy-configuration-packages-002 | 普通wheel安装，-I核模块来源/公开校验，原36项SST/NVT回归通过；与packages001所有.py/.json/.tzif逐字节一致，只有README描述metadata变化 |
| build/strategy-configuration-native-profile-002 | 新Python3.12 venv、锁公有依赖hash、App普通wheel/pip check；真实BacktestWorkspace→Host→原CtaMocker/Porter→V2→归档；第二-I进程读取新旧原件 |
| build/module-c-app-001/configuration-runtime/VERIFIED.json | 父作者实际CLI/HTTP/生产SPA：空库→唯一核→版本1/2→落盘后503→跨tab原request GET无重发→PWL保存→全CLI同根重启；exit0/listener关闭/reader_threads0/shutdown_complete=true |

目标Python文件ruff --target-version py312通过。复跑命令使用全新NNN目录：

```powershell
.venv/Scripts/python.exe -B tests/integration/strategy_configuration/validate.py --phase main --package-site build/strategy-configuration-native-profile-002/venv/Lib/site-packages --work build/strategy-configuration-main-NNN
.venv/Scripts/python.exe -B tests/integration/strategy_configuration/validate.py --phase backend --package-site build/strategy-configuration-native-profile-002/venv/Lib/site-packages --work build/strategy-configuration-backend-NNN
.venv/Scripts/python.exe -B tests/integration/strategy_configuration/validate.py --phase profiles --package-site build/strategy-configuration-native-profile-002/venv/Lib/site-packages --work build/strategy-configuration-profiles-NNN
.venv/Scripts/python.exe -B tests/integration/strategy_configuration/validate.py --phase frontend --work build/strategy-configuration-frontend-NNN
.venv/Scripts/python.exe -B tests/integration/strategy_configuration/validate.py --phase typecheck --work build/strategy-configuration-typecheck-NNN
```

validate.py沿scripts.native.run隐藏预绑定Job、180秒原截止、有限输出及整树回收。profile_native_chain.py提供prepare/run/read；run/read沿同工具在绑定候选python以-I执行。

## wheel与原生身份

最终普通wheel位于build/strategy-configuration-packages-002/wheels；packages.json绑定：

| 版本 | SHA256 |
|---|---|
| core 0.1.0a6 | 012d2d2fb456159781028ef01f12cf6a78d3b40aded02af40a824bf3f9c30312 |
| signals 0.1.0a3 | 6ff3c0b2d2d99d7af53bed7b92aa0e7ac3f2eaca88709d09aff729765d8e32e3 |
| v2 0.1.0a2 | b7d273301392a9d72b7524ee69eb2b18262ec7bcb2b3a24407fc6613baac3eb6 |
| variants 0.1.0a3 | 2d7f8d71b5e7cb1ecda68ac82ad208c73faefc0072728713e09c72996476806b |

native002的candidate.json、installation.json、app-source-sha256.json绑定完整源码/配置/site/运行时。此候选使用packages001，signals SHA=f4517a77365f5807ea85aa2e2165de8d0eec918f6a3cf550232f727331fa924b，v2 SHA=2375554b1babadbe5a4778db7327d97a23b4d8a9d4c7d2aa346c0076ce95c5dd；core/variants相同。packages002描述metadata变化单独登记，不改历史候选身份。

| native002其他制品 | SHA256 |
|---|---|
| App a6 wheel | bdbd1af09eca5987990bcb9ae072d3cc06a457bd0d10fa92dee3505ee22061c7 |
| SDK 0.13 wheel | a9826e42484c308fca719acc18e2f8f5fc5fad9869b38c043ee3be4df6508640 |
| NSQ a1 wheel | e75e80bd04c4c7088e2bfafef40e6c9de4d3fb772948b0f721eda159dda45310 |
| 原WtBtPorter | 4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e |
| 原ABI probe | a7fdb6ecd763ebdd395d4b0d11d78a1f6d30bbb57f23a63630c2410c243b71b6 |
| workspace.json | d8ab9fa0e444e53ff93dd69ac207eb76c194491d5b4dddf2e7fbd7814a5889b6 |

run/read-result.json共同核新run_id=0646a41485d3436d967e1ad41e690ba0、4记录、report SHA=3935b6606e86e354a17cd72aa0a5c2a9172341d3de4abc7f7de041c3dc221b74、receipt SHA=5e933374c9b7903f594703a1fb129a9fe9e4545a819f65a8f6b98abb745898d1；Host nonforced/exit0/pid_reaped/pipes_joined/owner_closed均成立。

旧真实归档目录build/guanheng-workspace/backtest-archive-runtime-002/roles/runs，run_id=07c3c728e98d4434bcd67af1852a9c46、4记录、report SHA=8c7f50547be5810cf57b3803a362de9ec8ffe6de6d9a3567b04f65943e28666b、receipt SHA=67e7f639161ffdb42762cfdfa9d399f005c9b8a3cc3a85d2d842d33d42b645b1。两次核旧目录逐文件SHA未变。

## 原失败及后继

backend001缺发行metadata在收集前退出；frontend001不适用cache参数在加载前退出；早期tsc共享Operations断言及本切片索引类型由各所有者修正，最终003通过。native-profile001复制旧venv依赖不完整在prepare失败、未启Host；002改为全新锁依赖venv完成。失败目录保留。

当前单版本配置主链及PWL影响链已验。统一独立review、所有保留策略、B正式激活/启停/运行事实、A真实完整日线、配置直接生成新回测session、账户/观察/比较报告及发布沿COP继续。B需提供配置版本与实际运行代际的接收/拒绝/查询事实；A需提供来源及覆盖标识的日线输入。

完整文件SHA与所有权见build/strategy-configuration-delivery-001/files.json；父作者公共App/锁/生产SPA脚本归组合候选单列。

## 独立审查后Unicode边界修正

独立规格审查发现：UTF-8字节合法的JSON可转义孤立代理，原decode未再核JSON值；纯核长度按Unicode码点，SPA原value.length按UTF-16单元，合法65..128个非BMP字符可能被拒绝，保存后整工作区读取失败。

SCW contracts共用Unicode标量检查，在decode后及规范encode前递归核键和值；这覆盖HTTP、直接owner配置和持久原件。转义孤立高/低代理422且原件不变，坏持久原件保留并暂停编辑。合法代理对解码为完整标量，保留原业务核长度、算法、包身份及持久schema。SPA字符串长度及配置名称输入按码点；输入移除UTF-16 maxLength，以完整码点截取128，说明通过独立描述关联输入框。

共用strategy-configuration-unicode.fixture.json的65/128个emoji名称分别经正式端点校验/保存/同根重启，SPA解码及组件回读/输入/核校验；端点和前端消费同一文件样本。新增边界覆盖孤立高/低代理作为键/值、POST/PUT、直接encode/decode/owner、摘要一致的坏持久原件及129码点拒绝。

| 新证据根 | 结果 |
|---|---|
| build/strategy-configuration-unicode-main-001 | 主链3 passed；含原链及两个跨端共用名称样本 |
| build/strategy-configuration-unicode-backend-002 | 590 passed /17.43秒，SCW/PWL及原纯包回归 |
| build/strategy-configuration-unicode-frontend-002 | 六文件88 passed，含共用样本组件/API及原回测兼容 |
| build/strategy-configuration-unicode-typecheck-001 | 全console类型检查通过 |

frontend-001新增提示放入label导致可访问名称变化，两项新增测试失败；提示移为aria-describedby描述后002通过。001冻结候选及所有原失败均保留。Unicode增量SHA、逐字节来源和本轮输出摘要见build/strategy-configuration-delivery-002；父作者负责新App组合安装及生产SPA受影响验证，独立review重新匹配本增量。

## Appa7安装与独立审查收口

Appa7/SDK0.14新环境已安装Unicode后端修正，wheel SHA `845f0fd3d56e79336d9e949abd2cef77779ad7f4e5de484679bfa62a16d2d81c`。本次前端沿用户纠正仅挂载策略目录，原参数组件保留组件验证资格；目录正常/搜索/旧链接/窄屏已单独验收，不恢复长表单。

`build/source-daily-chart-001/configuration-installed.py`通过实际已安装CLI两代执行正式HTTP：65/128个emoji名称经校验保存两版本；孤立代理返回422且store保持；同根重启后store、名称及版本逐值保持。两代CLI均exit0，App关闭完成、读取线程0、监听关闭，原件为configuration-installed/VERIFIED.json。相同fresh环境安装最终纯包002，36项回归再次通过。

两名独立审查者已分别对原Unicode P2执行delta，核9文件冻结清单、590/88/tsc原件、已安装后端摘要及上述CLI驱动/实际结果，均complete，原P2闭合。主页面和后端服务职责沿当前[策略目录](../specs/strategy-catalog.md)/SCW；本结果不授运行生效、完整模块或生产资格。
