import { expect, test } from 'vitest'
import { chartHoverDay, daySummaryLines } from './BacktestVisualChart'

test('成交标记序号与主曲线日序不同，优先使用真实轴日期', () => {
  const days = [20261103, 20261104, 20261105]
  const labels = new Map([['2026-11-05', 20261105]])
  expect(chartHoverDay({ axisValue: '2026-11-05', seriesType: 'scatter', dataIndex: 0 }, days, labels)).toBe(20261105)
  expect(chartHoverDay({ seriesType: 'scatter', value: [2, 100], dataIndex: 0 }, days, labels)).toBe(20261105)
})

test('悬停明确区分空仓、无成交和未知，读现成摘要即可', () => {
  expect(daySummaryLines([20261105, [], [], [], 0], '主报告')).toEqual(['主报告 · 当日日末持仓', '空仓', '当日无成交', '点击固定日期详情'])
  expect(daySummaryLines([20261105, null, null, null, null], '对比报告')).toContain('持仓未知')
  expect(daySummaryLines([20261105, null, null, null, null], '对比报告')).toContain('当日成交未知')
  expect(daySummaryLines(undefined, '对比报告')).toContain('对比报告持仓与买卖摘要暂不可用')
})
test('持仓与两边成交按证券摘要，完整数量留给固定详情，未知方向保留笔数', () => {
  const value = daySummaryLines([20261105, [['SSE.ETF.510300', '200']], [['SSE.ETF.510300', '300']], [['SSE.ETF.510300', '100']], 1], '主报告')
  expect(value).toContain('沪深300')
  expect(value).toContain('买入 沪深300')
  expect(value).toContain('卖出 沪深300')
  expect(value).toContain('其它方向成交 1 笔')
})
