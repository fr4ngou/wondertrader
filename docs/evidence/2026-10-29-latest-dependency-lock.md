# 当前唯一策略的Python依赖锁

类型：验证证据。日期：2026-10-29。状态：锁文件已同步并校验；普通安装器闭包改造与完整安装验证继续。

## 根因与修改

App声明已收敛为最新共振1.1.2，而uv.lock仍登记App a19及AI/risk/rules/signals/v2/variants，后续普通安装可能重新带入退出范围的策略。沿当前App pyproject及其本地source声明执行uv lock，保留已有直接版本约束、平台范围和可选依赖；不使用upgrade。当前锁的本地发行共五个：guanheng-app a26、guanheng-market-client、strategy-core a8、strategy-native a1和strategy-v1 a6。客户端动态版本按其源码元数据解析。

原锁逐字保存在build/guanheng-latest-dependency-lock-001/uv.before.lock，SHA256为af12c89f2757649bf81f4b6d4a93a069479c93cfefcca7802291a50a39a0e899；新锁SHA256为ca52bc3c63dad5087e0e1358db6900ca4b6c118fe294a53fd1c716bac7d67e9d。输入的五份pyproject在生成前后摘要相同，INPUTS/LOCKED/VERIFIED-001保留实际身份。原App/策略源码和运行实例保持。

## 验证与后续

366离线解析因PyArrow元数据缓存不足正常失败；367联网解析按既有约束完成36发行，11.516秒exit0。368随后执行uv lock --check --offline，0.046秒exit0；两次forced=false，整树0、双EOF、读线程join和资源回收通过。失败原件保留。

普通账户安装器另有硬编码旧七App项目的问题，缺少当前strategy-v1。该安装器按声明推导本地依赖闭包的完整模块正在开发，覆盖当前App、独立Host及冻结输入相容。此处只登记依赖锁校验，不据此授予完整普通安装、升级回退或生产运行资格。无真实下单/撤单或QMT界面操作。

## a27后继

App配置校验更新至a27、strategy-v1至a7后，主会话沿相同五份项目声明执行离线uv lock，380轮0.531秒exit0、完整关闭。生成前后五份pyproject摘要相同；新锁为0399f35f6492c0090c3dad2639844814f588efd109bc806c3aa0a60c6ee0f6f9。381轮完整冻结当前声明输入到build/guanheng-app-a27-install-001/source001，后继已完成App29/Host15普通安装及真实三证券分钟、八ETF日线HTTP链；root重核245输入和55根日期/OHLCV一致，正常关闭。上一a26安装模块和ZIP搬迁已完成，见[独立证据](2026-10-29-local-dependency-installation.md)。
