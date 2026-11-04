# WT展示快照发布修正上线

类型：发布记录。日期：2026-11-04。状态：已部署，原触发条件现场验真通过。承接[持续运行及日常启停](2026-11-04-wt-continuous-service-live.md)，沿用原模拟账户、100万元账本、五项持仓和独立观衡。

## 根因与实现

普通Windows读句柄在读取status.json时可能阻挡文件替换。原发布入口把WinError32直接升级为Runtime失败，随后按依赖关闭交易运行。固定安装角色的受控复现中，持有普通读句柄得到WinError32及exit2；释放句柄的对照正常。此前现场代8e7c0d65仅保留runtime_failure和未提交候选，原异常分类缺失，其精确失败原因仍未知。

自有Runtime将status.json作为可重建投影：仅共享冲突32/33暂留上一完整快照，下一正常周期尝试最新值，组件健康检查继续。每个发布者只保留一个最多65536字节的自有候选；按实际文件身份复用，避免临时文件及内存积累。其余编码和I/O错误保持原失败结果。ready、stop、closed、failure控制收据沿原严格入口。另存固定阶段、异常类别及系统错误码，诊断排除异常正文、账户与凭证。见[唯一规格](../specs/wt-service-control.md#展示状态发布)。此次仅修改自有Python运行适配，WT框架及交易算法保持原版本。

## 安装及实际结果

运行角色为`0.1.0a12+integrated.2.market.35.3.service.5`；安装目录`E:/workspace/wondertrader-data/runtime-service-20261104-004`，wheel SHA256为`ca8d97f5eadf4f2058d93deb86e1508b5e52e1c8ba95ee52a08462f3a42cc548`。以已验service.4固定wheel叠加三份核定模块，其他模块及SDK0.15保持。

配置为`E:/workspace/wondertrader-data/strategy-capital-real-20261102-001/private-service-20261104-001/service004.json`。公开CURRENT控制代`100ca951-5c94-467e-92aa-c220baa18a67`，逻辑实例保持`a309716d-1288-4328-ac57-abd6ef0bb2e9`，配置SHA256为`4969c31ee7b97cffc6813af0829c5b91b6865a55685f83c70d6efe85a6326c93`。

证据根为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/continuous-runtime`：

- `MODULE-RESULT.json`：150个共享冲突周期中健康检查继续，最多一个候选；解锁后发布最新值，非共享I/O故障继续失败。
- `STATUS-SHARE-BEFORE.json`、`STATUS-SHARE-CONTROL.json`、`STATUS-SHARE-AFTER.json`：固定安装角色的原触发条件与修正后实际SDK替换对照。
- `SNAPSHOT-DELTA-REVIEW.json`：对应三份模块及接线的独立增量审查，无未解决发现；运行资格由实际证据另行证明。
- `LIVE-SNAPSHOT-SHARING-PROOF.json`：运行中持有普通读句柄0.75秒，Runtime及五组件进程身份保持，解锁后继续发布；现金633075.20元、五持仓及原基准连续，QMT策略未修改或重启。
- `SNAPSHOT-FINAL-LIVE.json`、`SNAPSHOT-ROLE.json`、`runtime-snapshot-cas/CAS.json`：实际安装、来源文件及业务状态身份。

2026-11-04北京时间09:00再次沿已安装status入口查询，Runtime PID35320、执行42508、账户Host73576、交易Host43636、历史24772均ready，CURRENT保持本代。这个观察证明持续运行，策略自然计算及实际新委托结果继续单独验收。

## 日常使用、回退与剩余

操作员沿`E:/workspace/wondertrader-data/wt-service/DEPLOYMENT.json`及同目录启动/停止入口运行；状态查询使用本次004解释器及service004配置。独立观衡仍为`http://127.0.0.1:18143/strategies`，关闭观衡保持WT运行。

回退先正常停止当前代，再以保留的service.4安装及原恢复入口生成新控制代；原账与未决委托身份持续核查。保留原wheel、配置、Native和Host依赖，禁止重用已消费控制目录或覆盖金融状态。

旧账户Host内部失败原因继续依靠新有界诊断取证。统一日线角色正式采用及观衡消费者切换由各自交付记录补充；最终自然策略计算、模拟券商业务结果与清理审计仍在进行，整体目标保持active。
