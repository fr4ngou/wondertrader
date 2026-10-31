import {cleanup,render,screen} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {FieldCoverage} from './FieldCoverage'

afterEach(cleanup)

it('explains a partial market denominator without presenting the lower bound as a full ratio',()=>{
  render(<FieldCoverage metric="turnover.gt5.ashare" row={{turnover_gt5_pct:null,turnover_confirmed_lower_bound_pct:17.3,missing_float_count:2}} />)
  expect(screen.getByText(/可用非限售股本尚缺 2 只/)).toBeTruthy()
  expect(screen.getByText(/完整市场占比暂缺。已确认至少 17.3%/)).toBeTruthy()
})

it('keeps a price gap local to price-dependent metrics',()=>{
  const {rerender}=render(<FieldCoverage metric="turnover.gt5.ashare" row={{missing_price_count:1}} />)
  expect(screen.queryByRole('status')).toBeNull()
  rerender(<FieldCoverage metric="breadth.ashare" row={{missing_price_count:1,unclassified_count:1}} />)
  expect(screen.getByText(/涨跌比较价尚缺 1 只/)).toBeTruthy()
  expect(screen.getByText(/尚缺股票保留在股票池中/)).toBeTruthy()
})

it('explains source reference prices and actual turnover before a halt',()=>{
  render(<FieldCoverage metric="trin.ashare" row={{special_reference_count:1,halted_with_trades_count:2}} />)
  expect(screen.getByText(/1 只首日或新增交易证券采用来源参考价/)).toBeTruthy()
  expect(screen.getByText(/2 只证券有停牌标志且当日已有成交/)).toBeTruthy()
})
