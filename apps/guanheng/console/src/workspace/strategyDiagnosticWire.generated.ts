// 此文件由 scripts/generate-strategy-diagnostic-wire.py 生成；修改V1声明后重新生成并以--check核对。
export const diagnosticWire = {
  /** 唯一V1诊断线协议版本。 */
  schema: "guanheng.strategy-business-diagnostics.v1",
  /** 协议所有者源码摘要；生成校验绑定此身份。 */
  owner_sha256: "ef5f1d1659da2dab0521a4535ad72aaad6075c166e5c435c4695f6486875ceb8",
  /** 角色声明源码摘要；运行数学和策略版本保持原所有者。 */
  profile_sha256: "18c4f9271ff9d3e018a8aeee8d8fd366fb9c1e25e7a0435baa1533a7c821ef53",
  /** 每角色必需的市场字段名，直接取V1声明。 */
  market_fields: ["open","high","low","close","volume","amount"],
  /** 固定证券到角色的原映射；历史可替换角色按原验证器处理。 */
  common_roles: {"510300.SH":"csi300","510050.SH":"sh50","510500.SH":"zz500","512100.SH":"zz1000","588000.SH":"kc50","159780.SZ":"sc50","515080.SH":"dividend"},
  /** 本轮其余一个证券归属的角色，兼容已归档物理证券。 */
  remaining_role: "kc_composite",
  /** 每角色必需分支及字段顺序，直接取V1声明；无信号阈值或计算。 */
  branches: {"csi300":{"resonance_lamps":["share_probability","turnover_percentile","margin_percentile"]},"sh50":{"entries":["shares_delta_yi"],"sh50_large_redemption":["shares_delta_yi"]},"kc50":{"entries":["shares_delta_yi"],"large_subscription_exemption":["shares_delta_yi"]},"kc_composite":{"kc_cluster_reversal":["shares_delta_yi"],"kc_distribution_cluster":["shares_delta_yi"]},"zz500":{"zz500_cluster_reversal":["shares_delta_yi"],"zz500_distribution_cluster":["shares_delta_yi"]},"zz1000":{},"sc50":{},"dividend":{}},
  /** 当前原值验证器源码身份；不复制求值实现。 */
  current_owner_sha256: "f8830b381e01f7f1d6ad2de68b165b6aa058fab725eb00ab44c6ea2e8b344bc9",
  /** 当前原值字段集合，直接取V1当前视图声明。 */
  current_fields: ["shares_delta_yi","share_probability","turnover_percentile","margin_percentile"],
  /** 每字段依赖日期数量上下界，直接解释冻结V1验证器的原常量条件。 */
  current_dependency_ranges: {"shares_delta_yi":[2,2],"share_probability":[2,2],"turnover_percentile":[20,64],"margin_percentile":[20,60]},
  /** 当前原派生版本，直接取V1声明。 */
  current_derivation_version: "resonance-auxiliary-causal-v3",
} as const
