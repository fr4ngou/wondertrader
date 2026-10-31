import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { StrategyPositionState } from './StrategyPositionState'
import type { StrategyWorkbenchDetail } from '../types'

afterEach(cleanup)

describe('策略真实持仓解释', () => {
  it('单独展示未成交的清仓目标和仍在持续的真实周期', () => {
    const report: StrategyWorkbenchDetail['strategy_state'] = {
      strategy_id: 'resonance-regime-v1', strategy_version: '1.1.2', config_id: 'config', target_id: 'target', status: 'evaluated', reasons: [],
      analysis_basis_date: '2026-09-28', analysis_known_at: '2026-09-28T07:00:00Z', analysis_close_prices: { '159780.SZ': .855 },
      checkpoint: { evaluated_at: '2026-09-28T07:00:01Z', source_trade_date: '2026-09-28', analysis_revision: 'a', input_revision: 'b',
        position_cycles: { '159780.SZ': { status: 'held', quantity: 88700, opened_at: '2026-08-03T02:00:00Z', coverage_start_at: '2026-08-01T00:00:00Z', blocking_reasons: [] } },
        holding_days: { '159780.SZ': 40 }, reference_prices: { '159780.SZ': .998 }, target_weights: { '159780.SZ': 0 },
        model_signals: { '159780.SZ': 'BUY' }, exit_paths: { '159780.SZ': 'sc50_trailing_exit' } },
    }
    render(<StrategyPositionState report={report} version="1.1.2" unavailable={false} />)
    expect(screen.getByText('88,700')).toBeInTheDocument()
    expect(screen.getByText('40')).toBeInTheDocument()
    expect(screen.getByText('-14.33%')).toBeInTheDocument()
    expect(screen.getByText(/减仓待完成/)).toBeInTheDocument()
    expect(screen.getByText(/回撤超过 10%/)).toBeInTheDocument()
    expect(screen.getByText(/模型：买入/)).toBeInTheDocument()
    expect(screen.getByText(/退出判断：/)).toHaveTextContent('回撤超过 10%')
  })
  it('来源不可用时显示待恢复', () => {
    render(<StrategyPositionState report={null} version="1.1.2" unavailable />)
    expect(screen.getByText(/来源不可用/)).toBeInTheDocument()
    expect(screen.queryByText('账本确认空仓')).not.toBeInTheDocument()
  })
  it('实际清仓后并列显示旧模型信号和仍有效的退出决定日期', () => {
    const report: StrategyWorkbenchDetail['strategy_state'] = {
      strategy_id: 'resonance-regime-v1', strategy_version: '1.1.2', config_id: 'config', target_id: 'target',
      status: 'evaluated', reasons: [], analysis_basis_date: '2026-09-29', analysis_known_at: '2026-09-29T07:00:00Z',
      analysis_close_prices: { '159780.SZ': .855 }, exit_decision_dates: { '159780.SZ': '2026-09-28' },
      checkpoint: { evaluated_at: '2026-09-29T07:00:01Z', source_trade_date: '2026-09-29', analysis_revision: 'a', input_revision: 'b',
        position_cycles: { '159780.SZ': { status: 'flat', quantity: 0, opened_at: null, coverage_start_at: '2026-08-01T00:00:00Z', blocking_reasons: [] } },
        holding_days: {}, reference_prices: {}, target_weights: { '159780.SZ': 0 },
        model_signals: { '159780.SZ': 'BUY' }, exit_paths: { '159780.SZ': 'sc50_trailing_exit' } },
    }
    render(<StrategyPositionState report={report} version="1.1.2" unavailable={false} />)
    expect(screen.getByText(/模型：买入/)).toBeInTheDocument()
    expect(screen.getByText(/退出决定形成于 2026-09-28/)).toHaveTextContent('实际已清仓；等待更新日线的新买入信号')
    expect(screen.queryByText(/减仓待完成/)).not.toBeInTheDocument()
  })
})


it('尚未达到退出条件时仍展示该证券的规则阈值', () => {
  const report: StrategyWorkbenchDetail['strategy_state'] = {
    strategy_id: 'resonance-regime-v1', strategy_version: '1.1.2', config_id: 'config', target_id: 'target', status: 'evaluated', reasons: [],
    analysis_basis_date: '2026-09-28', analysis_known_at: '2026-09-28T07:00:00Z', analysis_close_prices: { '159780.SZ': .855 },
    checkpoint: { evaluated_at: '2026-09-28T07:00:01Z', source_trade_date: '2026-09-28', analysis_revision: 'a', input_revision: 'b',
      position_cycles: { '159780.SZ': { status: 'held', quantity: 88700, opened_at: '2026-09-15T02:00:00Z', coverage_start_at: '2026-08-01T00:00:00Z', blocking_reasons: [] } },
      holding_days: { '159780.SZ': 9 }, reference_prices: { '159780.SZ': .998 }, target_weights: { '159780.SZ': .2 },
      model_signals: { '159780.SZ': 'BUY' }, exit_paths: {} },
  }
  render(<StrategyPositionState report={report} version="1.1.2" unavailable={false} />)
  expect(screen.getByText('9')).toBeInTheDocument()
  expect(screen.getByText(/本次未产生退出判断/)).toHaveTextContent('持有满 10 个交易日')
  expect(screen.getByText(/本次未产生退出判断/)).toHaveTextContent('回撤超过 10%')
  expect(screen.queryByText(/减仓待完成/)).not.toBeInTheDocument()
})
