import { fetchReadJson, ReadHttpError } from '../api'

export class AccountReadBusyError extends Error {
  constructor() {
    super('账户读取繁忙，请等待本轮结束后刷新')
    this.name = 'AccountReadBusyError'
  }
}

export const accountKinds = ['position', 'order', 'deal', 'account'] as const
export type AccountKind = typeof accountKinds[number]
export type AccountField = { availability: 'present' | 'unknown' | 'invalid'; value: string | number | null; reason: string | null }
export type AccountRow = { identity: Record<string, string>; fields: Record<string, AccountField> }
export type AccountSourceV1 = {
  kind: 'qmt_http'; account_label: string; agent_id: string; environment: string; session_id: string; generation: number
}
export type AccountTransport = {
  host_instance_id: string; transport_generation: string
  route: { route_id: string; executor_id: string; route_epoch: number }; capability_sha256: string
}
export type ShmAccountSource = {
  kind: 'qmt_shm_bound'; account_label: string; environment: 'simulation' | 'live'; transport: AccountTransport
  broker_session: { availability: 'unknown'; value: null; reason: '未取得券商登录会话证据' }
}
type Group<Source> = {
  datatype: AccountKind; status: 'complete' | 'unavailable'; rows: AccountRow[]; source: Source | null
  execution_started_at: string | null; execution_finished_at: string | null
  request_id: string | null; result_sha256: string | null; reason: string | null
}
export type AccountGroupV1 = Group<AccountSourceV1>
export type AccountGroupV2 = Group<ShmAccountSource>
export type NativeAccountSource = { kind: 'wt_native_observation'; scope_id: string }
export type AccountGroupV3 = Group<NativeAccountSource> & { received_at: string | null; published_at: string | null; revision: number | null }
export type AccountGroup = AccountGroupV1 | AccountGroupV2 | AccountGroupV3

type Overview = {
  scan_id: string | null; status: 'complete' | 'partial' | 'unavailable'
  read_only: true; aggregate_only: true; trade_date: AccountField; reason: string
  close: { status: 'complete' | 'forced' | 'failed' | 'not_started'; closed: boolean; joined: boolean
    worker_live: boolean; queued: number; exit_code: number | null; error_code: string }
}
export type AccountOverviewV1 = Overview & { schema_version: '1.0'; groups: Record<AccountKind, AccountGroupV1> }
export type AccountOverviewV2 = Overview & { schema_version: '2.0'; groups: Record<AccountKind, AccountGroupV2> }
export type AccountOverviewV3 = Overview & { schema_version: '3.0'; groups: Record<AccountKind, AccountGroupV3>; runtime_state: string; observed_at: string }
export type AccountPublication = { scope_id: string | null; state: 'waiting' | 'refreshing' | 'ready' | 'degraded' | 'stopped' | 'unconfigured'; revision: number; updated_at: string | null; last_success_at: string | null; runtime_state: string }
export type AccountOverviewV4 = Overview & { schema_version: '4.0'; groups: Record<AccountKind, AccountGroupV2>; publication: AccountPublication }
export type AccountOverview = AccountOverviewV1 | AccountOverviewV2 | AccountOverviewV3 | AccountOverviewV4

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function keys(value: unknown, expected: readonly string[]): value is Record<string, unknown> {
  return record(value) && Object.keys(value).length === expected.length
    && expected.every(key => Object.hasOwn(value, key))
}

function oneOf(value: unknown, values: readonly string[]): boolean {
  return typeof value === 'string' && values.includes(value)
}

function nullableText(value: unknown): boolean { return value === null || typeof value === 'string' }

function validField(value: unknown): boolean {
  if (!keys(value, ['availability', 'value', 'reason']) || !oneOf(value.availability, ['present', 'unknown', 'invalid'])
    || !nullableText(value.reason)) return false
  return value.availability !== 'present' ? value.value === null
    : typeof value.value === 'string' || typeof value.value === 'number' && Number.isFinite(value.value)
}

function unicodeText(value: unknown, maximum: number): value is string {
  if (typeof value !== 'string' || value.length === 0 || value.length > maximum * 2) return false
  let count = 0
  for (const character of value) {
    const point = character.codePointAt(0)!
    if (++count > maximum || point >= 0xd800 && point <= 0xdfff) return false
  }
  return true
}

