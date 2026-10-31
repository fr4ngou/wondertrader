# WT未知委托恢复增量合入与独立整包

类型：增量合入及候选安装验证记录。日期：2026-11-01（北京时间）。状态：33份固定文件已合入本地主干，匹配的独立WT整包已搬迁安装；正式活动委托跨进程恢复和完整模块资格继续。

## 源码与审查

合入提交为 `67ebb9945a40bea1be4ee66249d5f8ed1d00068f`。Root核85项引用、33份交付/审查快照及两份离线制品。两份独立审查开放P1/P2均为零，资格限定为当前增量和两条新安装SDK替身主链；原[业务证据](2026-11-01-qmt-unknown-continuity.md)保留正式活动单恢复等未完成范围。

合入采用固定快照的Git对象，开发者工作区文件保持原样；共享证据索引只加入本批新条目。源码范围包含自有Common、Standard、Execution、Host/Agent、相关测试、规格和五份版本/构建配置，没有新增WT框架源码修改。Windows原字节源码保持原行结束，空白检查按CR结尾及原空格规则执行。干净主干文档检查通过。

实际接收入口为 `build/ms-unknown-continuity-delivery-001/INTERFACE-001.json`，SHA256为 `5bb89480241de6a748fe34f8c9fd3d5897d12569c5d80768834add787ff370df`。Root固定接收及合入记录分别为 `build/root-unknown-final-intake-001/INTERFACE-001.json`、`build/root-unknown-source-integration-001/INTERFACE-001.json`。

## 匹配整包

候选目录为 `build/root-unknown-wt-package-002`，包含Host和WT两个角色、9个组件，无观衡角色或SPA。新版Host/Agent与25个原生安装文件来自本增量同一组已验制品；其余8组件保持原描述和字节。

| 身份 | SHA256 |
|---|---|
| `wt-unknown-candidate.zip` | `981e41960546d8c759d9b1be8215069fc4ff991e5b142b6edc0384e85a06138e` |
| `SYSTEM-RUNTIME.json` | `11165acc66efe67822741863f913d4176f1c350061a474e725377233e27416f4` |
| `installed/SYSTEM-INSTALLATION.json` | `1a4cac3b38a042ec47d2f020bb4523fc85a774b706fa902cdbf61d83ebb4b220` |

公开create、ZIP搬迁extract、离线install和resolve四阶段全部完成并正常收尾，合计409.438秒，原1000秒总预算及各阶段预算保持。包共2317个文件；实际版本、无guanheng_app依赖和中文WT公开CLI核对通过。最终接收记录为 `build/root-unknown-wt-package-002/INTERFACE-CANDIDATE-002.json`。

匹配的23个Python wheel及两条已验SDK案例各自实际使用的5个原生二进制，与本包逐字节相同。Root复用原1000股原单一次、核清O/P后新增200股及最终1200股的实际结果，没有重放业务或复制其金融目录。

首轮候选描述遗漏原执行入口别名，公开create正确拒绝；后继完整保留原entries后在新目录创建。第二轮四项公开步骤均成功，Root末尾核验把`cta_host`的path/sha记录当成字符串，原外层TypeError保留；后继按公开结构只读核对同次产物，没有重装、重启或修改产品。归档内构建时“审查待接收”标记按当时语义保留，本记录关联之后完成的限定审查与合入，归档字节保持。

## 干净主干来源

Root逐一核对121项Native自有构建输入，全部与本次实际编译原件相同；原上游基线及两份已批准覆盖保持。随后从干净主干通过公开source_packages入口离线重建Host、Agent和Core，147个wheel内部成员全部与已验制品相同。Host/Agent的ZIP容器SHA分别记录，解压内容一致；Core整体SHA也相同。没有重复编译同字节Native或重复业务测试。

对应记录为 `build/root-unknown-committed-source-identity-001/INTERFACE-001.json`，原构建收据为 `E:/workspace/wondertrader-qa/root-unknown-source-clean-build-001/BUILD.json`。构建不读取旧QMT业务源码，也不启动真实QMT、账户或交易。

## 剩余与现场

完整交易仍需正式1.1.2金融/KV及数量阶段状态下，携带活动/部分未成交委托的跨进程恢复，继续原身份查询、未成交量抵扣及定向撤单。开发者1负责该完整主链。已完成的未知连续性增量不代表整个模块完成。

市场观察持续公开来源的闭市原件归档和原09:00服务循环由开发者2继续，已交付观衡独立升级。QMT按用户要求暂时关闭；现有WT/Host/采集和数据保持原版本，本候选未启动业务、未切生产、未真实下单或撤单。当前无需用户新增操作或决策。
