import { expect, test } from 'vitest'
import { validateTargetHistory } from './strategyTargetHistoryApi'

const selection = {strategy_id:'synthetic', strategy_version:'1.2.2'}
function sample() {
  return {schema_version:'guanheng.strategy-target-history.v1',read_only:true,observed_at:'2026-11-05T07:00:00Z',state:'available',reason:'synthetic',requested:selection,
    source:{kind:'wt-native-signals',source_id:'a'.repeat(64),snapshot_sha256:'b'.repeat(64),raw_count:4,changed_count:2,initial_count:1,unchanged_count:1,incomplete_tail:false,first_at:'2026-11-05T09:30:00+08:00',last_at:'2026-11-05T10:00:00+08:00'},next_cursor:null,
    items:[{id:'c'.repeat(64),sequence:4,changed_at:'2026-11-05T10:00:00+08:00',symbol:'510300.SH',previous_target_quantity:200,target_quantity:100,change_quantity:-100,kind:'changed',reference_price_cny:'4.25',target_weight:null,strategy_version:null,reason:null},
      {id:'d'.repeat(64),sequence:1,changed_at:'2026-11-05T09:30:00+08:00',symbol:'510300.SH',previous_target_quantity:null,target_quantity:0,change_quantity:null,kind:'initial',reference_price_cny:'4.25',target_weight:null,strategy_version:null,reason:null}]}
}

test('原目标为零与首次前值未知分别保留，不从当前版本倒推历史', () => {
  const value=validateTargetHistory(sample(),selection)
  expect(value.items[1]).toMatchObject({previous_target_quantity:null,target_quantity:0,change_quantity:null,strategy_version:null})
  expect(value.items[0].change_quantity).toBe(-100)
})

test('错策略、数量差、重复/乱序记录及错误来源计数均拒绝', () => {
  expect(()=>validateTargetHistory(sample(),{...selection,strategy_version:'different'})).toThrow()
  let value=sample();value.items[0].change_quantity=0;expect(()=>validateTargetHistory(value,selection)).toThrow()
  value=sample();value.items[1].id=value.items[0].id;expect(()=>validateTargetHistory(value,selection)).toThrow()
  value=sample();value.items.reverse();expect(()=>validateTargetHistory(value,selection)).toThrow()
  value=sample();value.source.raw_count=100;expect(()=>validateTargetHistory(value,selection)).toThrow()
})

test('非当前选择必须清空来源与记录，目标权重/原因未知不可造值', () => {
  const value=sample();expect(()=>validateTargetHistory({...value,state:'not_current'},selection)).toThrow()
  expect(validateTargetHistory({...value,state:'not_current',source:null,items:[],next_cursor:null},selection).items).toEqual([])
  expect(()=>validateTargetHistory({...value,items:[{...value.items[0],target_weight:0}]},selection)).toThrow()
})
