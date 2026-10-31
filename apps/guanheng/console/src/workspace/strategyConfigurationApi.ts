import { fetchReadJson } from '../api'

export const CONFIGURATION_ENDPOINT = '/v1/ui/strategy-configurations'
const prefix = 'guanheng.strategy-configuration-'
const id = /^[0-9a-f]{32}$/
const sha = /^[0-9a-f]{64}$/
const symbol = /^[0-9]{6}\.(SH|SZ)$/
const configKeys = ['config_revision', 'symbol_roles', 'execution_symbols', 'benchmark_role', 'valid_from', 'valid_until',
  'minimum_history_days', 'regime_ma_period', 'position_window', 'volume_window', 'budget_weight', 'symbol_cap_weight',
  'max_weight_change', 'strategy_id', 'strategy_version', 'observation_version', 'warmup_policy']
const integerKeys = ['minimum_history_days', 'regime_ma_period', 'position_window', 'volume_window'] as const
const weightKeys = ['budget_weight', 'symbol_cap_weight', 'max_weight_change'] as const

export type StrategyConfiguration = {
  config_revision: string; symbol_roles: [string, string][]; execution_symbols: [string, string][]; benchmark_role: string
  valid_from: string; valid_until: string; minimum_history_days: number; regime_ma_period: number; position_window: number
  volume_window: number; budget_weight: number; symbol_cap_weight: number; max_weight_change: number
  strategy_id: 'resonance-regime-v1'; strategy_version: '1.2.0'; observation_version: 'resonance-daily-closed-v3'; warmup_policy: 'regime-available-v1'
}
export type ConfigurationReceipt = { revision: number; request_id: string; request_sha256: string; configuration_sha256: string
  configuration: StrategyConfiguration; saved_at: string }
export type ConfigurationStore = { schema: string; store_id: string; revision: number; versions: ConfigurationReceipt[] }
export type ConfigurationCatalog = { strategy_id: string; strategy_version: string; label: string; example_kind: 'synthetic'; example: StrategyConfiguration }
export type ConfigurationWorkspace = { schema: string; owner_id: string; available: boolean; editable: boolean; reason: string | null
  catalog: ConfigurationCatalog[]; store: ConfigurationStore | null; max_versions: 32; runtime_effect: false }
export type ConfigurationValidation = { schema: string; configuration: StrategyConfiguration; configuration_sha256: string
  validation_time: string; validity: 'not_yet_valid' | 'within_window' | 'expired'; qualification: string }
export type SaveConfigurationIntent = { store_id: string; expected_revision: number; request_id: string
  configuration: StrategyConfiguration; configuration_sha256: string }

function invalid(): never { throw new Error('策略配置资料格式或身份无效，请重新读取核实') }
function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value) }
function exact(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key))
}
const text = (value: unknown, maximum = 256): value is string => {
  if (typeof value !== 'string' || /[\u0000-\u001f]/.test(value)) return false
  let points = 0
  for (const point of value) {
    const unit = point.charCodeAt(0)
    if (point.length === 1 && unit >= 0xd800 && unit <= 0xdfff) return false
    if (++points > maximum) return false
  }
  return points > 0
}
const identity = (value: unknown): value is string => typeof value === 'string' && id.test(value)
const digest = (value: unknown): value is string => typeof value === 'string' && sha.test(value)
const timestamp = (value: unknown): value is string => {
  if (typeof value !== 'string' || value.length > 32 || value.startsWith('0000')
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value) || !Number.isFinite(Date.parse(value))) return false
  return new Date(value).toISOString().slice(0, 19) === value.slice(0, 19)
}

