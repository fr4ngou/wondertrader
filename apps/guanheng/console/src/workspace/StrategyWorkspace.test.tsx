import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import StrategyWorkspace from './StrategyWorkspace'
vi.mock('./StrategyCatalogWorkspace', () => ({ default: () => <h1>策略目录夹具</h1> }))
afterEach(cleanup)
function Destination(){const location=useLocation();return <output aria-label="回测目的地">{location.pathname+location.search}</output>}
it('默认显示策略目录', () => {
 render(<MemoryRouter initialEntries={['/strategies']}><StrategyWorkspace /></MemoryRouter>)
 expect(screen.getByRole('heading',{name:'策略目录夹具'})).toBeVisible()
})
it('旧配置深链接进入只读策略目录', () => {
 render(<MemoryRouter initialEntries={['/strategies?tab=configuration']}><StrategyWorkspace /></MemoryRouter>)
 expect(screen.getByRole('heading',{name:'策略目录夹具'})).toBeVisible()
})
it('旧backtests标签转向独立回测并保留策略与报告身份', async () => {
 render(<MemoryRouter initialEntries={['/strategies?tab=backtests&strategy=demo%401&run=abc']}><Routes><Route path="/strategies" element={<StrategyWorkspace/>}/><Route path="/backtests" element={<Destination/>}/></Routes></MemoryRouter>)
 expect(await screen.findByLabelText('回测目的地')).toHaveTextContent('/backtests?strategy=demo%401&run=abc')
})
