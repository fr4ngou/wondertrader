/** 观衡公开的原版WT策略身份；内部信号算法与可选策略分别标识。 */
export const ORIGINAL_WT_STRATEGY = 'resonance-original-wt-351f9d5-stable'
/** 独立WT原生报告族，人民币本金、整手及撮合按原报告。 */
export const ORIGINAL_NATIVE_REPORT_SCHEMA = 'guanheng.original-native-replay-report.v1'
/** WT输入冻结的原stable信号算法；该值不登记为第二个公开策略。 */
export const ORIGINAL_SIGNAL_ALGORITHM = 'resonance-original-351f9d5-stable'
/** 原版WT策略版本，独立于App和读取侧制品版本。 */
export const ORIGINAL_VERSION = '0.1.0a2'
/** 同一WT报告族的已验版本；旧a1保留原模型，新a2独立核现金约束。 */
export const ORIGINAL_NATIVE_VERSIONS: readonly string[] = ['0.1.0a1', ORIGINAL_VERSION]
/** 现金约束版沿用原生限价撮合；旧a1执行模型单独保留。 */
export const ORIGINAL_CASH_EXECUTION = 'D-close-intent; WT-native-limit-next-tick; unfilled-intent-retained'
