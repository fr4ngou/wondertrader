export type Row = Record<string, string | number | null>
export interface Line { key: string; name: string; color: string; unit: string; panel: string; shown: boolean; formula: string; reading: string; chart_type?:string; candle_fields?:string[]; observed_dates_only?:boolean }
export interface Definition {
  id: string; definition_version?: string; board: string; label: string; frequency: string; source: string; source_url: string;
  unit: string; lines: Line[]; coverage: { start: string; end: string; observations: number };
  field_schema: Record<string, { label: string; unit?: string }>; primary_field: string;
  parameters: boolean; calculation_defaults?: { window: number; k: number; method: string; pcr_type: string };
  how_to_read?: { purpose: string; signals: string[]; example?: string; boundary: string };
  term_notes?: { term: string; note: string }[]; limitations: string[]; reading: string; formula: string;
  reference_levels?: { value: number; name: string; color: string }[]; reference_review?: unknown;
  axis_type?: string; metric_right?: boolean; price_above?: boolean; overlay?: boolean;
  primary_coverage?: {start:string|null;end:string|null;observations:number};
}
export interface Catalog {
  snapshot_id: string; published_at: string;
  boards: { id: string; label: string }[];
  datasets: { id: string; board: string; label: string; source?: string; frequency: string; dataset_version: string; coverage: Definition['coverage']; default_preset?: 'all' }[];
  preferences: { default_board: string; default_datasets: Record<string, string> };
}
export interface Series { snapshot_id: string; dataset_version: string; definition: Definition; rows: Row[]; total: number; next_cursor: string | null }
export interface History { coverage: Definition['coverage']; points: { date: string; value: number | null }[]; aggregation: string; raw_count: number }
export type Range = { start: string; end: string }
