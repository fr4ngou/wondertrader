# 分析窗口恢复的完整配置身份

类型：验证证据。范围：[AWP4](../specs/qmt-analysis-window-producer.md#awp4-同配置重启与唯一发布者)。状态：a5 SDK 模块完成，独立 delta 审查及最终系统组合继续。

独审确认 a4 只核 REQUEST 的 capture、日期、行数和证券，工作根未绑定来源连接和发布目标。隔离回归在普通 a4 安装中重现：同根换来源或发布目标仍启动，预期冲突未发生。原 a4 源、wheel、正常四代证据保持。

a5 在 AWP 持有原 OS 租约后，先核 CONFIGURATION.json 的版本化完整规范投影及 SHA，再恢复、归档和启动来源线程。投影绑定来源声明/provenance、工作根与发布目标、Native 路径/SHA、Python/worker 路径和全部刷新参数；秘密值仅由环境提供，文件保留其引用。冲突在状态/请求/发布改写和来源调用前失败，旧文件逐字保持。直接 provider 明确声明纯值身份；旧无身份根保留并拒绝自动接管。

`build/root-analysis-restart-002/normal001` 使用普通 a5/WT a10/Host a11/Agent a9，在同一配置及 owner/publication 根四代 exit0：前两代无来源 ready；第三代恢复原 Pending，32 SDK 方法经真实 WinSHM/3.6.8 正文→8870 原 Import/Reader→3208 QNA/R24；第四代无来源保持原发布 SHA 和实收时间。正常及业务两段原件分列，原 REQUEST 字节保持，输入前后相等。

配置回归分别核连接、provenance、发布目标、相同字节的不同制品/解释器路径、刷新间隔/预算/年龄/日期/行数，以及旧根缺身份。每次来源零调用、旧文件相等。原两项 OS 租约/未确认关闭/Pending/进程退出回归保持。版本范围是稳定 API 合同，实际安装仍由 wheel SHA 和 requirements.lock 精确固定。

本轮 WT/Host/Native/QNA/R24 源码改动零，SDK 通过不授真实 QMT、交易或生产资格。最终 a5 普通组合及系统发行由根统一验收。
