import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import StrategyWorkspace from './StrategyWorkspace'
vi.mock('./StrategyCatalogWorkspace', () => ({ default: () => <h1>策略目录夹具</h1> }))
vi.mock('./BacktestWorkspace', () => ({ default: () => <h1>既有原生回测夹具</h1> }))
afterEach(cleanup)
it('默认显示策略详情，可切换到既有回测工作区', async () => {
  render(<MemoryRouter initialEntries={['/strategies']}><StrategyWorkspace /></MemoryRouter>)
  expect(screen.getByRole('heading', { name: '策略目录夹具' })).toBeVisible()
  fireEvent.click(screen.getByRole('link', { name: '回测与报告' }))
  expect(await screen.findByRole('heading', { name: '既有原生回测夹具' })).toBeVisible()
})
it('旧配置深链接进入只读策略目录', () => {
  render(<MemoryRouter initialEntries={['/strategies?tab=configuration']}><StrategyWorkspace /></MemoryRouter>)
  expect(screen.getByRole('heading', { name: '策略目录夹具' })).toBeVisible()
  expect(screen.getByRole('link', { name: '策略详情' })).toHaveAttribute('aria-current', 'page')
})
it('旧backtests tab保持原回测入口', async () => {
  render(<MemoryRouter initialEntries={['/strategies?tab=backtests']}><StrategyWorkspace /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: '既有原生回测夹具' })).toBeVisible()
})