export function cloneConfiguration(value: StrategyConfiguration): StrategyConfiguration {
  return JSON.parse(JSON.stringify(value)) as StrategyConfiguration
}
function shape(value: unknown): StrategyConfiguration {
  if (!exact(value, configKeys) || value.strategy_id !== 'resonance-regime-v1' || value.strategy_version !== '1.2.0'
    || value.observation_version !== 'resonance-daily-closed-v3' || value.warmup_policy !== 'regime-available-v1'
    || !text(value.config_revision, 128) || !text(value.benchmark_role, 32) || !timestamp(value.valid_from) || !timestamp(value.valid_until)
    || integerKeys.some(key => !Number.isSafeInteger(value[key]))
    || weightKeys.some(key => typeof value[key] !== 'number' || !Number.isFinite(value[key]))) return invalid()
  for (const key of ['symbol_roles', 'execution_symbols']) {
    const rows = value[key]
    if (!Array.isArray(rows) || rows.length < 1 || rows.length > 8 || rows.some(pair => !Array.isArray(pair) || pair.length !== 2
      || !text(pair[0], 32) || typeof pair[1] !== 'string' || !symbol.test(pair[1]))) return invalid()
  }
  return cloneConfiguration(value as StrategyConfiguration)
}
function receipt(value: unknown): ConfigurationReceipt {
  if (!exact(value, ['revision', 'request_id', 'request_sha256', 'configuration_sha256', 'configuration', 'saved_at'])
    || !Number.isSafeInteger(value.revision) || (value.revision as number) < 1 || (value.revision as number) > 32
    || !identity(value.request_id) || !digest(value.request_sha256) || !digest(value.configuration_sha256) || !timestamp(value.saved_at)) return invalid()
  return { ...(value as ConfigurationReceipt), configuration: shape(value.configuration) }
}
export function decodeConfigurationWorkspace(value: unknown): ConfigurationWorkspace {
  if (!exact(value, ['schema', 'owner_id', 'available', 'editable', 'reason', 'catalog', 'store', 'max_versions', 'runtime_effect'])
    || value.schema !== prefix + 'workspace.v1' || !identity(value.owner_id) || typeof value.available !== 'boolean'
    || typeof value.editable !== 'boolean' || value.editable && !value.available || value.runtime_effect !== false || value.max_versions !== 32
    || (value.editable ? value.reason !== null : !text(value.reason)) || !Array.isArray(value.catalog) || value.catalog.length !== 1) return invalid()
  const catalog: ConfigurationCatalog[] = value.catalog.map(item => {
    if (!exact(item, ['strategy_id', 'strategy_version', 'label', 'example_kind', 'example']) || item.strategy_id !== 'resonance-regime-v1'
      || item.strategy_version !== '1.2.0' || !text(item.label) || item.example_kind !== 'synthetic') return invalid()
    return { ...(item as ConfigurationCatalog), example: shape(item.example) }
  })
  let store: ConfigurationStore | null = null
  if (value.store !== null) {
    const current = value.store
    if (!exact(current, ['schema', 'store_id', 'revision', 'versions']) || current.schema !== prefix + 'state.v1' || !identity(current.store_id)
      || !Number.isSafeInteger(current.revision) || (current.revision as number) < 0 || (current.revision as number) > 32
      || !Array.isArray(current.versions) || current.versions.length !== current.revision) return invalid()
    const versions = current.versions.map(receipt)
    if (versions.some((item, index) => item.revision !== index + 1) || new Set(versions.map(item => item.request_id)).size !== versions.length) return invalid()
    store = { ...(current as ConfigurationStore), versions }
  }
  if (value.available && store === null || !value.available && store !== null) return invalid()
  return { ...(value as ConfigurationWorkspace), catalog, store }
}
function decodeValidation(value: unknown): ConfigurationValidation {
  if (!exact(value, ['schema', 'configuration', 'configuration_sha256', 'validation_time', 'validity', 'qualification'])
    || value.schema !== prefix + 'validation.v1' || !digest(value.configuration_sha256) || !timestamp(value.validation_time)
    || !['not_yet_valid', 'within_window', 'expired'].includes(value.validity as string)
    || value.qualification !== 'configuration-only; data/runtime/execution-unqualified') return invalid()
  return { ...(value as ConfigurationValidation), configuration: shape(value.configuration) }
}

