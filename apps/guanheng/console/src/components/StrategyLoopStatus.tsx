import type { AutomationRuntimeStatus } from '../types'
import { absoluteChinaTime } from './RelativeTime'

const loops: Record<AutomationRuntimeStatus['loop_state'], string> = {
  idle: '空闲', waiting: '正常等待', advancing: '循环正在运行', converging: '循环正在收敛',
  blocked: '循环已阻断', unavailable: '循环状态不可用',
}
const health: Record<AutomationRuntimeStatus['business_health'], string> = {
  healthy: '业务正常', degraded: '业务降级', blocked: '交易受阻', unavailable: '业务状态不可用',
}
const gates: Record<AutomationRuntimeStatus['automation_gate'], string> = {
  enabled: '账户自动循环已开启', disabled: '账户自动循环已关闭',
  stopped: '账户自动循环已停止', unavailable: '账户自动循环开关不可用',
}

export function StrategyLoopStatus({ runtime, coverage }: {
  runtime?: AutomationRuntimeStatus | null
  coverage: 'complete' | 'partial' | 'unavailable'
}) {
  const available = coverage === 'complete' && runtime != null
  const label = available ? gates[runtime.automation_gate] : '账户自动循环状态不可确认'
  return <section className="strategy-readonly-note" aria-label="账户自动循环">
    <strong>{label}</strong>
    {available ? <p aria-label="循环与业务状态">{loops[runtime.loop_state]} · {health[runtime.business_health]}</p> : null}
    <p>这是账户层的循环观察。具体买卖仍按所选策略的价格和安全条件核对；记录提示先等待卖出完成时，买入等待卖出后再检查。循环运行记录与实际委托记录分别展示。</p>
    {available ? <p>最近观察：{absoluteChinaTime(runtime.last_observed_at)} · 最近成功循环：{runtime.last_successful_loop_at ? absoluteChinaTime(runtime.last_successful_loop_at) : '暂无成功记录'}</p> : <p>运行来源覆盖不足，等待原权威投影提供完整状态。</p>}
    {available && runtime.issues.length ? <p>{runtime.issues.filter(issue => issue.lifecycle !== 'resolved').map(issue => issue.user_safe_summary).join('；')}</p> : null}
  </section>
}
