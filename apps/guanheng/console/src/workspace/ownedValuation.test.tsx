import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import LiveStrategyPerformance from './LiveStrategyPerformance'
import {validateLivePerformance,type LivePerformance} from './liveStrategyApi'

const chart=vi.hoisted(()=>({options:[] as {series:{name:string;data:unknown[];lineStyle?:{type?:string}}[];tooltip:{formatter:(input:unknown)=>string}}[]}))
vi.mock('echarts/core',()=>({use:vi.fn(),init:()=>({setOption:(o:typeof chart.options[number])=>chart.options.push(o),
  getZr:()=>({on:vi.fn()}),resize:vi.fn(),dispose:vi.fn()})}))
afterEach(()=>{cleanup();chart.options=[]})

function fixture(reference:boolean):LivePerformance {
  const state=reference?'reference-fee-pending':'actual'
  const clock='2026-11-06T07:00:00Z'
  const value={schema_version:'guanheng.live-strategy-performance.v1',read_only:true,observed_at:clock,state:'available',reason:'原ASA估值',
    requested:{strategy_id:'sample',strategy_version:'1'},current:{strategy_id:'sample',strategy_version:'1',key_matches:true,is_current:true,runtime_state:'ready',scope_id:'a'.repeat(64),process_state:'alive'},
    coverage:{from:reference?null:'2026-11-06',to:reference?null:'2026-11-06',point_count:reference?0:1,reference_point_count:reference?1:0,
      basis:'actual-published-observations',history_state:'snapshot-only',reason:'原估值时点，无历史补值',deals_truncated:false,attribution:'strategy-allocated',valuation_state:state},
    baseline:null,summary:{nav_cny:reference?null:'1000196.67',pnl_cny:null,reference_nav_cny:reference?'1000200.00':null,valuation_state:state,
      reference_change_cny:reference?'200.00':'196.67',reference_return_pct:reference?'0.020000':'0.019667',baseline_cny:'1000000.00',
      return_pct:null,observed_at:clock,price_observed_at:clock,pnl_source:'ASA-owned-valuation',return_reason:'配置资本参考率不是投资收益率'},
    daily:[{date:'2026-11-06',observed_at:reference?null:clock,reference_observed_at:reference?clock:null,
      nav_cny:reference?null:'1000196.67',reference_nav_cny:reference?'1000200.00':null,reference_cash_cny:reference?'999600.00':null,
      cash_cny:reference?null:'999596.67',market_value_cny:'600.00',pnl_cny:null,return_pct:null,valuation_state:state,
      reference_change_cny:reference?'200.00':'196.67',reference_return_pct:reference?'0.020000':'0.019667',
      positions:[],deals:[],positions_state:'empty',deals_state:'empty'}],markers:[]}
  return validateLivePerformance(value,'sample','1')
}

test('手续费待确认参考线独立绘制，不生成实际净值或投资收益',()=>{
  render(<LiveStrategyPerformance data={fixture(true)} />)
  expect(screen.getAllByText(/参考净值（手续费待确认）/).length).toBeGreaterThan(0)
  expect(screen.getByText('配置资本参考变化率')).toBeVisible()
  expect(screen.getByText('0.020000%')).toBeVisible()
  expect(screen.getByText(/实际手续费尚待确认/)).toBeVisible()
  const lines=chart.options.at(-1)!.series
  expect(lines[0].data).toEqual([null])
  expect(lines[1].data).toEqual([1000200])
  expect(lines[1].lineStyle?.type).toBe('dashed')
  expect(chart.options.at(-1)!.tooltip.formatter([{dataIndex:0}])).toContain('参考净值（手续费待确认）')
})

test('实际费用补齐更新同一天资格及曲线，不沿用参考金额',()=>{
  const view=render(<LiveStrategyPerformance data={fixture(true)} />)
  view.rerender(<LiveStrategyPerformance data={fixture(false)} />)
  expect(screen.getByText('0.019667%')).toBeVisible()
  const lines=chart.options.at(-1)!.series
  expect(lines[0].data).toEqual([1000196.67]);expect(lines[1].data).toEqual([null])
  expect(screen.queryByText(/实际手续费尚待确认/)).toBeNull()
})

test('参考字段不允许伪装实际金额或伪造变化率',()=>{
  const value=fixture(true)
  expect(()=>validateLivePerformance({...value,summary:{...value.summary,nav_cny:'1000200.00'}},'sample','1')).toThrow()
  expect(()=>validateLivePerformance({...value,summary:{...value.summary,reference_return_pct:{fake:1}}},'sample','1')).toThrow()
})
