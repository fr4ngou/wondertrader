import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import StrategyRuntimeSummary from './StrategyRuntimeSummary'
import fixture from './strategy-runtime.fixture.json'
import { validateStrategyRuntime, type StrategyRuntime } from './strategyRuntimeApi'

const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.unstubAllGlobals() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><StrategyRuntimeSummary /></QueryClientProvider>)
}
const response = (v: unknown) => new Response(JSON.stringify(v))

test('页面仅显示券商实际持仓，目标与理论明细退出展示', async () => {
  const data = structuredClone(fixture)
  data.strategy.positions[1].broker_quantity = 700
  data.strategy.positions[1].broker_sellable = 300
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(data))); mount()
  const row = await screen.findByRole('row', { name: '510050.SH策略结果' })
  expect(row).toHaveTextContent('700')
  expect(row).toHaveTextContent('300')
  expect(screen.queryByRole('columnheader', { name: '目标仓位' })).not.toBeInTheDocument()
  expect(screen.queryByRole('columnheader', { name: /理论持仓|阶段目标/ })).not.toBeInTheDocument()
  expect(row).not.toHaveTextContent('200')
})

test('行情等待保持券商持仓、清空未生成目标，并可刷新恢复', async () => {
  const waiting = { ...structuredClone(fixture), strategy: { ...structuredClone(fixture.strategy),
    status: 'waiting_market_input', status_label: '等待策略所需行情', decision_at: null,
    positions: fixture.strategy.positions.map(p => ({ ...p, target_weight: null,
      theoretical_quantity: null, theoretical_sellable: null, pending_target: null, stage_target: null })) } }
  const fetch = vi.fn().mockResolvedValueOnce(response(waiting)).mockResolvedValueOnce(response(fixture))
  vi.stubGlobal('fetch', fetch); mount()
  await screen.findByText('等待策略所需行情')
  expect(screen.getByText(/核对策略所需行情/)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.getByRole('row', { name: '510050.SH策略结果' })).toHaveTextContent('200')
  expect(screen.getByText(/决策时间（北京时间）：尚未取得/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '刷新策略结果' }))
  await screen.findByText('正在调整卖出目标')
  expect(screen.queryByText(/核对策略所需行情/)).not.toBeInTheDocument()
})

test('真实桥投影保留券商实际持仓与可卖，省去内部目标明细', async () => {
  const data = structuredClone(fixture)
  data.strategy.positions[1].broker_quantity = 700
  data.strategy.positions[1].broker_sellable = 300
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(data))); mount()
  const sh50 = within(await screen.findByRole('row', { name: '510050.SH策略结果' }))
  expect(sh50.getByText('700')).toBeInTheDocument(); expect(sh50.getByText('300')).toBeInTheDocument()
  expect(sh50.queryByText('200')).not.toBeInTheDocument()
  expect(screen.getByText('正在调整卖出目标')).toBeInTheDocument()
  expect(screen.getByText(/决策时间（北京时间）：2026-10-29 19:38:12/)).toBeInTheDocument()
  expect(document.body).not.toHaveTextContent(/configuration_sha256|model_states|native_observation_id|来源会话/)
  expect(document.querySelector('details, pre')).toBeNull()
})

test('刷新中及失败保留原结果和时间，成功空更新再恢复', async () => {
  let release!: (value: Response) => void
  const fetch = vi.fn().mockResolvedValueOnce(response(fixture))
    .mockImplementationOnce(() => new Promise(resolve => { release = resolve }))
    .mockResolvedValueOnce(response({ ...fixture, state: 'unconfigured', strategy: null }))
    .mockResolvedValueOnce(response(fixture))
  vi.stubGlobal('fetch', fetch); mount(); await screen.findByText('正在调整卖出目标')
  fireEvent.click(screen.getByRole('button', { name: '刷新策略结果' }))
  await screen.findByText('正在刷新，当前显示上次成功结果。')
  expect(screen.getByText('正在调整卖出目标')).toBeInTheDocument()
  release(new Response('{}', { status: 503 }))
  await screen.findByRole('alert')
  expect(screen.getByText('正在调整卖出目标')).toBeInTheDocument()
  expect(screen.getByText(/结果读取时间（北京时间）：2026-10-29 19:38:13/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '刷新策略结果' }))
  await screen.findByText('当前尚未接入策略运行结果。')
  expect(screen.queryByText('正在调整卖出目标')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '刷新策略结果' }))
  await screen.findByText('正在调整卖出目标')
})

test('初次失败给出重试，不编造空仓或目标', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 }))); mount()
  await screen.findByRole('alert')
  expect(screen.queryByText(/均无持仓/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '刷新策略结果' })).toBeEnabled()
})

test.each([
  { state: ['waiting'], strategy: null },
  { runtime_state: ['closed'] },
])('数组状态显示格式错误并可重新读取恢复：%j', async invalid => {
  const fetch = vi.fn().mockResolvedValueOnce(response({ ...structuredClone(fixture), ...invalid }))
    .mockResolvedValueOnce(response(fixture))
  vi.stubGlobal('fetch', fetch); mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('策略运行结果格式无效')
  expect(screen.queryByText('正在调整卖出目标')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '刷新策略结果' }))
  await screen.findByText('正在调整卖出目标')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test.each([true, false, undefined])('完成状态按已发布执行资格显示，旧响应保持计算语义：%s', async qualified => {
  const data = structuredClone(fixture) as StrategyRuntime
  data.strategy!.status = 'converged'
  data.strategy!.status_label = '理论持仓已达到本阶段目标'
  if (qualified !== undefined) data.strategy!.execution_position_qualified = qualified
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(data))); mount()
  await screen.findByText(qualified === true ? '本轮调仓已完成' : '本阶段策略计算已完成')
  expect(screen.queryByText('理论持仓已达到本阶段目标')).not.toBeInTheDocument()
  expect(screen.queryByRole('columnheader', { name: '目标仓位' })).not.toBeInTheDocument()
})

test('执行来源已确认且仍在买入时，页面继续显示进行中', async () => {
  const data = structuredClone(fixture) as StrategyRuntime
  data.strategy!.status = 'buying'; data.strategy!.status_label = '正在调整买入目标'
  data.strategy!.execution_position_qualified = true
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(data))); mount()
  await screen.findByText('正在调整买入目标')
  expect(screen.queryByText('本轮调仓已完成')).not.toBeInTheDocument()
})

test.each([null, 0, 1, 'true'])('非法执行资格拒绝进入页面：%s', qualified => {
  const data = { ...structuredClone(fixture), strategy: { ...structuredClone(fixture.strategy), execution_position_qualified: qualified } }
  expect(() => validateStrategyRuntime(data)).toThrow('策略运行结果格式无效')
})

test.each([
  (v: typeof fixture) => { v.strategy.positions[0].broker_sellable = 100 },
  (v: typeof fixture) => { v.strategy.positions[0].target_weight = 2 },
  (v: typeof fixture) => { v.strategy.positions[0].symbol = '510050.SH' },
  (v: typeof fixture) => { v.strategy.status_label = 'private diagnostics' },
])('坏业务字段拒绝进入页面', change => {
  const v = structuredClone(fixture); change(v)
  expect(() => validateStrategyRuntime(v)).toThrow('策略运行结果格式无效')
})
