import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import type { MarketChartBundle } from '../types'
import SourceHistoryStatus from './SourceHistoryStatus'

afterEach(cleanup)
const bundle: MarketChartBundle = {
  schema_version: '1.7', symbol: '510300.SH', period: '1m', data_available: true,
  candles: [{ occurred_at: '2026-10-28T01:31:00Z', open: 10, high: 11, low: 9, close: 10.5, volume: 12.5 }],
  source_observation: { source_schema: 'qmt.source-selection-observation.v1', state: 'Partial',
    source_window: { from_at: '2026-10-28T01:31:00Z', to_at: '2026-10-28T01:32:00Z' },
    source_rows: 2, requested_limit: 300, selected_rows: 1, preparation_state: 'Unknown',
    preparation_request_id: '00000000-0000-4000-8000-000000000001' },
  source_provenance: [{ offset: 0, count: 1, first_at: '2026-10-28T01:31:00Z', last_at: '2026-10-28T01:31:00Z',
    metadata: { source: { provider: 'Qmt', instance_id: 'original-instance', session_id: 'original-session', generation: 3 },
      qualification: 'DevelopmentVerified', dataset_version: '<script>dataset</script>', source_license: 'unknown',
      adjustment: 'none', factor_version: '', minute_boundary: 'unknown', timezone: 'Asia/Shanghai', content_id: 'a'.repeat(64),
      value_semantics: 'source', timestamp_semantics: 'source_label', price_unit: 'unknown', volume_unit: 'lot', amount_unit: 'unknown' } }],
}

test('完整响应保留原诊断数据，用户页面保持简洁', () => {
  for (const state of ['Observed', 'Archive'] as const) {
    const { container, unmount } = render(<SourceHistoryStatus bundle={{ ...bundle,
      source_observation: { ...bundle.source_observation!, state, preparation_state: 'NotNeeded' } }} />)
    expect(container).toBeEmptyDOMElement()
    unmount()
  }
})

test('部分行情只说明缺失影响和处理方式，内部身份始终不进入页面', () => {
  const { container } = render(<SourceHistoryStatus bundle={bundle} />)
  expect(screen.getByRole('status')).toHaveTextContent('部分历史行情缺失，当前显示已取得的数据。')
  expect(screen.getByRole('status')).toHaveTextContent('历史数据更新结果待确认，请稍后重新读取。')
  for (const value of ['original-instance', 'original-session', '<script>dataset</script>', 'a'.repeat(64),
    '00000000-0000-4000-8000-000000000001', '数据集', '内容摘要', '来源实例', '来源会话', '查看分段来源']) {
    expect(container).not.toHaveTextContent(value)
  }
  expect(container.querySelector('details, script')).toBeNull()
})

test.each([
  ['Pending', '正在更新历史数据，请稍后重新读取。'],
  ['Unavailable', '历史数据暂时无法补齐，请稍后重试。'],
  ['NotSupported', '当前可读取的历史范围有限。'],
  ['Budget', '本次历史数据更新已暂停，可稍后重试。'],
] as const)('补齐状态%s表达用户可执行的动作', (preparation_state, label) => {
  render(<SourceHistoryStatus bundle={{ ...bundle, source_observation: { ...bundle.source_observation!, preparation_state } }} />)
  expect(screen.getByRole('status')).toHaveTextContent(label)
})

test('空、失效及旧响应隐藏已过期的说明，恢复后显示当前数据状态', () => {
  const { container, rerender } = render(<SourceHistoryStatus bundle={bundle} />)
  for (const current of [
    { ...bundle, data_available: false }, { ...bundle, candles: [] },
    { ...bundle, source_observation: undefined },
  ]) {
    rerender(<SourceHistoryStatus bundle={current} />)
    expect(container).toBeEmptyDOMElement()
  }
  rerender(<SourceHistoryStatus bundle={bundle} />)
  expect(screen.getByRole('status')).toHaveTextContent('部分历史行情缺失')
})
