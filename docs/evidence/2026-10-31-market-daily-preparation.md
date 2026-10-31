# 全市场日线缓存准备与原批量捕获

类型：验证证据。日期：2026-10-31。唯一要求见[规格](../specs/qmt-market-daily-preparation.md)。

原HPR只允许沪深格式。显式limits.v3保持原字段、额度、单证券SDK和截止，接收沪深北
格式。WT外部工作流复用原HPR更新缓存，再用原v8批量读取none/front，沿原slot保留请求、
结果、消费确认和来源时点。原SDK函数返回及实际覆盖分别记录。

## 已执行

固定原5576股票池在实际3.6.8正式单正文/WinSHM替身中，缓存初始为空；5576次原下载
实际改变该内存缓存，508次原批量SDK从同缓存回读。先暂停64项，再由新客户端沿同目录
续接，原64项逐字保持。完成后离线重读零SDK，两个Host的原64容量最终均回收至0。
完整原值逐位核对及每ID原30秒内接收见build中的AUDIT与ORIGINAL-ID-TIMES。

完整池采用source001原普通安装，后继source003增加完成包摘要核验、正式CLI与单次观察
截止收敛。source003普通23发行安装另实跑沪深北三下载及两批次、3168个float64事实，
原未知ID仅lookup的红绿、旧v1/v2默认、损坏摘要拒绝和离线CLI通过。完整池不追认成
source003全池实测，具体复用范围固定在MAINPATH-REUSE-001。

单timer、原SDK线程、零策略文件/网络违规、零运输线程及零金融写成立；五Host和Source
逻辑关闭、创建期Job/EOF/join/句柄回收均依原收据分别登记。全链总D7200秒，单请求
SDK5000ms/原policy/scope30000ms及容量保持。

旧SDK001由QA进度文件replace遇PermissionError终止，37个原SDK结果均已确认消费，
关闭正常；具体外部文件共享者缺少记录。后继QA改为不可变进度快照，旧原件保留。

## 实际与剩余资格

另冷核根已运行的旧v8三证券真实切片：两个原slot、沪深北均可读，缓存尾分别到
20261023/20261030/20261016；无凭据C包保持原批次映射和日期。这份真实材料仅授已有
缓存读取。BJ实际下载、完整5576真实更新、复权与共同闭合日仍待对应实际运行及C核实。
SDK包均标记synthetic，不能进入真实市场指标。

实际唯一入口及原始收据见`build/root-market-daily-preparation-001/INTERFACE-001.json`；
正式cohort由根合并Host持久I/O及组合层后建立。共享Native FullTick若接同HPR v3，
使用根负责的root-native-hpr-v3-001固定制品；根已用同一installation003完成其SDK
消费验收，最终durableIO合并cohort仍单列。本模块没有修改WT框架、账户或交易协议。
