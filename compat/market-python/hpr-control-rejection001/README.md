# HPR控制拒绝兼容闭包

类型：固定兼容源码说明。状态：工程资格已验，线上采用由运行owner负责。

两个普通Flit项目固定已有HPR Host基线及原Agent，独立于主干交易SDK升级。唯一需求为[HPR3-R1](../../../docs/specs/qmt-history-preparation.md#hpr3-r1-合法控制拒绝与原请求收束)。`SOURCE-IDENTITY.json`保存原wheel、现场两个已固定诊断overlay、全部原Host/Agent模块以及最终兼容源码身份。[原Agent项目](agent/README.md)保留原60个模块及原版本，构建无须追读已废弃项目或现场安装目录。

行为修改限`control.py`、`runtime.py`、`read_service.py`和`bulk_host_control.py`；`__init__.py`只调整兼容发行版本。control只引入拒绝持久交接、运输退休保护及关闭核同一Journal的直接前置，不包含主干新等待时钟、交易或资金路径。

从本目录运行`python -B build.py --out-dir <新wheel目录>`。构建核源码闭包后使用固定Flit3.12.0，要求已缓存该构建后端。安装必须选择本wheel及原Agent精确版本；不要用主干Agent或仅依赖pip check推定配对兼容。

验证须使用普通安装的新环境核真实来源材料的后继配对及相同策略字节，运行“合法拒绝→后继成功→正常关闭”。原pair绑定旧安装路径，保持只读；新配对通过原产品create/verify产生新Host身份，不改写旧manifest来冒充原安装。正式采用与运行验真由系统owner另行完成。

在新安装环境的Python下执行`-I -B verify.py --original-pair <只读原配对目录> --candidate-pair <独立新目录> --report <新验证报告>`。脚本核正常安装的63个Host/60个Agent源码，生成或核验后继配对，确认原策略逐字节相同，再运行固定原测试类；不打开现场Journal、不启动服务、不操作QMT。报告仅包含版本、SHA、布尔资格及测试计数。

[兼容Host项目](host/README.md)与[工程验证记录](../../../docs/evidence/2026-11-05-hpr-compatible-closure.md)分别说明发行边界和实际安装证据。
