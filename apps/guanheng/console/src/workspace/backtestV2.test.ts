import { afterEach, expect, it, vi } from 'vitest'
import source from './backtest-v2-days.fixture.json'
import configured from './backtest-day.fixture.json'
import { fetchReadJson } from '../api'
import { fetchBacktestDay } from './backtestApi'
import { validateV2Summary } from './backtestV2'
import packageProfiles from '../../../guanheng_app/v2_package_profiles.json'

vi.mock('../api', () => ({ fetchReadJson: vi.fn() }))
afterEach(() => vi.resetAllMocks())
const owner = 'a'.repeat(32); const request = '1'.repeat(32)
type Wire = Record<string, any> // Tests deliberately mutate adversarial JSON values.
const clone = (value: unknown): Wire => structuredClone(value) as Wire
const day = () => clone(source.overweight[2])

it('旧归档和新发行组均可读，版本/真实wheel摘要/依赖组必须一致', () => {
  const old = day()
  expect(validateV2Summary(old.evaluation_summary, old.record.trading_date)).toBe(old.evaluation_summary)
  const current = packageProfiles.profiles.find(profile => profile.profile_id === packageProfiles.current_profile)!
  const value = day()
  for (const row of [value.evaluation_summary.signal_trace, value.evaluation_summary.pipeline.signal]) {
    row.core_version = current.core_version; row.core_wheel_sha256 = current.core_wheel_sha256
  }
  value.evaluation_summary.pipeline.dependencies['guanheng-strategy-signals'] = current.signal_version
  expect(validateV2Summary(value.evaluation_summary, value.record.trading_date)).toBe(value.evaluation_summary)
  for (const field of ['core_version', 'core_wheel_sha256', 'signal_version'] as const) {
    const mixed = day()
    if (field === 'signal_version') mixed.evaluation_summary.pipeline.dependencies['guanheng-strategy-signals'] = current.signal_version
    else for (const row of [mixed.evaluation_summary.signal_trace, mixed.evaluation_summary.pipeline.signal]) row[field] = current[field]
    expect(() => validateV2Summary(mixed.evaluation_summary, mixed.record.trading_date)).toThrow('格式或身份无效')
  }
})
async function parse(value: Wire, hash?: string) {
  vi.mocked(fetchReadJson).mockResolvedValue(value)
  return fetchBacktestDay(owner, request, value.index, undefined, hash)
}

it('两份原DLL报告只通过公开日投影消费，保留真实信号/执行角色与超额原值', async () => {
  for (const value of [...source.roles, ...source.overweight]) {
    const parsed = await parse(clone(value), value.report_sha256)
    expect(parsed.report_schema).toBe('nsb-v2-report-v1')
  }
  const value = await parse(day())
  expect(value.record.status).toBe('blocked_raw_total')
  expect((value.evaluation_summary as Wire).pipeline.allocation.raw_diagnostic.total_weight).toBe(1.125)
  expect(value.record.submit_vector).toEqual([])
  expect(value.record.capture?.observation.positions.map(p => p.symbol)).toContain('589000.SH')
  expect((value.evaluation_summary as Wire).pipeline.allocation.latest_raw_weights.map((p: unknown[]) => p[0])).toContain('589680.SH')
})

it('configured旧响应和摘要无schema字段继续可读', async () => {
  const value = await parse(clone(configured), configured.report_sha256)
  expect(value.record.capture?.basis.nav_cny).toBe('100000')
  expect(value.report_schema).toBeUndefined()
})

it('V2预热summary=null有效，非预热空摘要拒绝', async () => {
  const value = day(); value.evaluation_summary = null
  value.record = { ...value.record, status: 'warming_up', capture: null, outcome: null }
  expect((await parse(value)).evaluation_summary).toBeNull()
  value.record.status = 'blocked_raw_total'
  await expect(parse(value)).rejects.toThrow('格式或身份无效')
})

