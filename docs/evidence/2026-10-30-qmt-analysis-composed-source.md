# 同正文分析连接的普通安装 SDK 主链

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-30。类型：验证记录。范围：QAC 可选分析连接；独立审查由根会话统筹。

## 实现与职责

沿[QAC规格](../specs/qmt-account-composed-source.md#可选分析读取连接)增加 `analysis_read`、CLI `--analysis-read-pair` 和明确配对/deployment v3。原 resident v7 validator 负责两分析操作及来源身份。材料编解码及完整部署 decoder 各保持单一实现，旧 decoder 拒绝新项；省略分析参数的旧正文、闭包和部署字节保持。

原 Read/TickReadAgent 继续处理连接和业务，Agent代码未变。一个策略正文共享原Context/SDK线程、一个100ms timer和一次QST订阅；交易、账户、分析、HPR依次获得单次重任务，轻量连接/退休继续推进。

## 普通安装与实际主路径

固定 Host a12/Agent a9、WT a11、producer a4/core a1 通过原 ATI 普通离线安装、完整RECORD和pip check。历史/采集工作进程沿独立Host解释器；分析窗口沿WT角色。角色及wheel身份由交付根（外部历史/待归仓路径：`../../build/root-analysis-composed-source-001/README.md`）的接口和冻结清单记录。

`main007` 实际Python3.6.8和Windows SHM运行105.859秒、exit0；2573输入前后相同。同WT七owner保持，原交易四查、插单→查单→撤单SDK替身各1，原生账户四查询65事实/30 ABI槽及浮点位精确；HPR补读、QST→原Writer两根DSB及原Reader五根历史基准通过。

同一正文新增分析完成96个SDK调用，三轮Native Import/Reader、QNA和R24读取；跨日及同日修订产生不同的正式发布身份。冷审159756个Native原始数值字段与来源逐IEEE浮点位相同，附加业务请求0。单timer/订阅、原线程、运输worker0及禁止file/network0均成立。全部Host、WT、来源业务owner和创建期Job/EOF/join/资源正常关闭。

## 保留失败与资格

旧QA前置路径错误、错误解释器角色及owner/PID观测失败原样保留。历史服务在含core普通`integrations`包的WT解释器中会遮蔽原历史bundle namespace；沿原独立Host角色运行后主路径成立。core与完整历史glue同解释器配置的支持另需明确处理。

本记录仅授上述固定安装SDK主链及必要兼容回归；真实QMT、真实下撤单、全市场压力、完整恢复、独立观衡页面和生产保持各自验收范围。
