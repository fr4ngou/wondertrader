# 独立原生来源历史服务

类型：模块A交付证据。日期：2026-10-28。范围：[SMP规格](../specs/native-source-market-process.md)；[三会话交付计划](../migration/parallel-system-delivery.md)模块A。独立来源历史主链通过，完整模块A和系统实盘资格继续开发。

## 实现及根因

原有5338证券/335个来源store可以通过Reader读取；常驻HTTP查询此前依赖开发验证入口。新增 source_market_service.py 正式受管子服务，复用 NativeSourceMarket、原生Reader、MarketHTTPServer 和同版SDK；App父进程由模块C接线。配置原字节各核SHA一次后传入同一对象，创建线程独占Reader及请求；沿统一Job/ready/stop/closed合同关闭。QMT内部无文件和网络访问边界保持，读取与本地HTTP发生在外部服务。

独立审查发现导入Host纯 private_files 会经过包初始化加载FastAPI/Uvicorn，仓库venv掩盖了安装依赖。已在包根因层改成保持公开API的惰性导出，并以 -S 禁用子进程site-packages验证真实入口。安装组件包含两枚原生DLL、MSVC运行库、纯Python闭包及WT/Boost/spdlog/RapidJSON许可证；打包沿唯一依赖锁。复用原候选先核固定上游、全文件集合、相对路径和逐文件SHA，禁止混入未登记输入。

## 固定来源及运行证据

- 固定WT来源08b230dd05facf6d650d949bfe51054115a2ecb1；本交付未修改WT框架C++。build/source-market-build-014冻结INPUTS，原生构建与组件安装通过；原受控作业174.640秒、exit0，非强停，树/管道EOF/读线程/资源确认关闭。
- 最终制品 build/source-market-package-023/GuanhengMarket.zip，SHA256 ffcc62a969e9c3a3ef1ed165c8f75d235408605a05e1d5a8f6f68cd1d6e0f06f；147份运行文件。INPUTS SHA256 da9b43fd14eb36ed17206c40b22b4f9f21dfa4b325375b7d6ece2747aac8362f。原受控打包1.578秒exit0，正常回收。运行文件集合及全部SHA与已验020完全相同，变更仅构建驱动兼容性及来源收据；原生二进制未重建。
- build/source-market-real-main-021/VERIFIED.json：搬迁020 ZIP逐文件核验→标准库子进程正式服务→335真实store注册→已安装SDK首次查询→同一DSB原生直接回读逐字段对照→正常关闭。20.625秒exit0，未强停、整树/EOF/join/资源关闭；监听端口确认关闭。QA父适配仅覆盖ready/closed schema，App正式接线由C另验。
- 五个样本每项2根；600000.SH、000001.SZ、301718.SZ尾部2026-10-27 15:00；510300.SH尾部2026-10-26 11:30；159919.SZ尾部2026-10-23 15:00。SDK与Reader的OHLC/量额、source身份、标签语义、单位和数据版本一致。原单位为unknown，覆盖Unknown，保留源值资格。
- source-market-regression-20261028-022：18项配置/控制/构造失败/原生关闭及发行清单根因回归通过，exit0、非强停、整树/EOF/join/资源关闭。原件在 build/guanheng-workspace/ 下同名根。
- 独立full/delta源码审查完成；两个P2（隐式Web依赖、Path.is_junction的Python3.12限定）均修复，末轮无未解决P1/P2。运行结果由本证据独立核实，审查自身为只读源码。

## 失败保留及后继

早期014入口发布函数参数误用，后续015/016 QA误用SDK关闭/Reader必填参数，均保留失败原件，修正后017主链通过；019构建工具启动时错误使用-I使其同目录native导入失败，020按原构建环境启动通过。上述失败未覆盖为成功，实际资源回收分别核对。

本轮完成真实主链和对应根因回归；真实令牌拒绝、空来源、HTTP处理异常与关闭抛错的更完整异常覆盖列为模块A后继，当前未据此授予全部异常恢复资格。全ETF历史仍有缺口，原单位/盘中时效/全天连续分钟仍待核实；服务不补造尾部。没有生产切换或真实委托/撤单。模块B/C继续各自大模块，最终由主会话固定候选集成。