function maskedAccount(value: unknown): boolean {
  // 唯一后端投影只给****或****+末四码点；未知原账号不得作为label展示。
  return unicodeText(value, 8) && !/[\u0000-\u001f\u007f-\u009f]/.test(value)
    && value.startsWith('****') && [4, 8].includes([...value].length)
}

function hex(value: unknown, size: number): boolean {
  return typeof value === 'string' && value.length === size && /^[0-9a-f]+$/.test(value)
}

function sourceV1(value: unknown): boolean {
  return keys(value, ['kind', 'account_label', 'agent_id', 'environment', 'session_id', 'generation'])
    && value.kind === 'qmt_http' && maskedAccount(value.account_label)
    && ['agent_id', 'environment', 'session_id'].every(key => typeof value[key] === 'string')
    && Number.isSafeInteger(value.generation) && (value.generation as number) >= 1
}

function sourceV2(value: unknown): boolean {
  if (!keys(value, ['kind', 'account_label', 'environment', 'transport', 'broker_session'])
    || value.kind !== 'qmt_shm_bound' || !maskedAccount(value.account_label)
    || !oneOf(value.environment, ['simulation', 'live'])) return false
  const transport = value.transport, broker = value.broker_session
  if (!keys(transport, ['host_instance_id', 'transport_generation', 'route', 'capability_sha256'])
    || !hex(transport.host_instance_id, 32) || !hex(transport.transport_generation, 32) || !hex(transport.capability_sha256, 64)
    || !keys(transport.route, ['route_id', 'executor_id', 'route_epoch'])) return false
  const route = transport.route
  // 路由沿生产者的Unicode标量/码点域；账号label的控制字符约束单独保留。
  return unicodeText(route.route_id, 128) && unicodeText(route.executor_id, 128)
    && Number.isSafeInteger(route.route_epoch) && (route.route_epoch as number) >= 0
    && keys(broker, ['availability', 'value', 'reason']) && broker.availability === 'unknown'
    && broker.value === null && broker.reason === '未取得券商登录会话证据'
}

