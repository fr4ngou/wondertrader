# 真实QMT账户公开入口主路径

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证证据。日期：2026-10-28。范围：当前源码观衡ASGI公开API、实际原生账户宿主、原WT Adapter与只读插件、独立已安装Host及真实QMT；未做真实下单、撤单或生产切换。

## 根因与实现

实际ManagedAccountScan已能取得四类真实账户结果，公开入口仍被schema2开发期固定False拦截。同输入先运行direct：原生完整返回，公开接口仍unavailable。根因在自有App准入接线。现在严格配置准入后由应用唯一ManagedAccountScan负责采集；capabilities表示配置支持，实际来源以本轮有界查询决定。未配置保持不可用，直接schema2缺少受管owner在创建资源前拒绝。原Job、截止、签名、IPC2、容量、投影与只读范围保持；本次没有修改WT框架。

## 输入身份

原生EXE SHA256：12946b1167dab339b597b69d507dd5448e0aa1b4fbe70889818ed6af6f91960c；TraderQMTReadOnly.dll：1b63d667f132a9b1418733af955f1eadc0b47b370601ca85512fbd04d2333f81。固定原生输入来自build/native/account-broker-current-002/cmake/bin。只读策略SHA：69369e811e7ecf5dabd01855d08fc9df24475be868decce730b2eef28a85c37b。配置摘要7d02418de5710b3152b1c53075e4cbce75f072d8d2197d0c67e2cfe0afdc1f8c；descriptor摘要7a71999b2136ac98169fe79be2030c3fb61b1918e9203227b1c1c3d95e3c7a12。秘密和真实账户明细只存private，本文仅登记摘要及条数。

| 文件 | SHA-256 |
|---|---|
| `apps/guanheng/guanheng_app/account_scan.py` | fca51f4e0625fafc4ca0a29fd9c6865f2056cf02fa39061736ac65511a7f07d9 |
| `apps/guanheng/guanheng_app/app.py` | 5b16978464e23cdb7c3ea550e124b88b391322edb5a7d009a0f049f7175cd778 |
| `apps/guanheng/guanheng_app/account_scan_config.py` | ad286a0e5624fb059a07cd39ac23b2feead9aa928ac319fa6cafda0378fe670c |
| `apps/guanheng/guanheng_app/account_scan_runtime.py` | 2f59682244e284db95f90e4bddfb1f652eb9b9be60a8a0b206aa4dccd9c20cc3 |
| `tests/integration/qmt_shm_account/test_scan_config.py` | 5950e0eec204899d9cf3b4709d4cff7ce434dc2dd8937d612c435e4be071ea1f |
| `tests/integration/qmt_shm_account/parent/test_parent_runtime.py` | 2037d184d51c87ee1d6cd686c0e3fc91866f264e9ef3de97ef024dec50096a05 |
| `tests/integration/thread_owner/test_account_capability.py` | 3cb7cd95848f52afdd5694103e9497c57bce5a211d3ef0a94219ffb94a284546 |

## 实际步骤与结果

1. 隐藏受管controller准备私有配置，核原生/插件/基础资料身份。App与Host使用各自解释器；真实QMT策略只走命名共享内存。
2. direct阶段Host PID74496：取得持仓4条、资金1条、委托0条、成交0条，四组complete；扫描器exit0、closed/joined=true、queued0、worker_live=false。公开旧入口仍unavailable，保留原结果。
3. 修正App接线后，保持同一个QMT只读探针运行，新App管理Host PID61788。原运行策略自动连接新Host；GET /v1/ui/account/overview实际HTTP200、DTO2.0 complete，同四组4/1/0/0，原生关闭状态一致。两次binding摘要不同，分别8f8c6a9ee9d933a38d41faee2bee85a3a8e39f6f4f05ca31d399db029f28f507和3d7e62b7631be5c2161f0bf39a57cba31d2482904b9b344d9cf7a0ea149d647f。未靠QMT停启协调新Host。
4. 两轮App shutdown_complete=true、Host closed/forced=false/pending=false、managed_pending=false。各外层原截止内exit0，tree_zero/readers_joined/resources_closed=true，双EOF=true。
5. 12:41:26.866实际停止只读探针并恢复原正文SHA35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae。行情全推策略保持运行。

原件：主路径目录（外部历史/待归仓路径：`../../build/qmt-account-public-main-20261028-001/`）内INPUTS、direct/ACCOUNT、direct/PUBLIC-BEFORE、public/ACCOUNT、各FINAL及PROBE-RESTORED；脱敏summary可读，private不得对外输出。外层根分别为build/guanheng-workspace/qmt-account-direct-main-20261028-001及qmt-account-public-main-20261028-001，各build-*下有result.json/输出。direct约53.906秒，public约21.609秒；这是整轮含认证/收尾耗时。

## 回归与审查

同版三文件pytest命令及实际收据位于build/guanheng-workspace/qmt-account-public-tests-main-20261028-003，JUnit位于build/qmt-account-public-tests-20261028-003/junit.xml：174 passed in 1.38s，exit0，原截止/创建期Job/隐藏窗口与资源回收收据通过。测试核支持版本、缺owner拒绝、唯一受管委派、原管道/截止/共享等待及能力字段；实际券商来源资格由上述实机记录提供。

前两次测试失败保留：001独立测试导入缺少策略包路径；002参数ID展开65537字节输入，触发Windows环境变量32767限制，且错误输出达到外层64KiB上限，根控制器回收。修正测试自身sys.path及8个短参数ID，保留原超大输入、预算和断言。002 JUnit及根结果保持，未算作通过。

独立静态full及规格delta（外部历史/待归仓路径：`../../build/qmt-account-public-review-20261028-001/REVIEW.md`）结论为本范围无必要P1/P2；最终规格SHA a6cf849822530bcbc54108b678f5c2d20dbfa9481884e51a62d6d744ea1e621a，报告SHA e24290e0e0e057f1a290552e9980aa8f77b46f5443febba7b5073344f894d55c。审查未读取运行报告或private、未执行程序；动态资格由本记录独立陈述。

## 未覆盖范围与后续

本次使用当前App源码和既有原生/Host安装，公开入口为ASGI TestClient实际路由。独立新wheel/SPA安装、真实TCP浏览器中文页、完整45项原生场景、生产运行和真实交易另验。四类查询分别发生，完整结果不表示同一柜台事务快照。Writer停止与映射同步方案仍proposed，未获此次解释性回复批准；其待决策不会阻断账户和历史适配。
