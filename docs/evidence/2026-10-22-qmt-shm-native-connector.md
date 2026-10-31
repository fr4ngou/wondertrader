# QMT共享内存连接包与C++原生行情接线

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-22。范围：[QSW-R1至R11](../specs/qmt-shm-wt-binding.md)。当前状态：独立full与Host a2修正delta完成，F1关闭、新增gap 0；安装与联调资格限定合成互操作。真实新包终端加载、来源单位、账户、历史及交易尚未取得资格。下方保留各轮历史记录。

## 实现与复用

独立Host/Agent包由本仓库构建，Agent兼容实际Python3.6.8标准库；Host在终端外拥有认证HTTP和内嵌通信Journal。QMT原线程执行允许的只读API，传输沿已验证的SHM/base control协议。未保留旧平台聚合契约、资金/持仓账本或人工审批流程。

C++新增有界HTTP owner、认证绑定客户端、行情端点及`ParserQMTHost`工厂，复用既有PollingParser、MarketParser、原ParserAdapter及CTA。原终端HTTP契约保持退役，受影响旧客户端仅作兼容回归；新路径不回退。未新增WT框架修改。

Host收尾时实际复现慢/半body可拖住默认Uvicorn关闭，R11在自有Server入口以完整接收预算、HTTP占位和一个总关闭期限修正。开发源168项及runtime-only新安装45组通过，包括实际3.6.8、Win32 SHM和10个独占进程关闭/容量场景；这些是作者开发证据，独立结论另取。

## 最终安装与联调

Host最终安装为`qmt-shm-package-001/install-d305b77949d1470ca6fb09601b02f83a`，安装清单SHA为`6a411e66548d0fd82ce7f28f1c28b7997f278edd90e7eec03addff2639cce675`。Agent wheel SHA为`9756a4b23618f9030accc0a30c8190913091fefa9cd8e7a0f8fa05a73219b97c`，Host wheel为`76bf3bb4cadd76aefdc198270f775767865ff18c4b7b86eb4a77b192598737ba`。

原生产品独立目录为`qmt-shm-native-001/native-install-001`；生产Parser DLL SHA为`c95adf9f77055bafc4db4d5e733446eee7a0c97777a540b81689035d382f6516`，不含故障测试门。与同一Host最终安装的联合轮`installed-final-002`实际经过pagefile SHM、原线程合成SDK、认证读取、新C++产品、原Adapter/CTA pool0和pool2，三绑定/原结果字节、时间代际、停止及资源收尾通过。自有Job退出码0，正常结束、进程回收和管道join均确认。

行情3.25、量10、额32.5是显式合成fixture，factor=1只证明映射；不授真实股数或分钟精度。当前native构建的工作树framework输入与固定上游Trader兼容输入各有清单，不能据该联合轮扩大冻结框架差异的资格。旧只读Trader兼容以固定原WT对象另构建，68项合成回归通过。

## 冻结、回核与独立审查

根任务已逐项核对Host311份原件、76份源码/规则、1361项安装，C++的5项索引、914份原件、86份当前源码/ZIP及4项独立原生产物，全部身份相符。回核脚本及收据在`build/guanheng-workspace/qmt-shm-integration-001`。