const mutations: [string, (v: Wire) => void][] = [
  ['未知报告schema', v => { v.report_schema = 'nsb-other' }],
  ['V2摘要漏schema', v => { delete v.report_schema }],
  ['configured携带V2摘要', v => { v.report_schema = 'nsb-report-v2' }],
  ['未知策略版本', v => { v.evaluation_summary.pipeline.signal.strategy_version = '2.0' }],
  ['策略ID数组', v => { v.evaluation_summary.pipeline.signal.strategy_id = ['resonance-regime-v2'] }],
  ['pipeline摘要数组', v => { v.evaluation_summary.pipeline.pipeline_sha256 = ['a'.repeat(64)] }],
  ['未来日期错配', v => { v.evaluation_summary.signal_trace.evaluation_end = '2024-03-29' }],
  ['另一profile', v => { v.evaluation_summary.signal_trace.signal_profile = 'legacy-runtime-full-prefix-v1' }],
  ['增长决策不是日摘要', v => { v.evaluation_summary.signal_trace.decision_series[0].decisions = [{}] }],
  ['原始权重缺证券', v => { v.evaluation_summary.pipeline.allocation.latest_raw_weights.pop() }],
  ['权重证券重复', v => { v.evaluation_summary.pipeline.allocation.latest_raw_weights[0][0] = '510300.SH' }],
  ['原始权重非有限', v => { v.evaluation_summary.pipeline.allocation.latest_raw_weights[0][1] = Infinity }],
  ['篡改超额事实', v => { v.evaluation_summary.pipeline.allocation.raw_diagnostic.exceeds_one = false }],
  ['篡改准入bool', v => { v.evaluation_summary.target_admission.accepted = 'false' }],
  ['超额却标接受', v => { v.evaluation_summary.target_admission.accepted = true; v.evaluation_summary.target_admission.code = 'accepted' }],
  ['未知policy', v => { v.evaluation_summary.target_admission.policy_id = 'scale-to-one' }],
  ['超额仍提交', v => { v.record.submit_vector = clone(source.roles[0]).record.submit_vector }],
  ['资格不明自动verified', v => { v.evaluation_summary.producer_readiness.source_qualified = true }],
  ['实际数量字符串', v => { v.record.capture.observation.positions[0].actual = '100' }],
  ['可卖大于实际', v => { v.record.capture.observation.positions[0].sellable = 999 }],
  ['持仓重复', v => { v.record.capture.observation.positions[0] = v.record.capture.observation.positions[1] }],
  ['未决数量负数', v => { v.record.capture.observation.positions[0].pending_target = -1 }],
  ['未验证原生观察', v => { v.record.capture.observation.verified = false }],
  ['无效资金', v => { v.record.capture.basis.cash_cny = 'NaN' }],
  ['目标vector非数组', v => { v.record.submit_vector = {} }],
  ['readback越界', v => { v.record.readback = Array(9).fill(['SSE.ETF.510300', 100]) }],
  ['readback超安全整数', v => { v.record.readback = [['SSE.ETF.510300', 2 ** 53]] }],
  ['非法交易日', v => { v.record.trading_date = 20240230 }],
  ['额外公开字段', v => { v.internal_private_path = 'PRIVATE_NOT_FOR_UI' }],
  ['文本容量超界', v => { v.scope = 'x'.repeat(524289) }],
]
it.each(mutations)('%s：固定去敏拒绝且不展示部分V2', async (_, change) => {
  const value = day(); change(value)
  await expect(parse(value)).rejects.toThrow('回测数据格式或身份无效，请重新读取')
})

it('同页report SHA必须与当日详情一致', async () => {
  await expect(parse(day(), '0'.repeat(64))).rejects.toThrow('格式或身份无效')
  const value = day(); vi.mocked(fetchReadJson).mockResolvedValue(value)
  await expect(fetchBacktestDay(owner, request, value.index, undefined, value.report_sha256, 20240325)).rejects.toThrow('格式或身份无效')
})

it('准入后数量向量与本次提交矛盾时拒绝', async () => {
  const value = clone(source.roles[0]); value.record.submit_vector = []; value.record.readback = []
  await expect(parse(value)).rejects.toThrow('格式或身份无效')
})

it('纯摘要入口也有限计量，不依赖调用方先验', () => {
  const value = day().evaluation_summary
  value.scope = 'x'.repeat(524289)
  expect(() => validateV2Summary(value, 20240327)).toThrow('格式或身份无效')
})

