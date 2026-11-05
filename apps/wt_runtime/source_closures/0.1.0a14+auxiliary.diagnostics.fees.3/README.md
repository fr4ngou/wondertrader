# 辅助数据与诊断组合源码闭包

类型：发行源码。版本：0.1.0a14+auxiliary.diagnostics.fees.3。状态：隔离主链已验证，线上采用另记。

SOURCE-MANIFEST.json固定ccd92347c3929714f2c948726490f2da361116a6的43个模块及Runtime13三个已验封存覆盖，共46个。三个覆盖保留原账户读取、库存和运行恢复行为，不能用当前开发分支的同名实现替换。所有输入均来自永久Git及此目录，不从已安装环境或QA目录提取。

用Python3.12运行build.py，指定--repository仓库、--backend固定flit_core3.12.0 wheel及全新的--work/--output目录。构建校验成员、后端和产物payload，输出BUILD.json。固定后端摘要见清单；依赖的V1a12、Native与Market SDK按运行角色的完整离线锁安装。本闭包只构建Runtime，保持各包独立发行。

实际重建46成员成功。两段完整原生回测及正式App读取见[组合验收](../../../../../docs/evidence/2026-11-06-integrated-auxiliary-diagnostics-backtest.md)。重建wheel与已验wheel的成员字节一致；ZIP时间元数据不同，各自保留实际摘要。生产配置、账户、金融状态和业务原件不进入源码闭包。
