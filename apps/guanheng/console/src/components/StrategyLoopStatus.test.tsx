import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { StrategyLoopStatus } from './StrategyLoopStatus'
import type { AutomationRuntimeStatus } from '../types'

afterEach(cleanup)
const runtime: AutomationRuntimeStatus = {
  schema_version: '1.0', generated_at: '2030-01-02T02:00:00Z', automation_gate: 'enabled',
  loop_state: 'advancing', business_health: 'healthy', trading_impact: 'none',
  last_observed_at: '2030-01-02T02:00:00Z', last_successful_loop_at: null,
  source_component: 'portfolio', issues: [],
}
test('explains a running account loop without inventing an order attempt', () => {
  render(<StrategyLoopStatus runtime={runtime} coverage="complete" />)
  expect(screen.getByText('账户自动循环已开启')).toBeVisible()
  expect(screen.getByText('循环正在运行 · 业务正常')).toBeVisible()
  expect(screen.getByText(/具体买卖仍按所选策略/)).toHaveTextContent('记录提示先等待卖出完成时')
  expect(screen.getByText(/最近观察/)).toHaveTextContent('暂无成功记录')
})
test('retains actual blocked or unavailable authority instead of promoting it to running', () => {
  const view = render(<StrategyLoopStatus runtime={{ ...runtime, loop_state: 'blocked', business_health: 'blocked' }} coverage="complete" />)
  expect(screen.getByText('循环已阻断 · 交易受阻')).toBeVisible()
  view.rerender(<StrategyLoopStatus runtime={runtime} coverage="partial" />)
  expect(screen.getByText('账户自动循环状态不可确认')).toBeVisible()
  expect(screen.queryByText('循环正在运行 · 业务正常')).not.toBeInTheDocument()
  view.rerender(<StrategyLoopStatus runtime={{ ...runtime, automation_gate: 'stopped', loop_state: 'blocked', business_health: 'blocked' }} coverage="complete" />)
  expect(screen.getByText('账户自动循环已停止')).toBeVisible()
  expect(screen.getByText('循环已阻断 · 交易受阻')).toBeVisible()
  expect(screen.queryByText('循环正在运行 · 业务正常')).not.toBeInTheDocument()
  view.rerender(<StrategyLoopStatus runtime={{ ...runtime, automation_gate: 'disabled', loop_state: 'waiting', business_health: 'degraded' }} coverage="complete" />)
  expect(screen.getByText('账户自动循环已关闭')).toBeVisible()
  expect(screen.getByText('正常等待 · 业务降级')).toBeVisible()
  view.rerender(<StrategyLoopStatus runtime={{ ...runtime, automation_gate: 'unavailable', loop_state: 'blocked', business_health: 'unavailable' }} coverage="complete" />)
  expect(screen.getByText('账户自动循环开关不可用')).toBeVisible()
  expect(screen.getByText('循环已阻断 · 业务状态不可用')).toBeVisible()
  view.rerender(<StrategyLoopStatus runtime={{ ...runtime, automation_gate: 'stopped', loop_state: 'blocked', business_health: 'blocked' }} coverage="partial" />)
  expect(screen.getByText('账户自动循环状态不可确认')).toBeVisible()
  expect(screen.queryByText('账户自动循环已停止')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('循环与业务状态')).not.toBeInTheDocument()
})
