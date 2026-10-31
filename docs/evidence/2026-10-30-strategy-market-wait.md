# 策略行情等待的只读展示

状态：限定修复开发与安装验收完成。最终a45普通及两全新根离线安装完成，离线原CLI/生产SPA实际等待、矛盾发布拒绝、读取失败及恢复通过；最终独立delta双轴通过。完整模块C、真实来源联合和生产资格分别保留。

## 根因与实现

B的NRT-R24正式发布`waiting_market_input`，在行情窗口尚未齐备时保留券商观察，尚无策略核结果。C原投影的状态集合未包含这一状态，将有效发布拒绝为503。`build/strategy-market-wait-001/REPRO-BEFORE.json`保留用B原件触发旧投影ValueError的证据。

本次在既有纯投影和浏览器状态白名单中接纳该正常等待，页面显示“等待策略所需行情”。未生成的目标和理论值保持未知；券商数量、可卖及原接收时间沿原发布。未知状态、坏格式和身份校验继续沿原失败语义。观衡读取不创建WT、Host或查询owner。

## 验证与范围

- `CHECKS-003.json`：六项后端根因/HTTP回归与八项前端状态/恢复验证通过。初始两次后端QA因解释器依赖缺失失败，原件保留；后继使用已有完整解释器和当前源码，未修改产品依赖以绕过问题。
- `FRONTEND-BUILD-001.json`：类型与生产构建通过；SPA身份在`SPA-001.json`。
- `main-001/RESULT.json`：普通a44原CLI及生产SPA读取B原等待和卖出报告，实际HTTP等待200→损坏发布503→卖出200。IAB实际确认中文等待、原持仓时间、失败保旧、恢复后200份持仓与阶段目标区分。App退出0，原Job树、EOF、线程join及资源关闭通过，输入前后保持。
- 主链发布者为明确协议fixture，报告样本来自B原件；本轮没有启动实际WT/QMT或发起来源请求，不把该范围提升为真实来源联合验收。当前用户18126预览保持原安装。

运行原件位于`build/strategy-market-wait-001`，QA源码位于`E:/workspace/wondertrader-qa/c-market-wait-001`。普通安装、离线安装及审查身份按后继固定交接登记。

## 最终候选与审查修正

首轮规格delta提出等待状态携旧目标可能造成矛盾，最终a45在原投影入口统一要求此状态无core_result/outcome，损坏帧沿原503。新增两项投影变异及HTTP冲突帧回归通过，原a44制品保留历史身份。另一个见证编码问题已核为原QA默认CP936写入，原字节保留并提供带原SHA的UTF8转录；最终main003见证显式UTF8，页面中文经实际CUA复核。

最终普通安装`install-002`，离线`package-002`两根各29发行及pip check通过。`INSTALLATION-IDENTITY-002.json`逐件复核三套原runtime收据各4822文件、29wheel/锁与98个App Python模块；18个SPA文件与已验构建一致。ZIP SHA256为`dc592297e8b73d10665e654a483fac10f1c9a726774b7a82a7309af07ad64f3a`，manifest为`b7e8299a5d24bc58d6acc26157bfc560fab340e2e69cc471a6d4ff23421c3c76`。

最终`main-003`直接运行离线安装的原CLI，实际HTTP与IAB确认正常等待、矛盾帧503、坏发布503保旧、卖出恢复；全部输入保持、App退出0及原Job/树/EOF/join/资源关闭通过。本轮发布者仍为协议fixture，原B样本资格和运行发布者分别登记。最终两轴补审及精确交接另列，用户18126保持原版本。

最终`REVIEW-SPEC-002.md`与`REVIEW-STANDARDS-002.md`对69件固定输入前后核验，状态/目标P3关闭，原见证损坏判断更正为CP936误读，无新增P级。规范审查独立复核三套原runtime收据文件及App/SPA身份。`PROJECT-CHECK-001.json`通过文档导航和技能完整性检查；此静态检查不授业务或发布资格。固定交接沿`build/strategy-market-wait-001/DELIVERY-001.json`及`CURRENT.json`，A唯一集成；本轮没有切换用户预览、生产或真实交易。
