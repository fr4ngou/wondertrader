# 历史实验组合的上游源码输入复核

类型：构建输入与资格更正。状态：已确认未批依赖；公开ABI替代实施中。固定上游`08b230dd`；后继规格[NHA](../specs/native-history-public-abi.md)。

## 已确认事实

NHP的输入清单、Ninja编译/链接关系与实际DLL摘要共同证明：历史实验组合读取当前工作树vendor源码，其中保留CORE-001/002/003/005冻结差异。`core-before`摘要不变证明本轮没有继续改动这些文件；它没有证明构建只含用户批准的修改。

| 差异 | 实际作用 |
|---|---|
| CORE-001标准库名称限定 | 修改头参与Helper、Reader、Writer和Factory编译；结构字段/对齐没有发现因此变化 |
| CORE-002store_bars检查/返回 | History直接调用修改版store_bars，之后另做完整回读 |
| CORE-003新增limited ABI | History的merge、回读、freeze/recover及非IRdm查询直接调用；Python NativeHistory也寻找该未批导出 |
| CORE-005Writer生命周期 | 完整Storage DLL链接修改后的Writer；历史路线仅创建IRdm，当前证据没有表明实例化Writer |
| NRC空Reader计数 | 当前Reader相对上游仅用户已批准分支、括号与中文原因注释 |

实际链：`cmake/native/CMakeLists.txt`从`${WT_ROOT}/src`构建vendor；自有Data链接Helper/Tools/Utils。NHP Ninja的Writer、IRdm、Helper和Factory输入及依赖已只读交叉核对。WTSUtils/WTSTools和Factory本体无行为diff，Factory仍读修改后的公共头。

## 现有证据的正确范围

NHQ/NQW/NHP、428行及依赖它们的业务整链结果继续绑定原实验输入，源码/数据值/线程行为观察保留；原样或仅获批vendor组合的可交付性尚未证明。这些结果不授予冻结核心修改的保留/发布权限，当前停止把该组合称为纯上游历史能力验证。原NQB只读交易bootstrap使用另一个逐Git blob固定原生快照，范围分别登记。

主任务已向用户说明这一发现。此次调查没有修改、还原或编译vendor，也没有访问账户、真实QMT、订阅、下载或数据库。

## 原接口边界及替代

原`read_dsb_bars`保留路径/回调/计数能力，先全量读入再解压。原`WTSCmpHelper`按帧声明分配，原IRdm首次加载也全量解压；count=N只约束返回选择。自有入口须先验证压缩体/头/单帧/已知raw/Bar数，再固定同一不可变字节源交原ABI，保留原解码、索引和Factory。

原`store_bars` ABI未变；其bool对创建/写失败传播有限。自有发布拥有独占新输出、完整原ABI回读及来源摘要的一致判定，并验证短写、旧.pending和替换。该职责不要求修改原Helper。已有`native_rows`可收敛复用；现仅查路径前后摘要不能消除两次打开之间的替换窗口。

下一构建在新唯一目录提取固定Git blob，历史目标只叠加已批准NRC；通过构建侧C++`/FIobjbase.h`和`NOMINMAX`处理名称冲突，沿已验original-build工具链复用缓存。自有C++和Python消费者显式迁移到自有安全边界及清晰命名的ABI；旧vendor、实验包和真实输入全部保留。

## 绑定身份

NHP清单SHA256：`3f0c4541bf4bd2e02ee90591193894bbc95bb93cc48635a0d3e50713e25914bc`；旧core-before：`15fcd259a7d5678c77f4b869d00569a839a5be40bbcdcfa8ac1a173b2d91e359`。

| 输入/产物 | SHA256 |
|---|---|
| WTSDataDef.hpp | `96b5ea63beddb3eee3bae4f86107bdb7c4cf1192d1cb5a18ce751b4e79180d3f` |
| WtDtHelper.cpp | `ba840920289323cea93deecd4375798e9196c5a39c1032389a2893ddf7cc8ab2` |
| WtDtHelper.h | `2ee62235448087426ac1c478a3e0ca0e80e4fa8b4e2721fb412d4a7c6cb2830a` |
| WtDataWriter.cpp | `2c6ffeaac444299da5f0b1986e8e8203b9e13435af882ad06183e848eb30cca2` |
| WtRdmDtReader.cpp（NRC） | `d3de2222e76082acd3c114831bcb2b1b30b7b11da405bed73e7d2cb96d880af5` |
| NHP Storage.dll | `240f03a0b1d1b2e8253a1c0f08b69b2382cc9bd3ededff1754b85047d2954725` |
| NHP Helper.dll | `6ca0fcac9d25edae08464d94aa2c428267071fa57e135a6401ad14e2f5d8f151` |
