# 独立观衡离线制品

ORP-R7：观衡按自身功能、接口兼容和安装/页面验收独立交付、升级及回滚。WT交易模块的开发、恢复验收或整套联合候选的收口，不作为观衡交付前置；观衡和WT无须使用相同版本号或同步发布。联合候选仅用于跨服务兼容和整链验证。观衡继续只读取WT公开发布及只读行情接口，WT负责通信、采集、策略与交易；缺少某类发布时，页面如实说明该类数据来源状态。

类型：接口规格。状态：accepted。范围：C只读App/SPA的development制品，依据[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)。前缀ORP；WT/Host及公共SRI保持原协议。

ORP-R1：制品仅包含普通App角色预建wheel、精确锁、原安装收据来源、生产SPA、固定安装工具闭包和短说明。复用原account_runtime_install.stage_artifacts/verify_artifacts/install_artifacts及原SRI路径/容量/复制原语。不得包含运行凭据、活动配置、WT/Host角色或程序源码重建步骤。

ORP-R2：OBSERVER-RUNTIME.json使用guanheng.observer-runtime.v1，字段精确为schema/development/role_manifest_sha256/spa_files/files。development为true，角色唯一app，spa_files含index.html且为相对路径→SHA；files为除自身清单外全部原件的SHA/字节数。普通容量沿SRI的20000文件、单文件256MiB和总1GiB，路径/链接/大小写冲突按同一原语拒绝。外部可信manifest SHA先核，再核完整文件集、原角色清单及SPA。

ORP-R3：C安装入口observer-install.py提供verify和install。verify无写入/子进程；install接受包根/manifest SHA、新target、显式CPython3.12 x64及uv、有限seconds或调用方原deadline。只从包内wheel/锁普通copy离线安装App，再保留相同SPA。调用原native.run隐藏创建期Job及输出上限；同一D覆盖安装和最终原件检查，成功收据最后发布。已有目标及来源/目标包含关系拒绝，失败现场保留。入口返回安装解释器、模块、SPA及安装收据摘要，不启动业务进程或切换版本。

ORP-R4：ZIP由明确固定原件生成，接收方从可信渠道核ZIP SHA后使用受信系统解压，再核manifest。工具不提供任意ZIP解压API。操作资料说明外部Python/uv、四WT身份pin、显式NAP来源、行情只读连接和独立个人目录；凭据留外部。观衡/WT独立启停，个人目录先准备存在并在升级中沿用，旧托管App排除回退候选。

最终收据换名返回后再次核原D。换名跨D时入口返回失败；已可见收据保留安装事实，完整有界安装资格同时要求本次入口exit0和返回摘要。失败恢复另选新目录，保留原现场。

ORP-R5：完整主路径为制品→可信解压→另一新根普通离线安装→与六组件WT实际HTTP及页面。a42只读基线→a43→a42回退核同WT/Host/PID和其他binding、原账户来源换代、五项历史、个人偏好连续与正常/异常关闭。适用旧结果格式可读性按原合同核验，真实QMT/完整系统/生产另外验收。随后覆盖清单/SPA篡改、非App角色、已有目标和同D失败，并做独审。

ORP-R6：独立观衡公开CLI使用标准SelectorEventLoop承载HTTP套接字，沿固定Uvicorn公开loop factory装配；同步行情/报告/观察读取继续在原有界线程池，App不持有asyncio子进程或管道。Windows的512套接字上限属于该运行时边界，当前单机操作员及有界浏览器通道按此范围验收，新增高并发部署须另核容量。客户端重置后，网络传输仍须执行原socket关闭和server责任释放，server.wait_closed完成后再沿原App资源关闭协议退出。修复保持原固定Python及第三方包字节、请求/线程/退出预算和金融事实，不替换标准库方法、不吞网络异常或增加按错误码特判。验收包含同次连接重置条件的原运行时失败/新运行时正常释放，以及普通/搬迁安装的完整页面读取、App关闭和独立历史服务连续性。
