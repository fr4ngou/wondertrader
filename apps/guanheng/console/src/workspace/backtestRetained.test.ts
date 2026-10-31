import {afterEach, expect, it, vi} from 'vitest'
import {fetchReadJson} from '../api'
import {fetchBacktestDay} from './backtestApi'
import {validatePerformance} from './backtestPerformanceApi'
import {RETAINED_REPORT_SCHEMA} from './backtestRetained'
import fixture from './backtest-retained-day.fixture.json'
import performance from './backtest-retained-performance.fixture.json'
vi.mock('../api', () => ({fetchReadJson:vi.fn()}))
afterEach(()=>vi.resetAllMocks())
const read=()=>fetchBacktestDay('a'.repeat(32),fixture.request_id,fixture.index,undefined,fixture.report_sha256,fixture.record.trading_date)

it('独立App的实际合成原生报告按唯一策略schema读取，绩效仍绑定同一归档', async()=>{
  vi.mocked(fetchReadJson).mockResolvedValue(fixture)
  expect((await read()).report_schema).toBe(RETAINED_REPORT_SCHEMA)
  expect(validatePerformance(performance.performance,performance.entry).strategy.version).toBe('1.1.2')
  expect(()=>validatePerformance({...performance.performance,scope:'RT-qualified'},performance.entry)).toThrow()
})

it.each(['version','qualification','schema','model','clock','weights','source','cash','position','vector'])('拒绝%s错配，保持输入和业务事实边界', async kind=>{
  const value=structuredClone(fixture) as unknown as Record<string,any>;const s=value.evaluation_summary
  if(kind==='version')s.strategy_version='1.1.1'
  if(kind==='qualification')s.execution_qualified=true
  if(kind==='schema')delete value.report_schema
  if(kind==='model')s.historical_model.availability_basis='actually-known'
  if(kind==='clock')s.decision_cutoff='2024-06-24T06:00:00Z'
  if(kind==='weights')s.targets['510300.SH']=.5
  if(kind==='source')s.current_view.dataset_sha256='0'.repeat(64)
  if(kind==='cash')value.record.capture.basis.cash_cny='NaN'
  if(kind==='position')value.record.capture.observation.positions[0].actual=-1
  if(kind==='vector')value.record.submit_vector=[{symbol:'510300.SH',quantity:100}]
  vi.mocked(fetchReadJson).mockResolvedValue(value)
  await expect(read()).rejects.toThrow('格式或身份无效')
})
