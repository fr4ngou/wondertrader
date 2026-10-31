# AWP 准备间隔身份归一证据

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

范围：AWP4/AWP5 同根重启的等值刷新数值；普通安装 a8/core a2。独立审查由根会话安排。

根因与实现：运行时已把 preparation interval 校验并转为 float，工厂权威身份改用该值，避免 JSON `1`、`1.0` 形成不同 SHA。省略补齐配置的原身份形状保持，真正不同值继续拒绝。

原 a7 普通安装 `red001` 实际第二代重启复现 `analysis_configuration_conflict`；后继 `green001` 三代 `1→1.0→1` 正常关闭及恢复原 Pending 请求，真正改为2时来源调用零、旧状态字节保持。原默认及相关恢复23项从新普通角色运行通过。

固定原件：后继接口（外部历史/待归仓路径：`../../build/root-analysis-history-preparation-002/INTERFACE-001.json`）、[规格](../specs/qmt-analysis-window-producer.md)。未变化的三轮 HPR/v7/原Import/Reader/QNA/R24沿[原主链](2026-10-30-analysis-history-preparation.md)复用；本次无实际QMT、SDK或Native业务请求。

旧 a7 已落盘整数权威根保持，不自动改写既有配置或原请求。整包接线、独立审查和真实后继资格分别验收。
