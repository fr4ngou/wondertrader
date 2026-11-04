# 2026-11-04 观衡a108统一WT日线接入上线

状态：verified（独立观衡消费者模块）。环境：本机Windows、原18143入口。授权：用户持续开发及独立观衡发布任务，Root分配统一WT消费者模块；Root保留交易、QMT和WT数据角色生命周期。日期：2026-11-04；执行：开发者1。

## 发布身份

| 项目 | 本次实际身份 |
|---|---|
| 正式源码/标签 | `2a4f39758e536335a56902097aa6e37a00446d08` / `release/observer-a108-wtdaily-20261104-001` |
| App | `0.1.0a108+wtdaily.1`，原六项目私有轮子及精确依赖锁离线构建 |
| 493输入CAS SHA256 | `416b4f0af125503c6e58e01d16f02754c454d18426d715fe68df1f93ccd10eec` |
| ZIP SHA256 | `73a68b69fc417a2703a33ce2ae1e637508e5ec41d02e2cfdaaa9548e205e9249` |
| 包manifest SHA256 | `4c6eedb3c9680742bffa2d561f9c07f4a5c03fdcdf0eed0d01da0f0c1545c1ba` |
| 安装记录 SHA256 | `7459cffcfb2dede17e4fa7bbc080b223c95c57a66f58ac7d7c5eb2cb36647cc2` |
| 安装根 | `E:/workspace/wondertrader-data/observer-programs/0.1.0a108+wtdaily.1` |
| 当前读取数据根 | `E:/workspace/wondertrader-data/observer-market-unified-20261104-001` |
| 当前观察快照 | `03d5c25383874dd7dcfb0feb6bb97d367bedd9ebaee7ae78af4a79eec4f7d6a8` |
| 正式来源配置SHA256 | `37d07d82211da1fb9bbad1a13cc7428ea8a2ef1881b9d56d4cd087239349e02d` |
| Web profile SHA256 | `d6623257c2881edf2e4648f4502a8ab6bbc7c107de82053fae3594a489dcf762` |
| 更新PREPARED SHA256 | `2917ec3814c572383e9af527301eab92e18125e8c15dfe2034807267bc7b45ea` |

最终Web为PID46032、启动器68688、控制代`346dc2e6-176f-46b4-8fe8-9b36338b6a99`；独立更新监督为PID75404、启动器46780、子进程2952，控制代`c85e4037-9b66-4e13-83d1-11edeca4258a`。实际进程创建时间、逐项文件摘要及后继运行身份以受控FINAL-DELIVERY和当前部署指针核对。SDK继续精确0.16.0，轮子字节身份以本包manifest核同。

## 预检与步骤

1. 采用已接收WT消费者契约和原公式，增加WT专用前日交易日期策略；29项独立来源定义、原792请求预算、40日批次及三窗口保持。
2. 通过两轴审查；在完整线上副本跑真实WT两来源、保留对比、原快照往返恢复及两版独立更新角色启停。原a107另经原T2108条目实际更新/CAS发布，并核较新历史保持及正常退出。
3. 从正式标签对应493项输入构建，核80项包文件后普通离线安装。136项App、19项SDK及26项SPA逐件匹配；26项SPA与已验a107相同。
4. 原独立更新器正常退出后，在原lease保护下备份最后目录事务和全部不可变对象至E盘。原目录继续保留；正式副本沿原refresh、日期合并及CAS更新WT两来源。
5. 核最终数据保留后封存首次live expected_current，启用新独立更新器；正常关闭旧Web，使用新的不可变profile启动a108。实际执行a108→a107→a108 Web回退并回到最终代，更新角色持续独立运行。
6. 更新当前DEPLOYMENT、UPDATE-DEPLOYMENT及profile别名；原profile、关闭证明、旧安装和后继快照均保留。

## 发布后验真

实际入口为`http://127.0.0.1:18143/observation`。两WT来源均固定版本7370ab6f…及日期11-03；正式刷新184次WT HTTP成功。七项指标两个日期的series与CSV共14组核同；原生日历选择单日后只显示该日一条记录；桌面与390像素窄屏均显示真实T2108数值及覆盖缺口，视口已恢复。

65项独立指标及定义、24表、全部原资产登记和32原快照保持，原运行/窗口记录逐行相同。更新器停止时Web继续读图表；重启保持current、7个已完成窗口及7条尝试，运行记录保持72。Web版本回退期间更新监督与心跳继续；两版Web均沿原关闭流程退出、读取线程归零。原策略页继续自动读取后继CURRENT；先前资金字段缺失及后继发布均随原件更新，最新WT失败状态如实展示。

完整证明、两项既有回归失败和来源限制见[验收记录](../evidence/2026-11-04-observer-wt-daily-consumer.md)。本次观察角色未发送交易动作；交易和资金发布资格继续由Root登记。

## 操作与回滚

使用当前指针查询，避免固定已退出代的PID：

```powershell
$web = Get-Content E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json -Raw | ConvertFrom-Json
& $web.python -I -B $web.tool status --profile $web.source_profile
$update = Get-Content E:/workspace/wondertrader-data/observer-current/UPDATE-DEPLOYMENT.json -Raw | ConvertFrom-Json
& $update.python -I -B $update.controller status --profile live
```

Web维护沿[原入口](../runbooks/observer-runtime.md#隐藏-web-的启动查询正常停止与重启)，将status替换为start/stop/restart。独立更新控制器支持start/status/stop；运行中start保留当前实例并提示查询状态。未知结果按原控制代继续核查。

已验旧Web回退profile位于`E:/workspace/wondertrader-data/observer-web-a107-wtdaily-rollback-20261104-001/formal-001/web-profile.json`，使用保留a107安装的observer-web.py。先正常停止当前Web，再用该profile启动旧版；它保持同一E盘观察目录、个人偏好及CURRENT路径，图表沿保留原行情连接。新a108更新器保持运行。返回a108时同样先停止旧版，再使用本次正式profile；当前指针随实际ready身份发布。

更新器版本回退使用保留的旧来源配置及已核兼容快照，字段能力按旧版登记。完整31来源配置已验加载/启停；实际发布覆盖原T2108兼容入口：完整E盘副本、原封存输入、原预算及service.now QA时钟，成功发布b17b…且保持较新11-03行，随后正常关闭。其余30来源本次未重新采集，新WT来源类型由a108消费。原a107在完整副本上的恢复/再采用已验证；正式目录此次保持后继快照。需要切换数据快照时，先正常关闭对应写入者，使用原观察CLI restore及实际expected-current，保留归档和窗口事实。

最终角色及当前E盘数据已上线；自然新日窗口、WT资金字段和数据owner全类别扩覆盖按其后继事实验收。
