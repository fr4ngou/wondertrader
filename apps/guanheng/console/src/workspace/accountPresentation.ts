import { accountKinds, type AccountGroup, type AccountKind, type AccountOverview } from './accountApi'

/** 当前轮原值与各类上次成功展示分开；来源改变后整体清除旧批回退。 */
export type AccountReadView = {
  current: AccountOverview
  scope: string | null
  complete: Partial<Record<AccountKind, AccountGroup>>
}

export function accountReadView(current: AccountOverview, previous?: AccountReadView): AccountReadView {
  if (previous?.current.schema_version!==current.schema_version
    || current.schema_version==='4.0' && previous?.current.schema_version==='4.0'
      && current.publication.scope_id!==previous.current.publication.scope_id) previous=undefined
  const sources = [...new Set(accountKinds.flatMap(kind => {
    const source = current.groups[kind].source
    if (!source) return []
    if (source.kind === 'wt_native_observation') return [JSON.stringify([source.kind, source.scope_id])]
    const identity = source.kind === 'qmt_shm_bound'
      ? [source.transport.host_instance_id, source.transport.transport_generation, source.transport.route.route_id,
        source.transport.route.executor_id, source.transport.route.route_epoch, source.transport.capability_sha256]
      : [source.agent_id, source.session_id, source.generation]
    return [JSON.stringify([source.kind, source.account_label, source.environment, ...identity])]
  }))].sort()
  const scope = sources.length ? JSON.stringify(sources) : previous?.scope ?? null
  const complete = previous?.scope === scope ? { ...previous.complete } : {}
  for (const kind of accountKinds) {
    if (current.groups[kind].status === 'complete') complete[kind] = current.groups[kind]
  }
  return { current, scope, complete }
}
