# 两份400期报告的读取成本后继

类型：模块B自有纯报告读取开发检查点。状态：in-progress。要求沿[NBC-R8](../specs/native-backtest-cli.md#nbc-r8-原报告读取的字节预算与消费性能)。C原请求固定在build/comparison-context-observer-001/C-READ-PERFORMANCE-REQUEST-002.json；C源与普通安装、原两份完成目录保持。

## 当前发现与实现

C已记录原5秒HTTP比较与错误恢复超时；B本机同普通a57/a11原版的baseline002完成三次比较、坏证明409和同身份恢复，比较3.234至3.625秒。负载下既有失败保留，本轮没有稳定重现同一503。baseline001的QA未消费HTTP错误响应，关闭被有限Job强制回收，业务结果未完整存证；后继QA显式消费/关闭响应，并在正常关闭前登记业务结果。001原件保留，不计合格产品证据。

原单份400报告的受控cProfile有276456次树visit、244158次通用JSON dumps调用；snapshot累计1.020秒、通用编码累计0.483秒，整份含分析器约3.016秒。该测量只用于定位成本。后继生产修改只在report_values.py：字符串长度直接使用标准JSON encode_basestring_ascii，有限整数/浮点沿标准repr，布尔/null按JSON字面量计数。类型/容量/树复制、检查回调频率、控制异常及冻结/领域验证保持。金融与算法核实现变化0，WT变化0。

## 验证及实际边界

report_snapshot.py先在原安装通过4组合同，后在自有源码通过相同合同：紧凑ensure_ascii的恰额度接受/少一字节拒绝，所有标量类别、Unicode/代理项与非BMP、深度/节点、大整数和非有限值、检查次数/原异常对象、复制/不可变投影隔离。原版2.701秒，新源码0.994秒，仅代表该组合测试输入。

同一report_read_http.py沿普通App CLI的装配和实际HTTP读取原两份不同400目录；QA只增加标准Server正常停止信号，不修改产品路由/5秒预算。原版baseline002和source-http001均完成三次比较、坏证明409及同身份恢复，各56个原件零漂移，所有内外Job正常退出、树零、EOF、读线程join、资源关闭。新源码比较3.250至4.813秒，源与原版不在同一负载时刻，本轮证据不支持宣称HTTP变快或超时问题已解决。

原件根为build/ms-report-read-baseline-001/002、ms-report-read-profile-001、ms-report-read-contract-old-001/new-001、ms-report-read-source-http-001；冻结原WT源在build/ms-report-read-performance-001/baseline-source。修改后的report_values.py SHA为6ed30e2f6dfee6ede78961e406519672ffc6f6a8f893250ed779ff3acdb5f2f5。当前为源码组合，尚未重建普通WT发行、全面回归/独立审查或交付给C/A集成；原a11封存材料不回写。

下一步继续同负载测量、既有报告族回归及安装后主链；若新源码不能改善完整消费问题，按实测收敛责任层。用户后继取消旧开仓历史迁入，其范围沿[初始库存方案](../migration/retained-strategy-takeover-proposal.md)，本项报告读取工作保持独立。全部新增项目产物位于E盘，实际账户操作0。
