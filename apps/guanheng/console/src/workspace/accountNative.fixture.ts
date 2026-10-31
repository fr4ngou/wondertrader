import fixture from './account.fixture.json'
import { accountKinds, type AccountGroupV3, type AccountOverviewV3 } from './accountApi'

export function nativeAccountFixture(): AccountOverviewV3 {
  const groups = Object.fromEntries(accountKinds.map(kind => {
    const original = structuredClone(fixture.groups[kind])
    const known = kind === 'position' || kind === 'account'
    const rows = known ? original.rows.map(row => ({ ...row, fields: Object.fromEntries(Object.entries(row.fields).map(([key, value]) =>
      [key, ['quantity','sellable','total_asset','available'].includes(key) ? value : { availability: 'unknown', value: null, reason: '来源未提供' }])) })) : []
    return [kind, { ...original, rows, status: known ? 'complete' : 'unavailable', source: { kind: 'wt_native_observation', scope_id: 'a'.repeat(64) },
      execution_started_at: null, execution_finished_at: null, request_id: null, result_sha256: null,
      reason: known ? 'WT最近发布的券商观察' : 'WT现有观察未提供此类数据', received_at: known ? kind === 'position' ? '2026-10-29T01:30:01Z' : '2026-10-29T01:30:03Z' : null,
      published_at: known ? '2026-10-29T01:30:05Z' : null, revision: known ? kind === 'position' ? 2 : 5 : null }]
  })) as Record<typeof accountKinds[number], AccountGroupV3>
  groups.account.rows[0].fields.available.value = 75000
  groups.account.rows[0].fields.total_asset.value = 100000
  groups.position.rows[0].fields.quantity.value = 700
  groups.position.rows[0].fields.sellable.value = 300
  return { schema_version: '3.0', scan_id: null, read_only: true, aggregate_only: true, status: 'partial',
    runtime_state: 'ready', observed_at: '2026-10-30T01:00:00Z', reason: 'WT最近发布的券商观察；委托与成交明细尚未提供。',
    trade_date: { availability: 'unknown', value: null, reason: '来源未提供' }, groups,
    close: { status: 'not_started', closed: false, joined: false, worker_live: false, queued: 0, exit_code: null, error_code: 'unconfigured' } }
}
