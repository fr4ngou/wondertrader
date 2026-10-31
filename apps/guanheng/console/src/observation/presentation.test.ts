import {expect,it} from 'vitest'
import {automaticUpdateLabel,localSchedulerLabel,failureLabel,sourceLabel} from './presentation'

it('已停止服务保留明确状态',()=>{
  expect(automaticUpdateLabel({enabled:false,state:'stopped',last_heartbeat:'2026-10-18T12:30:00+00:00'},'partial')).toBe('自动更新已停止')
})

it('已登记及未知来源名称使用中文',()=>{
  expect(sourceLabel('eastmoney.executive')).toBe('高管增减持')
  expect(sourceLabel('unregistered.internal.source')).toBe('其他数据来源')
})

it('调度开关、心跳、自然窗口失败和部分成功分别呈现',()=>{
  expect(automaticUpdateLabel(undefined)).toBe('自动更新状态暂不可用')
  expect(automaticUpdateLabel({enabled:false})).toBe('自动更新尚未启用')
  expect(automaticUpdateLabel({enabled:false,state:'not_running_or_stale',last_heartbeat:'2026-10-18T12:30:00+00:00'})).toMatch(/心跳已过期/)
  expect(automaticUpdateLabel({enabled:false,state:'not_running_or_stale',last_heartbeat:null})).toMatch(/尚未收到心跳/)
  expect(automaticUpdateLabel({enabled:true,state:'stale'},'partial')).toMatch(/心跳异常/)
  expect(automaticUpdateLabel({enabled:true,state:'running'},'failed')).toMatch(/更新失败/)
  expect(automaticUpdateLabel({enabled:true,state:'running'},'partial')).toMatch(/部分来源待补/)
  expect(automaticUpdateLabel({enabled:true,state:'running'},'success')).toBe('自动更新已启用')
})

it('数据根的调度记录与本实例托管失败分别展示',()=>{
  expect(localSchedulerLabel({state:'independent',label:'由独立观察服务更新'})).toBe('由独立观察服务更新')
  expect(automaticUpdateLabel({enabled:true,state:'running'},'success')).toBe('自动更新已启用')
  expect(localSchedulerLabel({state:'faulted',label:'失败',error:'本轮启动尚未取得成功确认'})).toContain('本实例调度：本轮启动')
  expect(localSchedulerLabel({state:'disabled',label:'未配置'})).toBe('本实例未托管调度')
  expect(localSchedulerLabel({state:'ready',label:'调度就绪'})).toBe('本实例调度：调度就绪')
})

it('指数日线缺失直接说明来源缺口和保留原值',()=>{
  expect(failureLabel('market_source_unavailable')).toContain('暂未提供这组指数日线')
  expect(failureLabel('market_volume_unit_unknown')).toContain('尚未确认成交量单位')
  expect(failureLabel('other')).not.toContain('错误码')
})