export class ConfigurationWriteError extends Error {
  constructor(readonly state: 'conflict' | 'rejected' | 'unknown') {
    super(state === 'conflict' ? '策略配置版本已变化，请重新读取后确认'
      : state === 'rejected' ? '策略参数或请求未通过业务校验，请检查窗口、预算、映射和有效期'
        : '策略配置保存结果尚未确认，请沿原请求编号核查；请勿重复保存')
    this.name = 'ConfigurationWriteError'
  }
}
async function write(path: string, method: 'POST' | 'PUT', value: unknown): Promise<unknown> {
  const body = JSON.stringify(value)
  if (new TextEncoder().encode(body).length > 16 * 1024) return invalid()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 6500)
  let status: number | undefined
  try {
    const response = await fetch(path, { method, credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body, signal: controller.signal })
    status = response.status
    if (!response.ok) throw new Error()
    return await response.json()
  } catch {
    throw new ConfigurationWriteError(status === 409 ? 'conflict' : status !== undefined && [403, 413, 415, 422].includes(status) ? 'rejected' : 'unknown')
  } finally { clearTimeout(timer) }
}

export async function fetchConfigurationWorkspace(signal?: AbortSignal): Promise<ConfigurationWorkspace> {
  return decodeConfigurationWorkspace(await fetchReadJson<unknown>(CONFIGURATION_ENDPOINT, '策略配置', signal, 'workspace', 6500))
}
export async function validateStrategyConfiguration(configuration: StrategyConfiguration): Promise<ConfigurationValidation> {
  // 草稿的有效期允许用户编辑成任意带时区ISO；业务合法性完全交唯一核决定。
  return decodeValidation(await write(CONFIGURATION_ENDPOINT + '/validate', 'POST', { schema: prefix + 'validation-request.v1', configuration }))
}
function matches(saved: ConfigurationReceipt, intent: SaveConfigurationIntent) {
  const canonical = (value: StrategyConfiguration) => JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b))))
  return saved.request_id === intent.request_id && saved.revision === intent.expected_revision + 1
    && saved.configuration_sha256 === intent.configuration_sha256 && canonical(saved.configuration) === canonical(intent.configuration)
}
export async function saveStrategyConfiguration(intent: SaveConfigurationIntent): Promise<ConfigurationReceipt> {
  if (!identity(intent.store_id) || !identity(intent.request_id) || !digest(intent.configuration_sha256)) return invalid()
  const { configuration_sha256: _sha, ...bound } = intent
  try {
    const value = await write(CONFIGURATION_ENDPOINT, 'PUT', { schema: prefix + 'save.v1', ...bound })
    if (!exact(value, ['schema', 'store_id', 'receipt', 'runtime_effect']) || value.schema !== prefix + 'saved.v1'
      || value.store_id !== intent.store_id || value.runtime_effect !== false) return invalid()
    const saved = receipt(value.receipt)
    if (!matches(saved, intent)) return invalid()
    return saved
  } catch (error) {
    if (error instanceof ConfigurationWriteError) throw error
    throw new ConfigurationWriteError('unknown')
  }
}
export async function lookupConfigurationRequest(intent: SaveConfigurationIntent, signal?: AbortSignal): Promise<ConfigurationReceipt | null> {
  if (!identity(intent.store_id) || !identity(intent.request_id)) return invalid()
  const value = await fetchReadJson<unknown>(`${CONFIGURATION_ENDPOINT}/requests/${intent.request_id}?store_id=${intent.store_id}`, '策略配置原请求', signal, 'workspace', 6500)
  if (!exact(value, ['schema', 'store_id', 'request_id', 'status', 'receipt']) || value.schema !== prefix + 'request.v1'
    || value.store_id !== intent.store_id || value.request_id !== intent.request_id) return invalid()
  if (value.status === 'absent' && value.receipt === null) return null
  if (value.status !== 'saved') return invalid()
  const saved = receipt(value.receipt)
  if (!matches(saved, intent)) return invalid()
  return saved
}