/** 唯一纯边界按版本核原生类型和闭合键；运输身份不推成券商登录或账户选择能力。 */
export function validateAccountOverview(value: unknown): AccountOverview {
  const invalid = (): never => { throw new Error('账户数据格式无效，请重新读取') }
  const native = record(value) && value.schema_version === '3.0'
  const published = record(value) && value.schema_version === '4.0'
  const stamp = (v: unknown): v is string => typeof v === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v))
  if (!keys(value, ['schema_version', 'scan_id', 'status', 'read_only', 'aggregate_only', 'trade_date', 'reason', 'close', 'groups', ...(native ? ['runtime_state', 'observed_at'] : []), ...(published ? ['publication'] : [])])
    || !oneOf(value.schema_version, ['1.0', '2.0', '3.0','4.0']) || value.read_only !== true || value.aggregate_only !== true
    || !oneOf(value.status, ['complete', 'partial', 'unavailable']) || typeof value.reason !== 'string'
    || !nullableText(value.scan_id) || !validField(value.trade_date) || !keys(value.groups, accountKinds)
    || !keys(value.close, ['status', 'closed', 'joined', 'worker_live', 'queued', 'exit_code', 'error_code'])) return invalid()
  const close = value.close
  if (native && (!stamp(value.observed_at) || !oneOf(value.runtime_state, ['new','starting','ready','stopping','closed','faulted','unconfigured']))) return invalid()
  if (published) {
    const publication=value.publication
    if (!keys(publication,['scope_id','state','revision','updated_at','last_success_at','runtime_state'])
      || !(publication.scope_id===null || hex(publication.scope_id,64))
      || !oneOf(publication.state,['waiting','refreshing','ready','degraded','stopped','unconfigured'])
      || !Number.isSafeInteger(publication.revision) || Number(publication.revision)<0
      || !oneOf(publication.runtime_state,['new','starting','ready','stopping','closed','faulted','unconfigured'])
      || !(publication.updated_at===null || stamp(publication.updated_at))
      || !(publication.last_success_at===null || stamp(publication.last_success_at))
      || publication.last_success_at!==null && (publication.updated_at===null || Date.parse(String(publication.last_success_at))>Date.parse(String(publication.updated_at)))
      || publication.state==='ready' && publication.last_success_at===null
      || (publication.state==='unconfigured'
        ? publication.scope_id!==null || publication.revision!==0 || publication.updated_at!==null || publication.last_success_at!==null
        : publication.scope_id===null || Number(publication.revision)<1 || publication.updated_at===null)
      || publication.last_success_at!==null && (value.scan_id===null || value.status==='unavailable')
      || publication.last_success_at===null && (value.scan_id!==null || value.status!=='unavailable')) return invalid()
  }
  if (!oneOf(close.status, ['complete', 'forced', 'failed', 'not_started'])
    || ['closed', 'joined', 'worker_live'].some(key => typeof close[key] !== 'boolean')
    || !Number.isInteger(close.queued) || (close.queued as number) < 0
    || !(close.exit_code === null || Number.isInteger(close.exit_code)) || typeof close.error_code !== 'string') return invalid()
  let completeGroups = 0
  for (const kind of accountKinds) {
    const group = value.groups[kind]
    if (!keys(group, ['datatype', 'status', 'rows', 'source', 'execution_started_at', 'execution_finished_at', 'request_id', 'result_sha256', 'reason', ...(native ? ['received_at','published_at','revision'] : [])])
      || group.datatype !== kind || !oneOf(group.status, ['complete', 'unavailable'])
      || !Array.isArray(group.rows) || group.rows.length > 4096
      || group.status === 'unavailable' && group.rows.length !== 0
      || ['execution_started_at', 'execution_finished_at', 'request_id', 'result_sha256', 'reason']
        .some(key => !nullableText(group[key]))) return invalid()
    if (group.status === 'complete') completeGroups += 1
    const source = group.source
    if (native) {
      if (source !== null && !(keys(source,['kind','scope_id']) && source.kind==='wt_native_observation' && hex(source.scope_id,64))) return invalid()
      if (['execution_started_at','execution_finished_at','request_id','result_sha256'].some(k=>group[k]!==null)) return invalid()
      if (group.status==='complete') {
        if (kind==='order' || kind==='deal' || source===null || !stamp(group.received_at) || !stamp(group.published_at)
          || Date.parse(group.received_at)>Date.parse(group.published_at) || Date.parse(group.published_at)>Date.parse(String(value.observed_at))
          || !Number.isSafeInteger(group.revision) || Number(group.revision)<=0) return invalid()
      } else if (group.received_at!==null || group.published_at!==null || group.revision!==null) return invalid()
    } else {
      if (source !== null && !(value.schema_version === '1.0' ? sourceV1(source) : sourceV2(source))) return invalid()
      if (group.status === 'complete' && (source === null || group.request_id === null
        || group.execution_started_at === null || group.execution_finished_at === null || group.result_sha256 === null)) return invalid()
    }
    for (const row of group.rows) {
      if (!keys(row, ['identity', 'fields']) || !record(row.identity) || !record(row.fields)
        || Object.values(row.identity).some(item => typeof item !== 'string')
        || Object.keys(row.fields).length > 64 || !Object.values(row.fields).every(validField)) return invalid()
    }
  }
  // 全轮完成来自四批和关闭证明；空完整批仍计完成，失败批保持不可用。
  if (value.status === 'complete' && (completeGroups !== 4 || close.status !== 'complete'
    || !close.closed || !close.joined || close.worker_live || close.queued !== 0 || close.exit_code !== 0 || close.error_code !== 'ok')
    || value.status === 'partial' && completeGroups === 0
    || value.status === 'unavailable' && completeGroups !== 0) return invalid()
  return value as AccountOverview
}

/** 同一既有读取调度和截止；错误正文不进入账户页面，也不自动重发。 */
export async function fetchAccountOverview(signal?: AbortSignal, timeoutSeconds = 30): Promise<AccountOverview> {
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 1 || timeoutSeconds > 30) {
    throw new Error('账户读取预算无效，请检查应用连接配置')
  }
  let value: unknown
  try {
    value = await fetchReadJson<unknown>('/v1/ui/account/overview', '账户', signal, 'workspace', (timeoutSeconds + 1.5) * 1000)
  } catch (error) {
    if (error instanceof ReadHttpError && error.status === 429) throw new AccountReadBusyError()
    throw error
  }
  return validateAccountOverview(value)
}
