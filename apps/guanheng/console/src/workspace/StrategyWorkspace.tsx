import { Navigate, useSearchParams } from 'react-router-dom'
import StrategyCatalogWorkspace from './StrategyCatalogWorkspace'

/** 旧回测标签转向独立入口，保留策略和报告选择。 */
export default function StrategyWorkspace() {
  const [params] = useSearchParams()
  if (params.get('tab') === 'backtests') {
    const next = new URLSearchParams(params); next.delete('tab')
    return <Navigate replace to={'/backtests' + (next.size ? `?${next}` : '')} />
  }
  return <StrategyCatalogWorkspace />
}
