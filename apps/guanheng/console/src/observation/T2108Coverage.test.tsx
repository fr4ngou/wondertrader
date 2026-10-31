import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { T2108Coverage } from './T2108Coverage'

afterEach(cleanup)

it('reads a pre-migration cached point using its unchanged definition version', () => {
  render(<T2108Coverage definitionVersion="t2108.ashare/1" row={{ adjustment_unverified_count: 2 }} />)
  expect(screen.getByText('原观察点，按当时核验口径保留。')).toBeTruthy()
  expect(screen.getByText(/复权待核 2 只/)).toBeTruthy()
})

it('keeps the old factor-review meaning on a historical observation', () => {
  render(<T2108Coverage row={{ method_version: 't2108.ashare/1', eligible_count: 1, market_count: 2, adjustment_unverified_count: 1 }} />)
  expect(screen.getByText('原观察点，按当时核验口径保留。')).toBeTruthy()
  expect(screen.getByText('原收盘参考核验口径')).toBeTruthy()
  expect(screen.getByText(/复权待核 1 只/)).toBeTruthy()
})

it('identifies current supplier computation and its actual partial coverage', () => {
  render(<T2108Coverage mixedMethods row={{ method_version: 't2108.ashare/2', source_kind: 'actual-qmt', eligible_count: 3, market_count: 5576, adjustment_unverified_count: 0 }} />)
  expect(screen.getByText('QMT当前等比前复权观察。')).toBeTruthy()
  expect(screen.getByText('供应商前复权序列口径')).toBeTruthy()
  expect(screen.getByText('此区间包含不同计算口径，历史点保留原值；请在原始数据中核对各点口径。')).toBeTruthy()
  expect(screen.getByText(/前复权不可用 0 只/)).toBeTruthy()
  expect(screen.getByText('当前比例以合格股票为分母；完整市场占比等待来源补齐。')).toBeTruthy()
})
