export type Row = Record<string, string | number | null>
export interface Line { key: string; name: string; color: string; unit: string; panel: string; shown: boolean; formula: string; reading: string; chart_type?:string; candle_fields?:string[]; observed_dates_only?:boolean; observation_dates?:string[]; axis?:'right'; signed?:boolean; reference_levels?:{value:number;name:string;color:string}[] }
export interface Definition {
  id: string; definition_version?: string; board: string; label: string; frequency: string; source: string; source_url: string;
  unit: string; lines: Line[]; coverage: { start: string; end: string; observations: number };
  field_schema: Record<string, { label: string; unit?: string }>; primary_field: string;
  parameters: boolean; calculation_defaults?: { window: number; k: number; method: string; pcr_type: string };
  how_to_read?: { purpose: string; signals: string[]; example?: string; boundary: string };
  term_notes?: { term: string; note: string }[]; limitations: string[]; reading: string; formula: string;
  reference_levels?: { value: number; name: string; color: string }[]; reference_review?: unknown;
  event_markers?: { field: string; anchor: string; values: {code: number; label: string; color: string}[] } | {date: string; key: string; name: string; position: string; value: number}[];
  axis_type?: string; metric_right?: boolean; price_above?: boolean; overlay?: boolean;
  primary_coverage?: {start:string|null;end:string|null;observations:number};
  panel_groups?: {id:string;title:string;min?:number;max?:number}[];
  trading_days?: string[];
  context_source?: {symbol:string;label:string;table:string};
}
export interface Catalog {
  snapshot_id: string; published_at: string;
  recent_events?: Record<string, {state: 'complete' | 'incomplete'; events: {date: string; label: string}[]}>;
  boards: { id: string; label: string }[];
  datasets: { id: string; board: string; label: string; source?: string; frequency: string; dataset_version: string; coverage: Definition['coverage']; default_preset?: 'all' }[];
  preferences: { default_board: string; default_datasets: Record<string, string> };
}
export interface Series { snapshot_id: string; dataset_version: string; definition: Definition; rows: Row[]; total: number; next_cursor: string | null }
export interface History { coverage: Definition['coverage']; points: { date: string; value: number | null }[]; aggregation: string; raw_count: number }
export type Range = { start: string; end: string }
export type DataRepair = {
  /** 同一轮补齐在重新连接后保持的身份。 */
  id: string
  /** 调度器记录的当前阶段。 */
  state: 'queued' | 'running' | 'complete' | 'partial' | 'failed'
  /** 无法启动整轮时的原因码。 */
  reason?: string
  /** 已提交到 WT 数据进程的补齐请求。 */
  wt_request?: { /** 按来源核定的闭合目标日。 */ dates: string[] }
  /** WT 原日更的业务确认。 */
  wt_receipt?: { /** 运行、发布或失败阶段。 */ state: 'running' | 'published' | 'failed' }
  /** 本轮实际核对的来源状态。 */
  items: {
    /** 现有来源登记 ID。 */
    source_id: string
    /** 逐项核对与补齐阶段。 */
    state: 'pending' | 'checking' | 'repairing' | 'complete' | 'missing' | 'waiting_for_wt' | 'waiting_for_wt_repair'
    /** 在已核覆盖范围内仍缺的交易日数。 */
    missing_count: number | null
    /** 仍有缺口的输入表或指标，沿实际覆盖检查。 */
    inputs?: {
      /** 源表或指标的登记身份。 */
      id: string
      /** 此输入缺失的交易日数。 */
      missing_count: number
      /** 最早缺失交易日。 */
      first_missing: string
      /** 最晚缺失交易日。 */
      last_missing: string
    }[]
    /** 仍有缺口时的原因码。 */
    reason: string | null
  }[]
}
