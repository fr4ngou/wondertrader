# 历史工作进程正式配置入口

类型：候选验证记录。日期：2026-10-21。依据[HDF规格](../specs/history-deployment-factory.md)。状态：DevelopmentVerified；本切片独立full及完整搬迁验证通过。本切片在观衡自有SDK组合既有客户端，保持原Operations、日历、行情及证据所有权；没有生产调用或发布。

## 实现与调用链

原worker要求部署方自行提供factory。新增 `guanheng_market_client.history_factory:create`，由严格v1配置与显式环境凭据构造OperationsClient、MarketClient、CalendarProjectionProvider、MinioEvidenceSink和HistoryRunner。worker取得原job锁后才构造；构造零网络、零线程、零作业推进。配置错误固定去敏，日历版本从同一来源生成，完整调用预算在接线时校验。实际执行继续由原step/close与CAS负责，无新增作业账本。

SDK升至0.8.0，显式源清单包含七个模块。基础导入保持标准库，storage extra沿已有MinIO7.2.20与urllib3 2.7.0；正式工厂选择该extra。CI从唯一依赖清单安装构造测试所需直接依赖，并覆盖SDK及其构建入口的变更触发。托管CI尚未运行，完整传递依赖锁定仍属于发行环境验收。

## 定向验证

- 11项纯Python回归通过：实际客户端类型、构造零网络/线程/业务动作、凭据隔离与快照、严格schema/重复键/非有限值/大小、组合预算、缺少storage依赖、CLI配置失败及异常链去敏。原始结果 `build/native/history-factory-tests/unit-result.json` 与 `unit.log`。
- wheel安装后的4项隔离整链首跑通过，19.616秒、退出0。原Operations归约器、原日历producer、实际native行情/DSB和真实MinIO SDK的合成S3服务参与；成功作业240根分钟线，经内容地址存储与回读、原CAS确认、task release、worker drain。S3 AccessDenied解除后同一进程、同一job恢复；构造及非法配置零连接。
- child以 `-I -S -B` 启动，只显式加入已安装wheel与storage site；记录模块文件摘要/PID，校验未导入QMT/WT业务源码或测试factory。socket审计仅准入本次随机回环端点。证据 `build/native/history-factory-flow-evidence/validation.json` 与 `flow-first.log`。
- wheel `guanheng_market_client-0.8.0-py3-none-any.whl` SHA-256 `ea0c224cb8dfaf03087eec7b85b04ea62c0dd80efd5068a348c29b50d3706c48`；factory源码摘要 `601d15512c614ac467cacce507fd56db61e715fe73d577ff32b4eff8aa804932`。

测试使用合成行情、作业及凭据。这里证明正式安装入口与实际组件组合；真实国信数据的既有证据保持[独立来源记录](2026-10-21-qmt-numeric-time.md)。

## 最终构建与审查

完整流程 `native.py all --offline --qmt-source D:/workspace/qmt --calendar-owner-source E:/workspace/qmt-worktrees/wondertrader-service-adapters` 退出0，显式设置测试用storage site。23阶段全部passed；92项启用CTest通过，另1项既有全天会话Disabled；32项pipeline通过。搬迁包中worker13、calendar9、factory4场景及原策略消费通过。日志 `build/native/history-factory-final-all.log`，本次固定回执与XML另存 `build/native/history-factory-final-evidence/`。

开发包 `dev-20261021T115625Z-f878add3.zip`，6,228,525字节，SHA-256 `653c80f9dac6b7dca447177e2ab2f81e16913fd655eff224d76d2d0e30a8b11a`。root复算包摘要并核对全部构建源摘要，无差异。12个已冻结框架文件仍与观察摘要相同；包含既有差异，当前资格为开发验证。

独立full目录 `build/native/reviews/history-factory-full/`：Standards与HDF-R1–R4均通过，开放问题0；40项WT输入及6项外部依赖均与审查一致，审查清单与all输入重叠25项全部一致。报告SHA `5e23feb7938598a1b74cfa6fc734b60d7cf87cc7ea8e501016141ea8631537ae`，输入清单SHA `689569550884f358717e8abc17b2633de7eb70162d711fce2b9d79922cca2c87`。审查独立复算包及包内wheel，确认与首轮候选相同。

## 剩余范围

生产分钟日历/证券历史排除、真实存储namespace/ACL/保留规则、独立服务监督和页面调用链仍需验收。队列owner崩溃恢复沿已有边界。原WtRunner正常退出的[13文件提案](../migration/native-cta-stop-proposal.md)待用户批准；本切片未改框架。整体接入目标保持active。

QMT公开执行契约另做只读刷新：27项原输入中26项相同，Host README变化；当前仍缺完整执行bootstrap/confirm_resume证明，见[账户观察与恢复边界](../migration/qmt-http-execution-boundary.md)。本工厂不增加账户或交易能力。
