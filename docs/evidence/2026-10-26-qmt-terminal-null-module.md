# QMT 自动退出与策略函数模块身份

类型：后继故障与验证记录。状态：本次生成器缺陷已修正，隔离回归及真实只读恢复通过；完整交易与整体迁移继续。

用户确认 QMT 自动退出后重新打开，保持策略停止。之前 2026-10-23 的真实共享内存行情与账户四查询证据继续有效。本记录处理本次重启后的运行故障。

## 现场证据

本次获准只读启动在 2026-10-26 04:36:38.377Z 点击运行；原配对正文 e105 保持。04:36:38.662Z Host 发布 binding，随后 last_tick 仍为空，最终健康为 unavailable／TimeoutError；这份 binding 只证明认证响应及 Host 发出 ready，不能证明 Agent 消费确认、init 返回或 timer 正常。无行情业务 POST、账户查询、下单或撤单。所属 Host 正常回收，原失败保留。

QMT 自带转储 `D:/software/guoxin/userdata/dumps/10179260-3a54-4987-9e68-fbed600c316c.dmp` 创建于04:36:38.586Z，转储时间04:36:39Z；进程号41400与本次QMT一致。异常 `0xc0000005` 读取地址0x8，线程72968，`python36.dll+0x169c7a`，RCX为空。转储仅限量提取异常、模块和上下文元数据；512字节栈窗口仅输出模块地址候选，未保存原始内存。具体函数对象未包含在所读内存范围，具体函数名保持 unknown。Windows Application 1000/1001 最近30分钟查询为空，原EventLog证据不用于排除故障。

## 触发链与责任

本机 Python DLL SHA256 `54fa9e8511cb57be78be995a9973676cf3eba2b54aa36f6244dd0cb5977c4002` 的公开导出确定异常位于 `PyUnicode_AsUTF8AndSize+0xA`。PE展开信息确定第一层返回地址位于栈+40，指向0x196b4e；其前的调用以函数对象+0x58字段作为输入，缺少空值检查。该分支用导出的 PyFunction_Type 检查函数类型。CPython 3.6.8 的该字段为 func_module；globals缺少__name__时构造器保留NULL。正式生成器私有entry全局确实缺少__name__，可确定生成函数元数据存在该缺陷，并与本次原生异常链强吻合。最终现场因果关闭仍以修后终端恢复为准。

源码修正在 `connectors/qmt_shm/host/guanheng_qmt_shm/pair.py` 的统一 renderer，SHA `a17911d36380e761d58402baf31e0ce6f701c9b5f092137c4f12341c48f2b1dc`：runtime与entry执行前继承合法宿主模块名，缺键时建立标准脚本名__main__；非法值加载前拒绝；私有entry继承同一身份。覆盖内部函数与导出回调，不修改QMT DLL、模块权限或WonderTrader框架。原冻结配对与终端e105保持，重新安装／配对须完整核验新字节身份。R15回调局部发布候选继续冻结。

## 验证

- 修改前目标Python3.6.8：只读／交易各三个正常作用域共6案，全部在模块字段前提失败；没有故意调用原生崩溃路径。
- 最终目标Python3.6.8：普通与分离全局／局部命名空间各12案，共24/24通过，覆盖只读5个、交易9个内部函数的模块字段、外层runtime函数、已有／缺省名字、非法值加载前拒绝，以及原init、timer、handlebar、stop、重复init。只使用Agent与Context替身，没有真实SDK、账户或交易。
- 初版修后夹具因datetime.strftime隐式导入time未列入测试白名单而失败；原失败保留。最终仅修测试标准库夹具，产品没有新增白名单。
- 最终同一测试源码两组root1324与68876（子PID见原件），均退出0、原截止内、创建期Job、无控制台、整树归零、管道EOF、reader join及句柄关闭均通过。
- 产品delta独立静审无P1/P2；最终普通／分离24案独立delta核查无P1/P2，报告见build/qmt-entry-module-identity-review-001/dynamic002/REPORT.md。

原件：`build/qmt-entry-module-null-001/{DUMP-METADATA,BEFORE-VERIFIED,AFTER-VERIFIED,FINAL-VERIFIED,SHARED-FINAL-VERIFIED,SPLIT-VERIFIED,FORMAL-CHANGE}.json`；正式回归入口为 `tests/integration/qmt_shm_entry_identity/`。

## 后续与边界

从原已验冻结安装输入仅覆盖renderer修正，构建新安装、生成新配对并逐字verify后，再进行单次受控只读恢复。当前QMT由用户重新打开，策略未启动；源恢复、真实行情／账户及完整业务验收继续。

依据：[Microsoft异常结构](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception)、[x64上下文](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-context)、[CPython3.6.8函数结构](https://github.com/python/cpython/blob/v3.6.8/Include/funcobject.h)、[函数构造器](https://github.com/python/cpython/blob/v3.6.8/Objects/funcobject.c)。

## 后继离线安装

原已验冻结输入295文件中，仅pair.py变化：引入正式renderer逐字相同实现，旧只读模板委派该renderer；原回调和其余294文件保持。新独立安装root44692／child16644退出0，40.0秒内完成，180秒原截止、创建期Job、整树／EOF／join／资源门均通过；8件执行工具前后SHA一致。已安装pair.py SHA `8e821774bccdfb46480687fe97436b4a9f76250fcf6bab0051229c77327a5e16`。新配对及真实终端恢复仍待验。

## 真实恢复结果

新安装／新配对完整verify实际通过：账户、连接、政策与内存runtime源保持原样，正文除模块身份前缀和entry的同名字段外，规范换行后的其余全文与旧配对逐字相同。新配对正文SHA a38fb5fc41a003946799bccffbd17c7db3bb86f3915ce2b1c67b73d7d6ceabac；终端同文件使用配对正文加一个LF，SHA ddd27d0f17f93c25b08b76788d089ee1830045ecc4c99f80c8eb7cbe1bdfa2a2。原e105已备份在受保护目录，新正文保持只读，策略完成后停止。其他策略及旧18017 Host保持。新Host解释器实际SHA c49b为新安装身份，原47b未冒充复用；实际完整SHA见身份原件。

首轮module-001因核对界面耗时，UI启动超过原60秒连接窗口，root63712退出2，无binding、无业务POST，Host完整回收；该轮保留为执行时序失败，不能用于修正成败判定。随后module-002使用新目录与同一新制品，在原窗口内启动同一策略：认证绑定、两次有效tick、唯一一次真实market.full_tick均成功；账户／历史／下单／撤单请求均为0。根UI停止策略后写stop.request，helper确认正常关闭。root4856实际退出0，用时148.65秒，小于原250秒；控制器原245秒，tree0／双EOF／reader join／资源关闭均通过。QMT原窗口32640882仍存在，本次启动后没有新增故障转储。观察只覆盖本轮，长期运行稳定性另验。

公开原件：`build/guanheng-workspace/qmt-source-module-20261026-002/{ROOT-RESULT,SOURCE-OBSERVATION-IDENTITY}.json`。固定结果13个字段经过白名单校验，其公开投影的canonical字节与私有原结果相同，SHA c9a2dd02ee8c2a45b24c3fac83a1b21addabbb67f2bda5d5be8c949b2a612709；真实业务回包仅保摘要关联。控制器child为启动入口，host-ready PID65328单独登记，不根据PID猜直接亲子关系；整树回收按Job实测登记。独立动态审查已完成，新P1/P2=0，见build/qmt-memory-restart-module-004/dynamic-review/REPORT.md；21份公开原件及固定结果SHA已独立核同。
