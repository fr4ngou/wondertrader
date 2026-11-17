/** 独立WT原生报告族，人民币本金、整手及撮合按原报告。 */
export const ORIGINAL_NATIVE_REPORT_SCHEMA = 'guanheng.original-native-replay-report.v1'
/** WT输入冻结的原stable信号算法；该值不登记为第二个公开策略。 */
export const ORIGINAL_SIGNAL_ALGORITHM = 'resonance-original-351f9d5-stable'
/** 次交易日开盘分钟模型，使用原信号与独立执行证券。 */
export const ORIGINAL_OPEN_EXECUTION = 'D+1 09:31 closed bar limit; WT CtaMocker 09:32 matching'
/** 现金约束版沿用原生限价撮合；旧a1执行模型单独保留。 */
export const ORIGINAL_CASH_EXECUTION = 'D-close-intent; WT-native-limit-next-tick; unfilled-intent-retained'
