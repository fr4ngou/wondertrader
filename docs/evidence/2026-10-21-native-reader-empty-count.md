# 2026-10-21 原生随机Reader空历史计数修正

类型：代码及隔离验证记录。状态：开发验证通过；生产未发布。用户批准仅此分支修正并要求中文注释。最终要求见[NRC规格](../specs/native-reader-empty-count.md)，提案与回滚见[最小提案](../migration/native-reader-empty-count-proposal.md)。

## 根因与实际修改

原样 `08b230dd05facf6d650d949bfe51054115a2ecb1` 的 `indexBarFromCacheByCount` 在空历史数组时返回NULL，保留引用输出count。上层使用该数量构造切片，导致有声明数量却没有数据块；空历史加不足量实时数据也会虚报总量。

正式源码仅在该空分支新增count=0、括号和中文原因注释，共4行新增。注释说明count是历史输出条数、空历史需归零以避免构造无数据块切片。保持文件原有换行与末尾形式，未扩改其他空分支、索引算法、线程、锁、交易或接口。

`build/native/capability-audit/empty-count-fix/core-boundary-check.json` 将本轮开始的可用已跟踪src文件摘要逐一回读；唯一变化为 `src/WtDataStorage/WtRdmDtReader.cpp`。其他已有冻结核心差异保持。

## 原样红例与隔离绿例

使用同一正式回归探针、原Helper及兼容原样对象。隔离绿色Storage只重新编译该原样TU的唯一批准差异，其他Storage对象复用固定原样构建；源码差异逐字校验（沿原换行形式）。构建输入和输出摘要见 `build-inputs.json`。

6个证券fixture为历史0/2/8根×实时0/3根；每证券请求1/3/5/10条和3个截止，共72例。独立预期按完整输入合并、时间筛选、取尾部，校验声明数量、真实block累计数量和每行全部字段。DMB为预先构造的静态文件；无真实账户、行情源或并发Writer。

| 版本 | 退出码 | 通过 | 失败 | 证明 |
|---|---:|---:|---:|---|
| 固定原样Storage | 1 | 51 | 21 | 重现空历史和部分实时虚报 |
| 唯一批准差异Storage | 0 | 72 | 0 | 空、部分、正常尾部及字段保持正确 |

结果 `run-d01e2310/results.json` 与 `build-inputs.json`、最终源码/探针摘要共同绑定，不能仅以进程退出码或未绑定源码的单个JSON判断实现。

## 正式构建与持续回归

正式native profile构建WtDataStorage及WtNativeReaderCountProbe成功。新增 `integration.native_reader_count`，Python driver为每轮生成独占目录，检查退出码与72例/72通过/0失败，同时保留stdout/stderr和结构化结果。work非空时探针拒绝覆盖。

CTest筛选原生计数回归和原生回测冒烟：2项通过、0失败；计数批次72例。正式driver换回原样Storage后退出1并明确报错，确认持续门禁实际拒绝原缺陷。

原Servo配合隔离修正Storage再验：空count返回0且回调一致；前序两证券428根真实样本仍逐字段一致。原派生缓存限制继续保留，本修正没有声明修复它。

最终身份见 `build/native/capability-audit/empty-count-fix/final-validation.json`，包含源码、规格、CMake、测试、正式二进制、构建日志、CTest XML及真实样本回归身份。独立full及证据收尾开放问题0，报告为同目录 `independent-full-review.md`。审查核对最终规格、源码、适用规范、本轮验证材料以及实际文件摘要；正式构建和执行证据待补项已关闭。

## 验证边界

本轮没有重跑PG候选链、主动下载、完整实时策略或真实交易，也未生成或发布新的完整系统发行包。上一完整包仍代表其原输入；当前开发二进制与旧包分别登记。本修正不增加RT map并发写入、扩容、热卸载或完整业务上线资格。

静态检查使用 `git -c core.whitespace=cr-at-eol diff --check -- src/WtDataStorage/WtRdmDtReader.cpp` 尊重原文件CRLF；本地文档检查覆盖导航/索引。后续继续核准原生数据接入、策略与独立业务真实链，整体目标保持active。