| 入口 | SHA256 |
|---|---|
| Host/Agent最终审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-package-001/final-001/review-inputs.json`） | `3d1a88424226ec1e55164a677e1ddfe9247af726ffee3d848ee9259552739f49` |
| Host/Agent原件清单 | `752fd901909e22d29f1656d338a9464f1ba0a43cc677258e4a2a59e4b6574cd7` |
| C++最终审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-native-001/final-001/review-inputs.json`） | `3d8ac4221990894169a95d7bac482e228a5b23b41973ebbdbb00c1c28a576dc8` |
| C++原件索引的manifest | `2f053fb65d6a7fc724ef62f57017408e93da682e83f2c590be7b7bd9aac140ae` |
| 两端整合审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-integration-001/review-001/review-inputs.json`） | `585a8aa7f7a75a15651921f8f9a08ad794a06f7809c821318aec679eaec615bf` |

三份国信手册已补成本仓库实际CLI命令，离线核验、启动及真实加载边界分开；补充文档ZIP随整合入口冻结。初始故障、旧轮及preview原件保留，既有012实例与私有配置保持。当前独立full进行中；不据编译、通过条数或作者联调宣布完整观衡、真实来源或生产交付完成。

## 后继：独立发现的关闭期限竞态

独立审查在同一冻结候选上复现QSW-F1（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-review-001/QSW-F1.md`）：`HostReadRuntime.begin_shutdown()`先判空、后赋关闭截止，并发调用者可覆盖首次已发布的期限。两线程公开`HostServer.request_close()`实测延长约1.254秒；真实SIGINT重入（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-review-001/QSW-F1-SIGNAL-ADDENDUM.md`）同样覆盖期限，且可观察到业务准入已停止、HTTP关闭事实尚未发布的短暂分歧。时钟为真实monotonic，没有伪造Runtime或运行来源SDK；Journal正常回收。

问题属于自有Host的关闭状态发布，当前没有证据指向WT线程实现、委托重放或权限扩大。现有候选保持冻结，待完整full封存后统一修正；修复须同时覆盖线程竞争、信号重入以及所有关闭/准入读者。现有运行实例、原生框架和终端保持原样，R11资格尚未关闭。

## 后继：完整报告与Host a2修正候选

独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-review-001/FULL-REVIEW.md`）已完整封存，结论gap、唯一P2为F1，报告SHA `f3311d2aab4d6407827aae2b09e55cc1a2b9659330c27b5e722f8b62dc53ff85`。适用R1至R11全部检查完成；168项、9组C++协议、两池实际安装、30次自主HTTP/双代重启和36种非法联合预算均保留独立原件，限定合成互操作。可选整套market测试停留既有history lifecycle用例，未取得整套通过资格，也未据此判为QSW新缺陷。根核1216份审查原件、报告及矩阵相符，见回核收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-shutdown-001/full-review-integrity.json`）。

完整报告后在自有Host修正首截止发布：精确私有dict以固定str键、float值通过一次setdefault保留首次发布；HTTP关闭及业务准入从同一事实读取，信号处理不获取Python锁。Host升至0.1.0a2、Agent保持a1，协议、profile、策略及C++产品字节保持。适用依据与实验见修正设计（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-shutdown-001/PLAN.md`）。

正式新noneditable安装的Host wheel SHA `05af1c46e6cd4e47a0f6ac7049043b3c3bbeba65030a4c6f2285c6989e86eb5d`；原安装、旧红灯及失败原件保留。两条实际Runtime/Server原先红灯已绿，完整170项回归通过；后继新增压力后最终3项停止回归通过，含32线程3200次公开关闭调用。相同生产C++ DLL与新Host经过真实Win32 SHM及原Adapter/CTA pool0/2，正常退出、PID回收和管道join确认，见新联合轮（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-shutdown-001/installed-chain-002/summary.json`）。上述为修正作者证据，独立delta仍待验收，F1尚未正式关闭。

新联合轮首次读到测试证据文件半写JSON而失败，失败进程已回收；仅修正测试helper在原观察期限内等待完整JSON，随后新根两池通过。该变化不修改产品HTTP或源端行为。另一次长路径wheel构建失败保留日志，后继直接调用同版Flit后端保持Windows路径有界；新安装依赖均由本地wheel和逐包SHA绑定。

## 后继：Host a2独立delta关闭

独立delta报告（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-shutdown-review-001/DELTA-REVIEW.md`）已完整封存，SHA `e08a0f03d080fdc15c9642ae9c7758a0e11b947eb5dacd539c0129ba46a92fac`；F1/P2关闭、新增gap 0。审查者以独立noneditable安装复现旧版双线程和真实SIGINT重入的期限延长，新版两类均无延长；100次过期重复、24线程1920次调用保持同一截止。实际HTTP/SHM在半body时收到真实SIGINT，业务及HTTP共同停止准入，0.581秒完成收尾，Journal与SDK调用数均为0，资源释放已核。

独立171项适用测试、原生产DLL两线程池安装互操作、测试helper半写恢复及原期限拒绝均通过；六个受管Job自然退出、PID回收，无遗留子进程。根任务已核验987份独审原件和报告身份，见回核收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-shutdown-001/independent-delta-integrity.json`）。当前通过范围绑定Host a2和原Agent/协议/生产Parser，未变更WT框架，也未将合成结果提升为真实终端、账户、历史或生产资格。