const contradictions: [string, (v: Wire) => void][] = [
  ['八项全零但报告总权重仍为112.5%', v => {
    const allocation = v.evaluation_summary.pipeline.allocation
    allocation.latest_raw_weights.forEach((p: unknown[]) => { p[1] = 0 })
    allocation.state.previous_raw_weights = clone(allocation.latest_raw_weights)
  }],
  ['精确总和为零但浮点总和仍为112.5%', v => { v.evaluation_summary.target_admission.raw_total_fraction = '0' }],
  ['同日同证券末特征的两份投影不一致', v => { v.evaluation_summary.pipeline.latest_features[0].change_pct = 123.456 }],
  ['旧事件被声明为当日新事件', v => {
    const allocation = v.evaluation_summary.pipeline.allocation
    allocation.latest_event_date = '2024-03-26'; allocation.new_event_for_cutoff = true
  }],
  ['事件早于评估起点', v => {
    const allocation = v.evaluation_summary.pipeline.allocation
    allocation.latest_event_date = '2024-03-24'; allocation.new_event_for_cutoff = false
  }],
  ['没有事件却声明出现当日事件', v => {
    const allocation = v.evaluation_summary.pipeline.allocation
    allocation.latest_event_date = null; allocation.latest_raw_weights = null; allocation.state.previous_raw_weights = null
    allocation.new_event_for_cutoff = true
  }],
]
it.each(contradictions)('%s：公开日入口拒绝同份摘要的矛盾事实', async (_, change) => {
  const value = day(); change(value)
  await expect(parse(value)).rejects.toThrow('回测数据格式或身份无效，请重新读取')
})

function numericSummary(values: number[], total: number, fraction: string, accepted: boolean): Wire {
  const value = day().evaluation_summary
  const allocation = value.pipeline.allocation
  allocation.latest_raw_weights.forEach((p: unknown[], i: number) => { p[1] = values[i] })
  allocation.state.previous_raw_weights = clone(allocation.latest_raw_weights)
  allocation.raw_diagnostic.total_weight = total
  allocation.raw_diagnostic.exceeds_one = total > 1
  allocation.raw_diagnostic.exceeds_pre_risk_capacity = total > allocation.raw_diagnostic.pre_risk_capacity
  value.target_admission = { ...value.target_admission, accepted, code: accepted ? 'accepted' : 'blocked_raw_total', raw_total_fraction: fraction }
  return value
}

it('末特征对象的键顺序不改变同份事实', () => {
  const value = day().evaluation_summary
  value.pipeline.latest_features = value.pipeline.latest_features.map((row: Wire) => Object.fromEntries(Object.entries(row).reverse()))
  expect(validateV2Summary(value, 20240327)).toBe(value)
})

it('八项小数累加保留IEEE舍入差异，不改写后端原始权重', () => {
  const value = numericSummary(Array(8).fill(.1), .8, '4/5', true)
  expect(validateV2Summary(value, 20240327)).toBe(value)
  expect(value.pipeline.allocation.latest_raw_weights.every((p: unknown[]) => p[1] === .1)).toBe(true)
})

it('精确小数总和超过1但浮点诊断恰为1时，保留精确准入阻断', () => {
  const value = numericSummary([.25, .25, .25, .25000000000000001, .00000000000000001, 0, 0, 0], 1, '100000000000000001/100000000000000000', false)
  expect(validateV2Summary(value, 20240327)).toBe(value)
  value.target_admission.accepted = true; value.target_admission.code = 'accepted'
  expect(() => validateV2Summary(value, 20240327)).toThrow('格式或身份无效')
})

it('零权重不能用绝对容差接受非零总和', () => {
  const value = numericSummary(Array(8).fill(0), 1e-20, '1/100000000000000000000', true)
  expect(() => validateV2Summary(value, 20240327)).toThrow('格式或身份无效')
})

it('没有分配事件时允许严格零总和与空权重', () => {
  const value = numericSummary(Array(8).fill(0), 0, '0', true)
  const allocation = value.pipeline.allocation
  allocation.latest_event_date = null; allocation.latest_raw_weights = null; allocation.state.previous_raw_weights = null
  allocation.new_event_for_cutoff = false
  expect(validateV2Summary(value, 20240327)).toBe(value)
})
