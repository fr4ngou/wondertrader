export type WorkspaceId =
  | 'dashboard'
  | 'market'
  | 'strategies'
  | 'portfolio'
  | 'orders'
  | 'operations'

export interface ConsoleAccount {
  agent_id: string
  account_label?: string | null
  trading_mode: 'shadow' | 'simulation' | 'live'
  account_environment: 'simulation' | 'live'
  reconciled: boolean
  ready_for_simulation_order: boolean
  heartbeat_at?: string | null
  snapshot_at?: string | null
  positions: Record<string, number>
  available_positions: Record<string, number>
  quote_count: number
  open_command_count: number
  blocking_reasons: string[]
}

export interface PerformanceReport {
  report_hash: string
  source_result_id: string
  dataset_version: string
  source_kind: 'qmt_native_fills' | 'versioned_fill_model'
  period: '1m' | '5m' | '1d'
  model_version: string
  initial_capital: number
  final_net_asset_value: number
  total_return: number
  annualized_return: number
  annualized_volatility: number
  sharpe_ratio?: number | null
  maximum_drawdown: number
  turnover: number
  trade_count: number
  benchmark_return?: number | null
  excess_return?: number | null
  valuation_started_at: string
  valuation_finished_at: string
  generated_at: string
}

export interface DirectionConfig {
  config_id: string
  version: number
  themes: string[]
  include_symbols: string[]
  exclude_symbols: string[]
  etf_candidates: Record<string, string[]>
  strategy_budgets: Record<string, number>
  strategy_parameters: Record<string, Record<string, string | number | boolean>>
  mode: 'shadow' | 'simulation'
  global_kill_switch: boolean
  account_kill_switch: boolean
  disabled_strategies: string[]
  unmanaged_position_policy: 'preserve'
  valid_until: string
  created_at: string
}

export interface StrategyConfigurationValidationReport {
  config_id: string
  config_version: string
  registry_version: string
  valid: boolean
  resolved_strategy_versions: Record<string, string>
  resolved_parameters: Record<string, Record<string, string | number | boolean>>
  reasons: string[]
  validated_at: string
}

export interface DirectionConfigActivationRecord {
  activation_id: string
  config_id: string
  config_version: string
  action: 'activate' | 'rollback'
  previous_config_id?: string | null
  supersedes_config_id?: string | null
  registry_version: string
  validation_report: StrategyConfigurationValidationReport
  occurred_at: string
  evidence_refs: string[]
}

export interface DirectionConfigDiff {
  schema_version: '1.0'
  from_config_id: string
  to_config_id: string
  added_themes: string[]
  removed_themes: string[]
  added_symbols: string[]
  removed_symbols: string[]
  budget_changes: Record<string, { from: number | null; to: number | null }>
  candidate_changes: Record<string, { from: string[]; to: string[] }>
  newly_disabled_strategies: string[]
  newly_enabled_strategies: string[]
  mode_changed: boolean
  kill_switch_changed: boolean
}

export type ConfigVersionControlAction = 'activate' | 'rollback'

export interface ConfigVersionControlRequest {
  schema_version: '1.0' | '1.1'
  action: ConfigVersionControlAction
  target_config_id: string
  target_config_version: number
  reason: string
  idempotency_key: string
  expected_active_config_id?: string | null
  supersedes_config_id?: string | null
  expected_gate_updated_at: string
  confirmed: true
}

export interface ConfigVersionControlResult {
  schema_version: '1.0' | '1.1'
  action: ConfigVersionControlAction
  config: DirectionConfig
  gate: AutomationGate
  activation: DirectionConfigActivationRecord
  audit_event_id: string
  replayed: boolean
}

export interface AutomationGate {
  active_config_id?: string | null
  global_kill_switch: boolean
  account_kill_switch: boolean
  auto_execution_enabled: boolean
  updated_at: string
}

export interface AutomationGateUpdateRequest {
  schema_version: '1.0'
  active_config_id: string | null
  auto_execution_enabled: boolean
  expected_gate_updated_at: string
}

export interface ReleaseReadiness {
  strategy_id: string
  strategy_version: string
  code_commit: string
  strategy_artifact_sha256: string
  evidence_binding: 'code_commit' | 'strategy_artifact'
  config_version: string
  dataset_version: string
  passed_stages: string[]
  highest_passed_stage?: string | null
  next_required_stage?: string | null
  matching_gate_count: number
  stale_gate_count: number
  blockers: string[]
  evaluated_at?: string
}

export interface ReleaseGateEvidence {
  gate_id: string
  stage: 'historical_backtest' | 'event_replay' | 'realtime_shadow' | 'simulation' | 'small_live'
  strategy_id?: string | null
  strategy_version?: string | null
  code_commit: string
  config_version: string
  dataset_version: string
  status: 'pending' | 'passed' | 'failed'
  required_evidence_refs: string[]
  evidence_refs: string[]
  approved_by?: string | null
  approved_at?: string | null
  reasons: string[]
  created_at: string
}

export type PromotionReviewFromStage =
  | 'historical_backtest'
  | 'event_replay'
  | 'realtime_shadow'

export type PromotionReviewToStage =
  | 'event_replay'
  | 'realtime_shadow'
  | 'simulation'

export interface PromotionReviewCreateRequest {
  schema_version: '1.0'
  strategy_id: string
  strategy_version: string
  code_commit: string
  config_version: string
  dataset_version: string
  from_stage: PromotionReviewFromStage
  to_stage: PromotionReviewToStage
  reason: string
  idempotency_key: string
  confirmed: true
}

export interface PromotionReviewState {
  schema_version: '1.0'
  review_id: string
  strategy_id: string
  strategy_version: string
  code_commit: string
  config_version: string
  dataset_version: string
  from_stage: PromotionReviewFromStage
  to_stage: PromotionReviewToStage
  state: 'draft' | 'ready'
  readiness: ReleaseReadiness
  operator_session_id: string
  reason: string
  request_sha256: string
  evidence_refs: string[]
  created_at: string
  reviewed_at: string
  switches_environment: false
  grants_approval: false
  execution_authorized: false
}

export interface PromotionReviewResult {
  schema_version: '1.0'
  review: PromotionReviewState
  audit_event_id: string
  replayed: boolean
}

export interface AuditEventSummary {
  schema_version: '1.0'
  event_id: string
  event_type: string
  occurred_at: string
  ingested_at: string
  source: string
  correlation_id: string
  strategy_id?: string | null
  config_version?: string | null
  model_version?: string | null
  payload_keys: string[]
  payload_sha256: string
  evidence_refs: string[]
  read_only: true
}

export interface AuditEventFilters {
  limit: number
  offset: number
  event_type?: string
  source?: string
  strategy_id?: string
  correlation_id?: string
}

export interface AuditEventPage {
  schema_version: '1.0'
  items: AuditEventSummary[]
  total: number
  limit: number
  offset: number
  has_more: boolean
  read_only: true
}

export type OperatorActionCategory =
  | 'strategy_control'
  | 'config_control'
  | 'emergency_stop'
  | 'promotion_review'
  | 'backtest_control'
  | 'watchlist_control'
  | 'simulation_promotion'

export interface OperatorActionHistoryItem {
  schema_version: '1.0'
  action_id: string
  category: OperatorActionCategory
  action: string
  occurred_at: string
  actor_label: 'local_operator'
  target_label: string
  strategy_id?: string | null
  config_version?: string | null
  environment: 'shadow' | 'simulation' | 'backtest' | 'none'
  reason?: string | null
  outcome: 'recorded'
  effects: string[]
  evidence_event_id: string
  read_only: true
  executable: false
}

export interface OperatorActionHistoryPage {
  schema_version: '1.0'
  items: OperatorActionHistoryItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
  contains_operator_session_ids: false
  contains_raw_payload: false
  contains_accounts_or_orders: false
  read_only: true
  executable: false
}

export interface AuditEventExportFilters {
  event_type?: string | null
  source?: string | null
  strategy_id?: string | null
  correlation_id?: string | null
  occurred_from?: string | null
  occurred_to?: string | null
}

export interface AuditEventExport {
  schema_version: '1.0'
  generated_at: string
  filters: AuditEventExportFilters
  total_matching_event_count: number
  exported_event_count: number
  truncated: boolean
  events: AuditEventSummary[]
  export_sha256: string
  contains_raw_payload: false
  contains_account_ids: false
  contains_secrets_or_signatures: false
  contains_executable_orders: false
  read_only: true
  executable: false
}

export interface TradingFacts {
  risk_approval_count: number
  order_command_count: number
  execution_event_count: number
  dead_letter_event_count: number
}

export interface DailyAudit {
  trade_date: string
  matched: boolean
  reasons: string[]
  order_counts: Record<string, number>
  execution_event_count: number
  unresolved_command_count: number
  generated_at: string
}

export interface AutomationRuntimeIssue {
  schema_version: '1.0'
  issue_key: string
  issue_code: string
  source_component: string
  severity: 'info' | 'warning' | 'critical'
  impact_scope_kind: 'platform' | 'account' | 'symbol' | 'strategy'
  impact_scope_id: string
  lifecycle: 'active' | 'stale' | 'resolved'
  last_authoritative_state: 'active' | 'resolved'
  relationship?: 'root_cause' | 'symptom' | 'projection'
  root_issue_key?: string | null
  revision: number
  retryable: boolean
  user_safe_summary: string
  registry_version?: string | null
  user_safe_title?: string | null
  recommended_next_step?: string | null
  runbook_path?: string | null
  reason_parameters: Record<string, string | number | boolean>
  evidence_refs: string[]
  first_observed_at: string
  last_observed_at: string
  last_authoritative_observed_at: string
  coverage_interrupted_at?: string | null
  resolved_at?: string | null
}

export interface AutomationRuntimeStatus {
  schema_version: '1.0'
  generated_at: string
  automation_gate: 'enabled' | 'disabled' | 'stopped' | 'unavailable'
  loop_state: 'idle' | 'waiting' | 'advancing' | 'converging' | 'blocked' | 'unavailable'
  business_health: 'healthy' | 'degraded' | 'blocked' | 'unavailable'
  trading_impact: 'none' | 'new_risk_blocked' | 'symbol_blocked' | 'account_blocked' | 'unavailable'
  last_successful_loop_at?: string | null
  current_block_started_at?: string | null
  last_observed_at: string
  source_component: 'portfolio'
  issues: AutomationRuntimeIssue[]
}

export interface OperationalLogEvent {
  schema_version: '1.0'
  event_at: string
  collected_at: string
  severity: 'debug' | 'info' | 'warning' | 'error' | 'critical'
  service: string
  component: string
  environment: 'local' | 'shadow' | 'simulation' | 'live'
  issue_code?: string | null
  user_safe_summary: string
  exception_type?: string | null
  stack_fingerprint?: string | null
  stack_frames: string[]
  correlation_id?: string | null
  trace_id?: string | null
  strategy_id?: string | null
  strategy_version?: string | null
  source_version: string
  redaction_policy_version: string
  structured_metadata: Record<string, string | number | boolean>
}

export interface OperationalLogFingerprintGroup {
  schema_version: '1.0'
  stack_fingerprint: string
  issue_code: string
  severity: 'warning' | 'error' | 'critical'
  service: string
  count: number
  first_event_at: string
  last_event_at: string
  user_safe_summary: string
  lifecycle: 'active' | 'recovered' | 'startup_transient'
  service_ready?: boolean | null
  lifecycle_reason: string
}

export interface OperationalLogQueryPage {
  schema_version: '1.0'
  events: OperationalLogEvent[]
  fingerprint_groups: OperationalLogFingerprintGroup[]
  coverage: {
    schema_version: '1.0'
    status: 'complete' | 'partial' | 'unavailable'
    loki_status: 'healthy' | 'unavailable'
    alloy_status: 'healthy' | 'degraded' | 'unavailable'
    source_status: 'healthy' | 'degraded' | 'unavailable'
    minio_status: 'healthy' | 'degraded' | 'unavailable'
    persistence_status: 'verified' | 'unavailable'
    persistence_last_write_at?: string | null
    queried_at: string
    last_successful_query_at?: string | null
    last_successful_collection_at?: string | null
    latest_event_at?: string | null
    retention_days: 14
    retention_status: 'verified' | 'unavailable'
    source_delay_seconds?: number | null
    collection_lag_seconds?: number | null
    dropped_count?: number | null
    drop_status: 'observed' | 'unavailable'
    export_failure_count?: number | null
    export_status: 'observed' | 'unavailable'
    invalid_response_line_count: number
    failure_code?: string | null
  }
  truncated: boolean
  next_cursor?: string | null
  read_only: true
}

export interface ExecutionQueueItem {
  schema_version: '1.0'
  queue_item_id: string
  correlation_id: string
  identity: {
    source_kind: 'automatic_strategy' | 'operator_manual'
    strategy_lineage_id?: string | null
    genesis_epoch_id?: string | null
  }
  strategy_id?: string | null
  strategy_version?: string | null
  config_version?: string | null
  symbol: string
  side: 'buy' | 'sell' | 'cancel'
  target_quantity: number
  completed_quantity: number
  remaining_quantity: number
  stage: 'target_observed' | 'capital_pending' | 'planned' | 'risk_pending' | 'approved' | 'command_pending' | 'signed' | 'submitted' | 'partial_fill' | 'filled' | 'cancelled' | 'rejected' | 'failed' | 'superseded'
  wait_state?: 'waiting_market' | 'waiting_session' | 'waiting_allocation' | 'blocked' | null
  stage_entered_at: string
  last_changed_at: string
  event_at: string
  originated_before_today: boolean
  changed_today: boolean
  blocking_issue_codes: string[]
  next_legal_stage?: string | null
  risk_status: 'not_evaluated' | 'accepted' | 'rejected' | 'unavailable'
  approval_status: 'not_reached' | 'accepted' | 'failed' | 'unavailable'
  command_status: 'not_reached' | 'accepted' | 'failed' | 'unavailable'
}

export interface ExecutionQueueProjection {
  schema_version: '1.0'
  agent_id: string
  account_id: string
  account_environment: 'simulation' | 'live'
  projection_revision: number
  as_of: string
  trading_date?: string | null
  calendar_status: 'available' | 'unavailable'
  today_activity: ExecutionQueueItem[]
  carryover_pending: ExecutionQueueItem[]
  source_coverage: Record<string, 'complete' | 'partial' | 'unavailable'>
  truncated: boolean
  next_cursor?: string | null
  read_only: true
}

export interface AccountExecutionCapitalAllocation {
  allocation_decision_id: string
  strategy_id: string
  strategy_lineage_id: string
  strategy_spendable_cash: number
  requested_amount: number
  allocated_amount: number
  decision: 'allocated' | 'partially_allocated' | 'rejected'
  reason_codes: string[]
}

export interface AccountExecutionRiskReservation {
  reservation_id: string
  queue_item_id: string
  strategy_id: string
  strategy_lineage_id: string
  symbol: string
  side: 'buy' | 'sell'
  quantity: number
  still_reserved_quantity: number
  executed_unabsorbed_quantity: number
  released_quantity: number
  cash_reserved: number
  risk_notional_reserved: number
  status: 'provisional' | 'committed' | 'unknown' | 'executed_unabsorbed' | 'released'
  last_changed_at: string
}

export interface AccountExecutionBatchProjection {
  batch_id: string
  account_label: string
  account_environment: 'simulation' | 'live'
  account_boundary_captured_at: string
  current_state: 'planning' | 'active' | 'blocked' | 'invalidated' | 'completed'
  current_reason_codes: string[]
  successor_batch_id?: string | null
  active_config_version: string
  created_at: string
  strategy_count: number
  strategy_ids: string[]
  strategy_lineages: string[]
  available_cash_before_reservations: number
  available_cash_after_reservations: number
  gross_market_value: number
  allocations: AccountExecutionCapitalAllocation[]
  reservations: AccountExecutionRiskReservation[]
}

export interface AccountExecutionProjection {
  schema_version: '1.0'
  generated_at: string
  batches: AccountExecutionBatchProjection[]
  source_coverage: 'complete'
  read_only: true
}

export interface StrategyEligibilityItem {
  schema_version: '1.0'
  strategy_id: string
  strategy_version: string
  strategy_lineage_id?: string | null
  genesis_epoch_id?: string | null
  display_name: string
  registered: boolean
  configured_budget?: number | null
  disabled: boolean
  configured_enabled: boolean
  intent_eligible: boolean
  automation_candidate: boolean
  candidate_ready: boolean
  projection_state: 'ready' | 'blocked' | 'unavailable'
  runtime_lifecycle: 'unavailable' | 'stopped' | 'starting' | 'running' | 'degraded' | 'blocked'
  accepts_new_events: boolean
  valid_target_available: boolean
  dependency_status: Record<string, 'satisfied' | 'blocked' | 'unavailable' | 'not_required'>
  blocking_issue_codes: string[]
  today_pending_count?: number | null
  today_completed_count?: number | null
  today_failed_count?: number | null
}

export interface StrategyEligibilityProjection {
  schema_version: '1.0'
  generated_at: string
  source_component: 'portfolio'
  active_config_id?: string | null
  active_config_version?: string | null
  items: StrategyEligibilityItem[]
  source_coverage: Record<string, 'complete' | 'partial' | 'unavailable'>
  read_only: true
}

export interface StrategyPosition {
  schema_version: '1.0'
  symbol: string
  quantity: number
  valuation_price: number
  market_value: number
}

export interface StrategyCapitalSleeve {
  fees_settlement_pending?: boolean
  schema_version: '1.0' | '1.1'
  strategy_lineage_id: string
  genesis_epoch_id?: string | null
  strategy_id?: string | null
  strategy_version?: string | null
  virtual_cash: number
  spendable_cash?: number | null
  /** Cumulative internal reserve assigned after genesis; null when exact facts are unavailable. */
  capital_contributions_total?: number | null
  /** Same ready capital snapshot; initial principal plus contributed capital. */
  contributed_principal?: number | string | null
  investment_pnl?: number | string | null
  return_on_principal?: number | string | null
  positions?: StrategyPosition[]
  market_value: number
  net_asset_value: number
  opening_net_asset_value?: number | null
  realized_pnl?: number | null
  unrealized_pnl?: number | null
  fees?: number | null
  daily_return?: number | null
  total_return?: number | null
  pnl_metrics_available: boolean
  daily_return_available: boolean
  total_return_available?: boolean
  valuation_at?: string | null
  valuation_source: 'account_capital_reconciliation' | 'strategy_capital_snapshot'
  reconciliation_status: 'reconciled' | 'blocked' | 'unavailable'
  reconciliation_issue_codes: string[]
  account_boundary_captured_at: string
}

export interface NonStrategyOwnershipSummary {
  schema_version: '1.0'
  owner_kind: 'operator_manual' | 'external_manual' | 'unknown_history'
  position_count: number
  total_quantity: number
  market_value: number
}

export interface AccountCapitalReconciliation {
  schema_version: '1.0' | '1.1'
  account_label: string
  account_boundary_captured_at: string
  broker_cash?: number | null
  broker_market_value?: number | null
  broker_total_asset?: number | null
  broker_reported_asset_gap?: number | null
  reference_fee_reserve_limit?: number
  unallocated_reference_fee_balance?: number
  strategy_sleeve_count: number
  strategy_sleeves: StrategyCapitalSleeve[]
  non_strategy_ownership: NonStrategyOwnershipSummary[]
  unallocated_strategy_reserve?: number | null
  independent_cash?: number | null
  cash_residual?: number | null
  market_value_residual?: number | null
  asset_residual?: number | null
  amount_tolerance: number
  reflected_state: 'known' | 'unavailable'
  status: 'reconciled' | 'blocked' | 'unavailable'
  blocking_issue_codes: string[]
  calculated_at: string
}

export interface TradingOperationsProjection {
  schema_version: '1.0'
  generated_at: string
  automation_runtime?: AutomationRuntimeStatus | null
  automation_runtime_sources: Partial<Record<'portfolio' | 'operations', AutomationRuntimeStatus>>
  active_issues: AutomationRuntimeIssue[]
  reconciliations: AccountCapitalReconciliation[]
  observability_stack_status: Record<string, 'healthy' | 'degraded' | 'unavailable' | 'verified'>
  source_coverage: Record<string, 'complete' | 'partial' | 'unavailable'>
  read_only: true
  executable: false
}

export interface OperationsSnapshot {
  healthy?: boolean
  platform_services_ready?: boolean
  services?: Array<{
    service: string
    live: boolean
    ready: boolean
    latency_ms: number
    checked_at?: string
    reason?: string | null
    deployment_identity: {
      schema_version: '1.0'
      observation_available: boolean
      expected_code_commit?: string | null
      platform_code_commit?: string | null
      image_code_commit?: string | null
      status: 'matched' | 'mismatch' | 'unconfigured' | 'unavailable'
      reasons: string[]
      read_only: true
    }
  }>
  alerts?: Array<{
    alert_key: string
    category: string
    severity: 'info' | 'warning' | 'critical'
    source: string
    active: boolean
    observed_value?: string | number | boolean | null
    threshold?: string | number | boolean | null
    first_seen_at?: string
    last_seen_at?: string
    evidence_refs?: string[]
  }>
  trading_facts?: TradingFacts
  automation_runtime?: AutomationRuntimeStatus | null
  runtime_issues?: AutomationRuntimeIssue[]
  observability_stack_status?: Record<string, 'healthy' | 'degraded' | 'unavailable' | 'verified'>
  observability_profile_enabled?: boolean | null
  market_bar_workers?: Array<{
    period: string
    running: boolean
    schedule_state: string
    latest_closed_bar_at?: string | null
  }>
  [key: string]: unknown
}

export interface OperationPolicy {
  schema_version: '1.0'
  policy_id: string
  operation_ids: string[]
  queue_timeout_ms: number
  execution_timeout_ms: number
  response_grace_ms: number
  total_timeout_ms: number
  max_attempts: number
  retry_backoff_initial_ms: number
  retry_backoff_max_ms: number
  retryable_error_codes: string[]
  checkpoint_scope: 'none' | 'symbol' | 'segment'
  terminal_proof_window_ms: number
  max_concurrency: number
}

export interface OperationsHistoryJobSummary {
  schema_version: '1.0'
  job_id: string
  dataset_version: string
  symbols: string[]
  period: '1m' | '5m' | '15m' | '30m' | '60m' | '1d'
  status: 'queued' | 'running' | 'stop_requested' | 'stopped' | 'succeeded' | 'failed'
  completed_segments: number
  remaining_segments: number
  current_symbol?: string | null
  current_start_date?: string | null
  current_end_date?: string | null
  estimated_remaining_seconds?: number | null
  heartbeat_at?: string | null
  created_at: string
  updated_at: string
  completed_at?: string | null
  error_code?: string | null
  error_message?: string | null
  read_only: true
}

export interface ThresholdRegistryEntry {
  schema_version: '1.0'
  key: string
  value: string | number | boolean
  unit: 'seconds' | 'milliseconds' | 'count' | 'bytes' | 'ratio' | 'boolean'
  classification: 'risk_policy' | 'measured' | 'engineering_provisional'
  owner: string
  applies_to: string[]
  rationale: string
  evidence_refs: string[]
  last_reviewed: string
  adjustment: 'adr_required' | 'policy_approval_required'
}

export interface DatabaseMigrationStatus {
  schema_version: '1.0'
  generated_at: string
  observation_available: boolean
  source_versions: string[]
  applied_versions: string[]
  missing_versions: string[]
  unknown_applied_versions: string[]
  checksum_mismatch_versions: string[]
  latest_source_version?: string | null
  latest_applied_version?: string | null
  contiguous: boolean
  up_to_date: boolean
  read_only: true
  executable: false
}

export interface OperationsWorkbenchProjection {
  schema_version: '1.3'
  generated_at: string
  database_migrations: DatabaseMigrationStatus
  history_jobs: OperationsHistoryJobSummary[]
  operation_policies: OperationPolicy[]
  thresholds: ThresholdRegistryEntry[]
  conversation_receipt_observation_available: boolean
  conversation_receipt_invalid_count: number
  conversation_receipts: ConversationOperationReceiptSummary[]
  read_only: true
}

export interface ConversationOperationReceiptSummary {
  schema_version: '1.0'
  receipt_sha256: string
  plan_sha256: string
  operation_id: string
  risk_class: 'read_only' | 'research_write'
  status: 'succeeded' | 'failed' | 'timed_out'
  started_at: string
  completed_at: string
  duration_ms: number
  git_commit: string
  output_count: number
  output_bytes: number
  strategy?: string | null
  total_return?: number | null
  annualized_return?: number | null
  maximum_drawdown?: number | null
  trade_count?: number | null
  summary_lines: string[]
  content_verified: true
  artifacts_verified: boolean
  artifact_verification_status?: 'verified' | 'not_checked' | 'failed'
  trading_side_effects: 'none'
  read_only: true
  executable: false
}

export interface ConsoleOverview {
  generated_at: string
  read_only: true
  operations?: OperationsSnapshot | null
  account?: ConsoleAccount | null
  active_config?: DirectionConfig | null
  simulation_promotion?: SimulationPromotionRecord | null
  automation_gate?: AutomationGate | null
  trading_operations?: TradingOperationsProjection | null
  release_gates: ReleaseGateEvidence[]
  release_readiness: ReleaseReadiness[]
  performance_reports: PerformanceReport[]

  daily_audit?: DailyAudit | null
  errors: Record<string, string>
}

export interface ConsoleBootstrap {
  schema_version: '1.0' | '1.1' | '1.2' | '1.3' | '1.4' | '1.5'
  generated_at: string
  overview: ConsoleOverview
  overview_complete?: boolean
  overview_details_path?: '/v1/console/overview'
  qmt_connection_status?: QMTConnectionStatus | null
  control_locked: boolean
  control_unlock_available: boolean
  control_session?: OperatorControlSession | null
  ui_capabilities?: ConsoleUICapabilityManifest | null
  display_only?: boolean
  
  backtest_reports_available?: boolean
  live_available: false
  manual_order_available: false
  manual_cancel_available: false
  workspaces: WorkspaceId[]
}

export type ProjectMilestoneState = 'completed' | 'validating' | 'accumulating' | 'blocked'

export interface ProjectEngineeringMilestoneStatus {
  id: string
  status: ProjectMilestoneState
  authority: string
  blocks_new_feature_work: boolean
  preserves_business_focus: string
  trading_mode_change: false
}

export interface ProjectMilestoneStatusItem {
  id: string
  title: string
  status: ProjectMilestoneState
  summary: string
  next_actions: string[]
  user_test_ids: string[]
}

export type ProjectUserTestState = 'ready' | 'accumulating' | 'blocked' | 'completed'
export type ProjectDeferredIssueState = 'deferred' | 'in_progress' | 'resolved'

export interface ProjectCompletionMilestone {
  id: string
  title: string
  status: ProjectMilestoneState
}

export interface ProjectCompletionUserTest {
  id: string
  milestone: string
  title: string
  status: ProjectUserTestState
}

export interface ProjectCompletionDeferredIssue {
  id: string
  milestones: string[]
  title: string
  status: ProjectDeferredIssueState
}

export interface ProjectCompletionAuditProjection {
  schema_version: '1.3'
  scope: 'M2-M11'
  complete: boolean
  current_focus: string[]
  completed_milestone_ids: string[]
  remaining_milestones: ProjectCompletionMilestone[]
  outstanding_user_tests: ProjectCompletionUserTest[]
  optional_user_tests: ProjectCompletionUserTest[]
  deferred_issues: ProjectCompletionDeferredIssue[]
  registry_sha256: {
    project_milestones: string
    user_test_obligations: string
    deferred_issues: string
  }
  blockers: string[]
  read_only: true
  requires_qmt: false
  runtime_changes: false
  executable: false
}

export interface ProjectStatusProjection {
  schema_version: '1.3'
  generated_at: string
  latest_update: string
  snapshot_scope: 'versioned_roadmap'
  runtime_status_authority: 'console_runtime_projections'
  authority: string
  current_focus: string[]
  active_engineering_milestone: ProjectEngineeringMilestoneStatus
  milestones: ProjectMilestoneStatusItem[]
  registry_sha256: string
  completion_audit: ProjectCompletionAuditProjection
  read_only: true
  requires_qmt: false
  runtime_changes: false
  executable: false
}

export type QMTConnectionLayerState =
  | 'online'
  | 'busy'
  | 'degraded'
  | 'stale'
  | 'offline'
  | 'unavailable'
  | 'not_exposed'

export interface QMTConnectionLayer {
  schema_version: '1.0'
  layer: 'gateway' | 'agent' | 'trading_server' | 'account'
  state: QMTConnectionLayerState
  observed_at?: string | null
  age_seconds?: number | null
  evidence_source: 'gateway_sync' | 'agent_heartbeat' | 'account_snapshot' | 'qmt_not_exposed'
  detail: string
}

export interface QMTConnectionStatus {
  schema_version: '1.0'
  agent_id: string
  generated_at: string
  layers: QMTConnectionLayer[]
  blocking_reasons: string[]
  read_only: true
  executable: false
}

export interface QMTExecutionBoundaryStatus {
  schema_version: '1.0'
  agent_id: string
  agent: QMTConnectionLayer
  trading_server: QMTConnectionLayer
  account: QMTConnectionLayer
  platform_mode?: 'shadow' | 'simulation' | null
  agent_mode?: 'shadow' | 'simulation' | 'live' | null
  account_environment?: 'simulation' | 'live' | null
  reconciled?: boolean | null
  bridge_simulation_ready?: boolean | null
  mode_matches?: boolean | null
  published_preflight_ready: boolean
  native_route_attestation: 'not_exposed'
  blocking_reasons: string[]
  generated_at: string
  read_only: true
  executable: false
}

export type OperatorControlCapability =
  | 'strategy_control'
  | 'config_version_control'
  | 'emergency_stop'
  | 'backtest_control'
  | 'promotion_review'
  | 'watchlist_control'
  | 'simulation_intent_review'
  | 'simulation_execution_authorize'
  | 'simulation_command_batch_issue'

export interface ConsoleUICapabilityManifest {
  schema_version: '1.0'
  bff_contract_version: '2026-08-17' | '2026-08-19'
  supported_operator_capabilities: OperatorControlCapability[]
  authorization_source: 'operator_control_session' | 'none'
  grants_operator_authority: false
  live_execution_available: false
  manual_order_available: false
  manual_cancel_available: false
}

export interface OperatorControlSession {
  schema_version: '1.0'
  session_id: string
  issued_at: string
  last_seen_at?: string | null
  idle_expires_at: string
  absolute_expires_at: string
  capabilities: OperatorControlCapability[]
}

export interface OperatorControlStatus {
  schema_version: '1.0'
  locked: boolean
  unlock_available: boolean
  session?: OperatorControlSession | null
  csrf_token?: string | null
  reasons: string[]
}

export interface WatchlistItem {
  symbol: string
  display_name?: string | null
  note?: string | null
  tags: string[]
  added_at: string
}

export interface Watchlist {
  schema_version: '1.0'
  watchlist_id: string
  name: string
  version: number
  items: WatchlistItem[]
  updated_at: string
  affects_strategy: false
}

export interface WatchlistMutationRequest {
  schema_version: '1.0'
  name: string
  expected_version: number
  items: WatchlistItem[]
  confirmed: true
}

export interface WatchlistMutationResult {
  schema_version: '1.0'
  watchlist: Watchlist
  audit_event_id: string
  replayed: boolean
}

export interface MarketSymbolSuggestion {
  schema_version: '1.0'
  symbol: string
  display_name?: string | null
  market_data_available: boolean
  already_in_watchlist: boolean
  source_kinds: Array<'active_config' | 'watchlist' | 'market_fact' | 'order_history' | 'manual_code'>
}

export interface MarketSymbolSuggestionPage {
  schema_version: '1.0'
  query: string
  items: MarketSymbolSuggestion[]
  source_coverage: Record<'active_config' | 'watchlist' | 'market_facts' | 'order_history', 'complete' | 'partial' | 'unavailable'>
}

export interface ProblemDefinition {
  schema_version: '1.0'
  issue_code: string
  title: string
  meaning: string
  impact: string
  recommended_action: string
  fact_source: string
  unavailable_meaning: string
  registry_version: string
  updated_at: string
  match_values: string[]
}

export interface ProblemDictionary {
  schema_version: '1.0'
  definitions: ProblemDefinition[]
  alert_category_labels: Record<string, string>
  alert_source_labels: Record<string, string>
  alert_titles: Record<string, string>
  alert_value_labels: Record<string, string>
}

export interface EmergencyStopControlRequest {
  schema_version: '1.0'
  scope: 'global'
  reason: string
  idempotency_key: string
  expected_gate_updated_at: string
  confirmed: true
}

export interface EmergencyStopControlResult {
  schema_version: '1.0'
  scope: 'account' | 'global'
  gate: AutomationGate
  audit_event_id: string
  replayed: boolean
}

export interface BacktestComparisonDifference {
  order_key: string
  field: 'correlation_id' | 'symbol' | 'side' | 'quantity' | 'limit_price' | 'target_weight' | 'filled_quantity' | 'average_fill_price' | 'status'
  platform_value?: string | number | boolean | null
  qmt_value?: string | number | boolean | null
  tolerance: number
}

export interface BacktestComparisonSummary {
  schema_version: '1.0'
  report_id: string
  dataset_version: string
  strategy_id?: string | null
  strategy_version?: string | null
  source_kind: 'generic' | 'resonance_qmt_portfolio'
  platform_order_count: number
  qmt_order_count: number
  missing_in_qmt_count: number
  missing_in_platform_count: number
  blocking_difference_count: number
  tolerated_difference_count: number
  exact_match: boolean
  gate_passed: boolean
  report_hash: string
  generated_at: string
  read_only: true
  executable: false
}

export interface BacktestComparisonProjection extends BacktestComparisonSummary {
  missing_in_qmt: string[]
  missing_in_platform: string[]
  blocking_differences: BacktestComparisonDifference[]
  tolerated_differences: BacktestComparisonDifference[]
}

export interface StreamEvent {
  schema_version: '1.0'
  seq: number
  event_id: string
  event_type: string
  occurred_at: string
  payload: Record<string, unknown>
}

export type MarketChartPeriod = '1m' | '5m' | '1d' | '1w' | '1mo'

export interface MarketChartCandle {
  occurred_at: string
  open: number
  high: number
  low: number
  close: number
  volume?: number | null
}

export interface MarketChartOverlayEvent {
  kind: 'signal' | 'execution'
  occurred_at: string
  label: string
  direction?: 'increase' | 'hold' | 'decrease' | 'buy' | 'sell' | null
  price?: number | null
  status?: string | null
  source: string
  correlation_id?: string | null
  evidence_refs: string[]
  occurrence_count?: number
}

export interface MarketChartBenchmarkPoint {
  occurred_at: string
  close: number
}

export interface MarketChartBenchmark {
  symbol: string
  points: MarketChartBenchmarkPoint[]
  data_available: boolean
  missing_reason?: string | null
}

export interface MarketChartNativeSource {
  /** 原提供者；公开提供者与Mixed仅用于来源日线，具体分段身份由SDK核验。 */
  provider: 'Qmt' | 'Tdx' | 'BaoStock' | 'Tencent' | 'CSI' | 'Mixed'
  dataset_version: string
  content_id: string
  qualification: 'DevelopmentVerified' | 'NativeVerified' | 'ProductionQualified'
  coverage: 'Unknown'
  adjustment: 'none'
  source_minute_boundary: 'left' | 'right' | 'unknown'
  chart_minute_boundary: 'left' | 'source_label' | 'source_date'
  timezone: 'Asia/Shanghai'
  value_semantics?: 'source'
  timestamp_semantics?: 'source_label' | 'source_date'
  price_unit?: 'CNY' | 'unknown'
  volume_unit?: 'share' | 'lot' | 'unknown'
  amount_unit?: 'CNY' | 'unknown'
}

export interface MarketChartBundle {
  schema_version: '1.0' | '1.1' | '1.2' | '1.3' | '1.4' | '1.5' | '1.6' | '1.7' | '1.8'
  symbol: string
  period: MarketChartPeriod
  candles: MarketChartCandle[]
  data_available: boolean
  as_of?: string | null
  missing_reason?: string | null
  source_period?: '1m' | '1d' | null
  source_bar_count?: number | null
  source_kind?: 'market_bars' | 'resonance_daily' | 'mixed' | 'quote_observations' | 'wondertrader' | null
  native_source?: MarketChartNativeSource | null
  source_observation?: {
    source_schema: 'qmt.source-selection-observation.v1'
    state: 'Archive' | 'Observed' | 'Partial'
    source_window: { from_at: string; to_at: string } | null
    source_rows: number; requested_limit: number; selected_rows: number
    preparation_state: 'NotNeeded' | 'CallReturned' | 'Unknown' | 'Pending' | 'Unavailable' | 'NotSupported' | 'Budget'
    preparation_request_id: string | null
  } | null
  source_provenance?: Array<{
    offset: number; count: number; first_at: string; last_at: string
    metadata: {
      source: { provider: 'Qmt'; instance_id: string; session_id: string; generation: number }
      qualification: 'DevelopmentVerified'; dataset_version: string; content_id: string
      source_license: string; adjustment: 'none'; factor_version: ''; timezone: 'Asia/Shanghai'
      minute_boundary: 'left' | 'right' | 'unknown'; value_semantics: 'source'; timestamp_semantics: 'source_label'
      price_unit: 'CNY' | 'unknown'; volume_unit: 'share' | 'lot' | 'unknown'; amount_unit: 'CNY' | 'unknown'
    }
  }>
  observation_count?: number | null
  volume_available?: boolean
  volume_partial?: boolean
  derived?: boolean
  benchmark?: MarketChartBenchmark | null
  overlays?: MarketChartOverlayEvent[]
  overlay_unavailable_sources?: Array<'benchmark' | 'strategy' | 'bridge'>
  overlays_read_only?: true
  overlays_executable?: false
}

export interface PublicObservationProjection {
  symbol: string
  period: MarketChartPeriod
  candles: MarketChartCandle[]
  chart_available: boolean
  chart_reason?: string | null
  as_of?: string | null
  last_price?: number | null
  price_as_of?: string | null
  price_kind?: 'spot' | 'candle_close' | null
  quote_reason?: string | null
  source_id?: 'eastmoney.public-display' | 'tencent.public-display' | null
  price_source_id?: 'eastmoney.public-display' | 'tencent.public-display' | null
  read_only: true
  trading_eligible: false
}

export interface MarketChartRefreshRequest {
  schema_version: '1.0'
  period: '1m' | '5m'
  requested_count: number
  read_only: true
  executable: false
}

export interface MarketChartRefreshReceipt {
  schema_version: '1.0'
  symbol: string
  requested_period: '1m' | '5m'
  source_period: '1m'
  requested_count: number
  collected_bar_count: number
  latest_closed_at?: string | null
  refreshed_at: string
  coalesced: boolean
  source: 'qmt_market_data_ex'
  read_only: true
  executable: false
}

export interface MarketDataUniverseMember {
  symbol: string
  periods: Array<'1m' | '1d'>
  strategy_refs: string[]
}

export interface ActiveMarketDataUniverse {
  schema_version: '1.0'
  config_id: string
  config_version: string
  registry_version: string
  members: MarketDataUniverseMember[]
  universe_sha256: string
  generated_at: string
  evidence_refs: string[]
  read_only: true
  executable: false
}

export interface MarketDataSubscriptionView {
  schema_version: '1.0' | '1.1'
  symbol: string
  period: '1m' | '1d'
  universe_sha256: string
  gateway_generation: number
  acquisition_mode: 'qmt_native' | 'bridge_poll'
  status: 'active' | 'release_pending' | 'released' | 'failed'
  updated_at: string
}

export interface MarketBarWorkerStatus {
  period: '1m' | '1d'
  enabled: boolean
  running: boolean
  operation_busy: boolean
  attempt_count: number
  success_count: number
  failure_count: number
  last_collected_count: number
  last_attempt_at?: string | null
  last_success_at?: string | null
  last_error_active: boolean
  skip_count: number
  schedule_state:
    | 'continuous'
    | 'waiting_window'
    | 'eligible'
    | 'waiting_current_bar'
    | 'retry_pending'
    | 'completed_today'
    | 'non_trading_day'
    | 'calendar_unavailable'
    | 'no_required_symbols'
  next_eligible_at?: string | null
  latest_closed_bar_at?: string | null
}

export interface MarketDataSubscriptionProjection {
  schema_version: '1.0' | '1.1'
  target_universe: ActiveMarketDataUniverse
  bridge_universe_sha256?: string | null
  gateway_generation?: number | null
  active: MarketDataSubscriptionView[]
  pending_additions: string[]
  pending_removals: string[]
  bridge_converged: boolean
  target_converged: boolean
  lifecycle: 'not_started' | 'waiting_for_gateway' | 'converging' | 'converged' | 'blocked'
  blocking_reasons: string[]
  worker_status_available?: boolean
  worker_statuses?: MarketBarWorkerStatus[]
  collection_ready_periods?: Array<'1m' | '1d'>
  collection_blocking_reasons?: string[]
  checked_at: string
  read_only: true
  executable: false
}

export interface ResonanceDailyBarCoverageItem {
  schema_version: '1.0'
  symbol: string
  latest_closed_at?: string | null
  latest_trade_date?: string | null
  status: 'current' | 'stale' | 'unavailable' | 'future'
  matches_trade_date: boolean
  source_feature_version: 'qmt-1d-v1'
}

export interface ResonanceDailyBarCoverage {
  schema_version: '1.0' | '2.0'
  observation_version?: 'resonance-daily-closed-v3'
  config_id?: string
  strategy_universe_sha256?: string
  required_symbols?: string[]
  trade_date: string
  trade_date_source: 'explicit' | 'official_calendar'
  generated_at: string
  items: ResonanceDailyBarCoverageItem[]
  covered_symbol_count: number
  required_symbol_count: number
  complete: boolean
  read_only: true
  executable: false
}

export interface ResonanceShadowAcceptanceSummary {
  schema_version: '1.0'
  result_sha256: string
  trade_date: string
  generated_at: string
  code_commit: string
  strategy_id: 'resonance-regime-v1'
  strategy_version: '1.0.0'
  config_version: string
  dataset_version: string
  latest_batch_date?: string | null
  latest_outcome: 'not_evaluated' | 'no_change' | 'intents_emitted' | 'blocked'
  daily_bar_worker_running: boolean
  daily_bar_worker_last_collected_count?: number | null
  portfolio_risk_complete: boolean
  baseline_trading_facts: TradingFacts & { captured_at: string }
  observed_trading_facts: TradingFacts & { captured_at: string }
  trading_facts_unchanged: boolean
  ready: boolean
  reasons: string[]
  read_only: true
  executable: false
}

export interface SimulationAcceptanceSummary {
  schema_version: '1.0'
  result_hash: string
  generated_at: string
  code_commit: string
  dataset_version: string
  expected_config_version: string
  evidence_config_version?: string | null
  strategy_id?: string | null
  strategy_version?: string | null
  execution_config_version: string
  account_label: string
  symbol: string
  quantity: number
  window_start: string
  window_end: string
  attempt_count: number
  approval_count: number
  command_count: number
  execution_event_count: number
  snapshot_count: number
  reconciliation_count: number
  passive_cancelled_unfilled: boolean
  buy_filled_quantity: number
  same_day_t1_rejection_observed: boolean
  sell_filled_quantity: number
  next_trading_day_close_observed: boolean
  position_restored: boolean
  commands_are_simulation_only: boolean
  duplicate_command_count: number
  final_reconciliation_matched: boolean
  auto_execution_enabled: boolean
  valid: boolean
  issues: string[]
  read_only: true
  executable: false
}

export interface SimulationStrategyCycleStatus {
  schema_version: '1.0'
  generated_at: string
  agent_id: string
  account_label?: string | null
  state: 'unavailable' | 'blocked' | 'ready_for_manual_cycle' | 'passed' | 'not_applicable'
  agent_running: boolean
  account_reconciled: boolean
  agent_simulation_mode: boolean
  active_simulation_config: boolean
  promotion_lineage_bound: boolean
  mode_only_activation?: boolean
  automation_disabled: boolean
  status_sources_available: boolean
  configuration_ready: boolean
  latest_acceptance_matches_lineage: boolean
  latest_acceptance_valid: boolean
  acceptance_passed: boolean
  target_config_version?: string | null
  evidence_config_version?: string | null
  strategy_id?: string | null
  strategy_version?: string | null
  latest_acceptance?: SimulationAcceptanceSummary | null
  blocking_reasons: string[]
  next_action:
    | 'restore_qmt_agent'
    | 'reconcile_account'
    | 'switch_agent_to_simulation'
    | 'activate_simulation_config'
    | 'restore_promotion_lineage'
    | 'disable_automatic_execution'
    | 'restore_status_projection'
    | 'run_manual_t1_cycle'
    | 'none'
  read_only: true
  executable: false
}

export interface ControlledSimulationDeploymentReadiness {
  schema_version: '1.0'
  generated_at: string
  bff_contract_version: '1.0'
  project_focus_active: boolean
  project_milestone_status: 'completed' | 'validating' | 'accumulating' | 'blocked'
  required_migrations: string[]
  database_migrations: DatabaseMigrationStatus
  required_services: string[]
  services: NonNullable<OperationsSnapshot['services']>
  simulation_cycle: SimulationStrategyCycleStatus
  trading_facts?: (TradingFacts & { captured_at: string }) | null
  status_sources_available: boolean
  required_migrations_ready: boolean
  required_services_ready: boolean
  runtime_deployed: boolean
  configuration_ready: boolean
  acceptance_passed: boolean
  state: 'unavailable' | 'source_only' | 'blocked' | 'ready_for_manual_uat' | 'passed' | 'not_applicable'
  blocking_reasons: string[]
  deployment_permission_required: true
  authorizes_deployment: false
  authorizes_trading: false
  read_only: true
  executable: false
}

export interface MarketQuoteView {
  schema_version: '1.0'
  symbol: string
  captured_at: string
  last_price: number
  bid_price_1?: number | null
  ask_price_1?: number | null
  tick_size: number
  exchange_timestamp?: string | null
  trading_date?: string | null
  market_phase?: 'continuous' | 'closing_auction' | 'after_hours_waiting' | 'after_hours_fixed_price' | 'closed' | 'unknown'
  stale: boolean
  freshness_state: 'verified' | 'unverified' | 'expired'
  age_seconds: number
}

export interface MarketQuoteProjection {
  schema_version: '1.0'
  symbol: string
  quote?: MarketQuoteView | null
  data_available: boolean
  missing_reason?: string | null
}

export interface PortfolioPnLSnapshot {
  schema_version: '1.1'
  environment: 'backtest' | 'shadow' | 'simulation' | 'live'
  captured_at: string
  snapshot_age_seconds: number
  snapshot_stale: boolean
  data_available: boolean
  total_equity?: number | null
  cash?: number | null
  market_value?: number | null
  day_pnl?: number | null
  realized_pnl?: number | null
  unrealized_pnl?: number | null
  fees_total?: number | null
  taxes_total?: number | null
  valuation_source: 'qmt_account_snapshot' | 'unavailable'
  day_pnl_source: 'qmt_equity_delta_from_persisted_day_start' | 'unavailable'
  cash_flow_adjusted: boolean
  realized_pnl_complete: boolean
  realized_pnl_source: 'qmt_account_snapshot' | 'unavailable'
  unrealized_pnl_complete: boolean
  unrealized_pnl_source: 'qmt_position_aggregate' | 'unavailable'
  fees_complete: boolean
  fees_source: 'qmt_account_snapshot' | 'unavailable'
  taxes_complete: boolean
  taxes_source: 'qmt_account_snapshot' | 'unavailable'
  missing_reason?: string | null
}

export interface PortfolioPositionItem {
  schema_version: '1.1'
  symbol: string
  quantity: number
  available_quantity: number
  frozen_quantity: number
  position_value?: number | null
  cost_price?: number | null
  unrealized_pnl?: number | null
  last_price?: number | null
  quote_captured_at?: string | null
  quote_stale?: boolean | null
  valuation_source: 'account_snapshot' | 'latest_quote_derived' | 'unavailable'
  cost_source: 'qmt_position' | 'unavailable'
  unrealized_pnl_source: 'qmt_position' | 'unavailable'
}

export interface PortfolioPositionsSnapshot {
  schema_version: '1.1'
  environment: 'simulation' | 'live'
  captured_at: string
  snapshot_age_seconds: number
  snapshot_stale: boolean
  items: PortfolioPositionItem[]
  data_available: boolean
  valuation_complete: boolean
  total_position_value?: number | null
  missing_valuation_symbols: string[]
  cost_complete: boolean
  missing_cost_symbols: string[]
  unrealized_pnl_complete: boolean
  total_unrealized_pnl?: number | null
  missing_unrealized_pnl_symbols: string[]
  missing_reason?: string | null
  read_only: true
}

export interface PortfolioPerformancePoint {
  occurred_at: string
  net_asset_value: number
  benchmark_value?: number | null
  drawdown: number
  snapshot_seq?: number | null
  total_equity?: number | null
  cash?: number | null
  market_value?: number | null
  day_start_equity?: number | null
  day_pnl?: number | null
}

export interface PortfolioPerformanceSeries {
  schema_version: '1.1'
  environment: 'backtest' | 'shadow' | 'simulation' | 'live'
  points: PortfolioPerformancePoint[]
  data_available: boolean
  missing_reason?: string | null
  source_kind: 'qmt_account_snapshot_history'
  calculation_method: 'raw-account-equity-v1'
  normalization_method: 'first-source-snapshot-equity-v1'
  drawdown_method: 'running-peak-on-full-source-series-v1'
  cash_flow_adjusted: false
  baseline_at?: string | null
  baseline_equity?: number | null
  latest_at?: string | null
  latest_equity?: number | null
  total_return?: number | null
  maximum_drawdown?: number | null
  sample_interval_seconds?: number | null
  source_point_count: number
  generated_at: string
  warnings: string[]
}

export interface StrategyContribution {
  schema_version: '1.0'
  strategy_id: string
  environment: 'backtest' | 'shadow' | 'simulation' | 'live'
  contribution: number
  captured_at: string
  contribution_kind: 'gross_realized_pnl_cny'
  currency: 'CNY'
  matched_quantity: number
  closed_trade_count: number
  open_quantity: number
  fees_included: false
  complete: boolean
  evidence_refs: string[]
}

export interface StrategyContributionSnapshot {
  schema_version: '1.0'
  environment: 'backtest' | 'shadow' | 'simulation' | 'live'
  captured_at: string
  items: StrategyContribution[]
  data_available: boolean
  missing_reason?: string | null
  attribution_scope: 'managed-closed-fills-v1'
  warnings: string[]
}

export interface PortfolioStrategyTarget {
  schema_version: '1.0'
  strategy_id: string
  intent_id: string
  sleeve: 'core' | 'swing'
  requested_weight: number
  applied_weight: number
  confidence: number
  occurred_at: string
  valid_until: string
  evidence_refs: string[]
}

export interface PortfolioAllocationItem {
  schema_version: '1.0'
  symbol: string
  themes: string[]
  configured: boolean
  management_status: 'managed' | 'configured_idle' | 'unmanaged'
  target_state: 'current' | 'expired' | 'missing' | 'invalid_config'
  quantity: number
  position_value?: number | null
  actual_weight?: number | null
  valuation_available: boolean
  requested_target_weight?: number | null
  target_delta?: number | null
  strategy_targets: PortfolioStrategyTarget[]
}

export interface PortfolioThemeExposure {
  theme: string
  symbols: string[]
  actual_weight?: number | null
  actual_complete: boolean
  requested_target_weight: number
}

export interface PortfolioAllocationSnapshot {
  schema_version: '1.0'
  environment: 'shadow' | 'simulation' | 'live'
  captured_at: string
  config_id?: string | null
  config_version?: string | null
  actual_data_available: boolean
  target_data_available: boolean
  actual_missing_reason?: string | null
  target_missing_reason?: string | null
  total_equity?: number | null
  cash_weight?: number | null
  actual_weight_total?: number | null
  requested_target_weight_total?: number | null
  managed_actual_weight?: number | null
  unmanaged_actual_weight?: number | null
  items: PortfolioAllocationItem[]
  theme_exposures: PortfolioThemeExposure[]
  warnings: string[]
  read_only: true
  executable: false
}

export interface StrategyDefinition {
  strategy_id: string
  strategy_version: string
  display_name: string
  description: string
  supported_sleeves: Array<'core' | 'swing'>
  input_event_types: string[]
  output_contract: 'StrategyIntent'
  parameter_definitions: StrategyParameterDefinition[]
  default_budget: number
  maximum_budget: number
  maximum_weight_change: number
  replay_method: string
  implementation_ref: string
  market_data_symbol_source: 'active_config' | 'fixed' | 'none'
  fixed_market_data_symbols: string[]
  market_data_periods: Array<'1m' | '1d'>
  evidence_refs: string[]
}

export interface StrategyParameterDefinition {
  name: string
  value_type: 'number' | 'integer' | 'boolean' | 'string' | 'choice'
  description: string
  required: boolean
  default?: number | string | boolean | null
  minimum?: number | null
  maximum?: number | null
  choices: Array<number | string | boolean>
}

export interface StrategyRegistrySnapshot {
  registry_version: string
  strategies: StrategyDefinition[]
  generated_at: string
}

export interface StrategyRuntimeState {
  schema_version: '1.0'
  strategy_id: string
  strategy_version: string
  environment: 'backtest' | 'shadow' | 'simulation' | 'live'
  lifecycle: 'unavailable' | 'stopped' | 'starting' | 'running' | 'pausing' | 'paused' | 'error'
  state_version: number
  config_version?: string | null
  last_transition_at?: string | null
  last_event_at?: string | null
  updated_at?: string | null
  blocking_reasons: string[]
  accepts_new_events: boolean
  can_emit_intents: boolean
  available_actions: Array<'pause' | 'resume' | 'start' | 'stop'>
  executable: false
}

export interface StrategyIntentLedgerItem {
  intent_id: string
  correlation_id: string
  config_id?: string | null
  config_version: string
  strategy_id: string
  symbol: string
  sleeve?: 'core' | 'swing' | null
  target_weight: number
  budget_weight?: number | null
  confidence: number
  reason: string
  occurred_at: string
  valid_until: string
  evidence_refs: string[]
  executable: false
}

export interface StrategyWorkbenchDetail {
  schema_version: '1.2'
  strategy: StrategyDefinition
  runtime?: StrategyRuntimeState | null
  execution_boundary?: QMTExecutionBoundaryStatus | null
  active_config_id?: string | null
  active_config_version?: string | null
  active_config_mode?: 'shadow' | 'simulation' | null
  simulation_promotion?: SimulationPromotionRecord | null
  simulation_mode_activation?: DirectionConfigActivationRecord | null
  configured: boolean
  configured_budget?: number | null
  configured_parameters: Record<string, number | string | boolean>
  disabled: boolean
  readiness?: ReleaseReadiness | null
  release_evidence_scope?: 'current_config' | 'historical_config' | 'absent' | 'unavailable'
  release_evidence_config_version?: string | null
  historical_release_gates?: ReleaseGateEvidence[]
  historical_performance_reports?: PerformanceReport[]
  performance_reports: PerformanceReport[]
  latest_shadow_acceptance?: ResonanceShadowAcceptanceSummary | null
  recent_intents?: StrategyIntentLedgerItem[]
  current_target?: {
    portfolio_target_id: string
    config_id: string
    config_version: string
    source_trade_date: string
    source_closed_at: string
    observed_at: string
    valid_until: string | null
    target_weights: Record<string, number>
    evidence_refs: string[]
    items: Array<{ symbol: string; target_weight: number; reason: string }>
    decision?: {
      status: 'evaluated' | 'initializing'
      rule_version: string
      model_state_method: 'causal_history_replay' | 'ledger_position_replay'
      history_start: string
      history_end: string
      history_batch_count: number
      required_dependencies: Array<'positions' | 'costs' | 'fills' | 'orders' | 'position_cycles'>
      execution_context_revision: string | null
    } | null
  } | null
  strategy_state?: {
    strategy_id: string; strategy_version: string; config_id: string | null; target_id: string | null
    status: 'evaluated' | 'recovering' | 'legacy_model'; reasons: string[]
    analysis_basis_date: string | null; analysis_known_at: string | null; analysis_close_prices: Record<string, number>
    exit_decision_dates?: Record<string, string>
    checkpoint: {
      evaluated_at: string; source_trade_date: string; analysis_revision: string; input_revision: string
      position_cycles: Record<string, { status: 'held' | 'flat' | 'unknown'; quantity: number; opened_at: string | null; coverage_start_at: string; blocking_reasons: string[] }>
      holding_days: Record<string, number>; reference_prices: Record<string, number>; target_weights: Record<string, number>
      model_signals: Record<string, string>; exit_paths: Record<string, string>
    } | null
  } | null
  last_successful_automation_loop_at?: string | null
  target_replacements?: {
    strategy_id: string; strategy_version: string; config_id: string; truncated: boolean
    items: Array<{
      event_id: string; episode_id: string; previous_revision: number; previous_target_revision: string
      previous_strategy_version: string; successor_target_id: string; successor_rule_version: string
      config_version: string; symbol: string; side: 'buy' | 'sell'; replaced_at: string
      evaluated_at: string; source_trade_date: string; target_weight: number
      observed_position_quantity: number; prior_state_available: boolean
      prior_blocking_reasons: string[]; prior_blocking_reason_labels: string[]; decision_input_refs: string[]
    }>
  } | null
  errors: Record<string, string>
  generated_at: string
  read_only: true
  executable: false
}

export interface ControlledSimulationIntentPreflight {
  schema_version: '1.0' | '1.1'
  strategy_id: string
  strategy_version: string
  generated_at: string
  state: 'unavailable' | 'blocked' | 'no_action' | 'ready_for_operator_review' | 'not_applicable'
  account_label?: string | null
  active_config_id?: string | null
  active_config_version?: string | null
  evidence_config_version?: string | null
  latest_batch_id?: string | null
  latest_batch_date?: string | null
  latest_outcome: 'not_evaluated' | 'no_change' | 'intents_emitted' | 'blocked'
  runtime_running: boolean
  agent_running: boolean
  account_reconciled: boolean
  agent_simulation_mode: boolean
  active_simulation_config: boolean
  promotion_lineage_bound: boolean
  mode_only_activation?: boolean
  release_evidence_ready: boolean
  strategy_evaluation_ready: boolean
  automation_disabled: boolean
  kill_switches_clear: boolean
  status_sources_available: boolean
  intent_identity_current: boolean
  transaction_boundary_ready: boolean
  expected_intent_count: number
  current_intent_count: number
  allocation?: PortfolioAllocationSnapshot | null
  review_artifact?: ControlledSimulationIntentReviewArtifact | null
  blockers: string[]
  transaction_blockers: string[]
  next_action: 'restore_authoritative_sources' | 'resolve_strategy_preflight'
    | 'wait_for_next_closed_daily_batch' | 'review_current_strategy_intents'
    | 'use_automatic_execution_status'
  automatic_approval_path_enabled: false
  operator_authorization_present: false
  approval_created: false
  command_created: false
  read_only: true
  executable: false
}

export interface ControlledSimulationIntentReviewItem {
  symbol: string
  intent_id: string
  sleeve: 'core' | 'swing'
  requested_weight: number
  applied_weight: number
  confidence: number
  occurred_at: string
  valid_until: string
  evidence_refs: string[]
}

export interface ControlledSimulationIntentReviewArtifact {
  schema_version: '1.0'
  generated_at: string
  strategy_id: string
  strategy_version: string
  account_label: string
  execution_mode: 'simulation'
  active_config_id: string
  active_config_version: string
  evidence_config_version: string
  dataset_version: string
  strategy_artifact_sha256: string
  promotion_id: string
  promotion_review_artifact_sha256: string
  promotion_review_input_sha256: string
  promotion_shadow_acceptance_sha256: string
  latest_batch_id: string
  latest_batch_date: string
  latest_batch_sha256: string
  intents: ControlledSimulationIntentReviewItem[]
  required_transaction_rechecks: string[]
  review_input_sha256: string
  human_approval_status: 'not_recorded'
  operator_authorization_present: false
  approval_created: false
  command_created: false
  read_only: true
  executable: false
}

export interface ControlledSimulationOrderPreviewItem {
  symbol: string
  intent_id: string
  sleeve: 'core' | 'swing'
  target_weight: number
  current_quantity: number
  available_quantity: number
  target_quantity: number
  delta_quantity: number
  side: 'buy' | 'sell' | 'none'
  lot_size: 100
  reference_price: number
  limit_price?: number | null
  quote_captured_at: string
}

export interface ControlledSimulationOrderPreview {
  schema_version: '1.1'
  generated_at: string
  state: 'unavailable' | 'blocked' | 'no_action' | 'ready_for_operator_review'
  agent_id: string
  account_label: string
  execution_mode: 'simulation'
  review_artifact_sha256: string
  review_input_sha256: string
  preview_input_sha256: string
  heartbeat_at?: string | null
  account_snapshot_at?: string | null
  review_age_seconds: number
  transaction_boundary_ready: boolean
  items: ControlledSimulationOrderPreviewItem[]
  blockers: string[]
  completed_rechecks: string[]
  pending_post_approval_rechecks: string[]
  automatic_approval_path_enabled: false
  operator_authorization_present: false
  approval_created: false
  command_created: false
  read_only: true
  executable: false
}

export interface ControlledSimulationOperatorReviewRequest {
  schema_version: '1.0'
  strategy_id: string
  strategy_version: string
  review_artifact_sha256: string
  preview_input_sha256: string
  reason: string
  idempotency_key: string
  confirmed: true
}

export interface ControlledSimulationOperatorReviewSummary {
  schema_version: '1.0'
  review_id: string
  strategy_id: string
  strategy_version: string
  agent_id: string
  account_label: string
  execution_mode: 'simulation'
  review_artifact_sha256: string
  preview_input_sha256: string
  reason: string
  item_count: number
  buy_item_count: number
  sell_item_count: number
  created_at: string
  state: 'reviewed_for_order_planning'
  creates_approved_orders: false
  creates_commands: false
  execution_authorized: false
  read_only: true
  executable: false
  contains_operator_session_id: false
  contains_request_sha256: false
}

export interface ControlledSimulationOperatorReviewReceipt {
  schema_version: '1.0'
  review: ControlledSimulationOperatorReviewSummary
  audit_event_id: string
  replayed: boolean
}

export interface ControlledSimulationExecutionAuthorizationRequest {
  schema_version: '1.0'
  strategy_id: string
  strategy_version: string
  review_id: string
  review_artifact_sha256: string
  preview_input_sha256: string
  reason: string
  idempotency_key: string
  confirmed: true
}

export interface ControlledSimulationExecutionAuthorizationSummary {
  schema_version: '1.0'
  authorization_id: string
  review_id: string
  strategy_id: string
  strategy_version: string
  agent_id: string
  account_label: string
  execution_mode: 'simulation'
  review_artifact_sha256: string
  preview_input_sha256: string
  reason: string
  approval_count: number
  created_at: string
  state: 'approved_for_bridge_recheck'
  creates_approved_orders: true
  creates_commands: false
  automatic_execution_enabled: false
  live_enabled: false
  bridge_recheck_required: true
  contains_account_id: false
  contains_operator_session_id: false
  contains_request_sha256: false
  contains_approval_ids: false
}

export interface ControlledSimulationExecutionAuthorizationReceipt {
  schema_version: '1.0'
  authorization: ControlledSimulationExecutionAuthorizationSummary
  audit_event_id: string
  replayed: boolean
}

export interface ControlledSimulationCommandBatchSummary {
  schema_version: '1.0'
  batch_id: string
  authorization_id: string
  strategy_id: string
  strategy_version: string
  agent_id: string
  account_label: string
  execution_mode: 'simulation'
  review_artifact_sha256: string
  preview_input_sha256: string
  reason: string
  command_count: number
  created_at: string
  state: 'commands_persisted_for_transport'
  creates_commands: true
  automatic_execution_enabled: false
  live_enabled: false
  bridge_rechecked: true
  current_cash_covers_all_buys: true
  current_risk_headroom_covers_all_buys: true
  contains_account_id: false
  contains_operator_session_id: false
  contains_request_sha256: false
  contains_approval_ids: false
  contains_command_ids: false
  contains_signatures: false
}

export interface ControlledSimulationExecutionSubmissionReceipt {
  schema_version: '1.0'
  authorization: ControlledSimulationExecutionAuthorizationSummary
  authorization_audit_event_id: string
  authorization_replayed: boolean
  batch: ControlledSimulationCommandBatchSummary
  batch_audit_event_id: string
  batch_replayed: boolean
}

export interface SimulationPromotionRecord {
  schema_version: '1.0'
  promotion_id: string
  source_config_id: string
  source_config_version: number
  target_config_id: string
  target_config_version: number
  strategy_id: 'resonance-regime-v1'
  strategy_version: '1.0.0'
  code_commit: string
  review_artifact_sha256: string
  review_input_sha256: string
  shadow_acceptance_sha256: string
  operator_ref: string
  reason: string
  occurred_at: string
  auto_execution_enabled: false
  live_activation_enabled: false
  rollback_mode: 'shadow'
  evidence_refs: string[]
}

export type StrategyControlAction = 'pause' | 'resume' | 'start' | 'stop'

export interface StrategyControlRequest {
  schema_version: '1.0'
  strategy_version: string
  environment: 'shadow'
  action: StrategyControlAction
  reason: string
  idempotency_key: string
  expected_state_version: number
  expected_config_version: string
  confirmed: true
}

export interface StrategyControlResult {
  schema_version: '1.0'
  action: StrategyControlAction
  accepted: boolean
  state: StrategyRuntimeState
  audit_event_id?: string | null
  reasons: string[]
  replayed: boolean
}

export interface OrderSummary {
  schema_version: '1.1'
  command_id: string
  correlation_id: string
  execution_mode: 'simulation' | 'live'
  trading_session?: 'continuous' | 'after_hours_fixed_price'
  strategy_id: string
  symbol: string
  side: 'buy' | 'sell' | 'cancel'
  quantity: number
  limit_price?: number | null
  status: 'pending' | 'received' | 'submitted' | 'partial_fill' | 'filled' | 'cancelled' | 'rejected' | 'failed' | 'expired' | 'duplicate' | 'error'
  created_at: string
  broker_order_id?: string | null
  execution_detail_available?: boolean
  filled_quantity?: number | null
  average_fill_price?: number | null
  latest_execution_at?: string | null
  rejection_reason?: string | null
}

export interface OrderLedgerPage {
  schema_version: '1.0'
  items: OrderSummary[]
  total: number
  limit: number
  offset: number
  has_more: boolean
  read_only: true
}

export interface OrderLedgerFilters {
  limit: number
  offset: number
  symbol?: string
  strategy_id?: string
  status?: OrderSummary['status']
  correlation_id?: string
  created_from?: string
  created_to?: string
}

export interface OrderExecutionTraceStage {
  stage: 'intent' | 'risk' | 'approval' | 'command' | 'qmt' | 'execution'
  status: 'pending' | 'accepted' | 'rejected' | 'completed' | 'unavailable'
  occurred_at?: string | null
  summary: string
  evidence_ref_count: number
}

export interface OrderExecutionTrace {
  schema_version: '1.0'
  correlation_id: string
  stages: OrderExecutionTraceStage[]
  complete: boolean
  read_only: true
}

export interface PerformanceValuationPoint {
  occurred_at: string
  net_asset_value: number
  cash: number
  market_value: number
  benchmark_value?: number | null
  evidence_refs: string[]
}

export interface PerformanceDrawdownPoint {
  occurred_at: string
  net_asset_value: number
  running_peak: number
  drawdown: number
}

export interface BacktestPerformanceReport extends Omit<PerformanceReport, 'valuation_started_at' | 'valuation_finished_at'> {
  report_id: string
  source_result_id: string
  source_result_hash: string
  period: '1m' | '5m' | '1d'
  model_version: string
  initial_capital: number
  final_net_asset_value: number
  sharpe_ratio?: number | null
  sortino_ratio?: number | null
  drawdown_peak_at?: string | null
  drawdown_trough_at?: string | null
  drawdown_recovered_at?: string | null
  realized_trade_count: number
  winning_trade_count: number
  win_rate?: number | null
  commission_total: number
  slippage_total: number
  benchmark_return?: number | null
  excess_return?: number | null
  valuation_points: PerformanceValuationPoint[]
  drawdown_curve: PerformanceDrawdownPoint[]
  evidence_refs: string[]
}

export interface BacktestMonthlyReturn {
  month: string
  started_at: string
  finished_at: string
  observation_count: number
  strategy_return: number
  benchmark_return?: number | null
}

export interface BacktestRollingMetric {
  occurred_at: string
  window_started_at: string
  observation_count: number
  strategy_return: number
  benchmark_return?: number | null
  annualized_volatility: number
  maximum_drawdown: number
}

export interface BacktestAnalyticsProjection {
  schema_version: '1.0'
  report_hash: string
  dataset_version: string
  period: '1m' | '5m' | '1d'
  rolling_window_observations: number
  monthly_returns: BacktestMonthlyReturn[]
  rolling_metric_source_count: number
  rolling_metrics_sampled: boolean
  rolling_metrics: BacktestRollingMetric[]
  analytics_sha256: string
  generated_at: string
  read_only: true
  executable: false
}

export interface BacktestTradeLedgerItem {
  sequence: number
  trade_id: string
  symbol: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  gross_value: number
  commission: number
  slippage_cost: number
  realized_pnl?: number | null
  occurred_at: string
  positions_after: Record<string, number>
}

export interface BacktestTradeLedgerPage {
  schema_version: '1.0'
  report_hash: string
  total: number
  limit: number
  offset: number
  items: BacktestTradeLedgerItem[]
  ledger_sha256: string
  generated_at: string
  read_only: true
  executable: false
}

export interface BacktestPositionEvolutionPoint {
  sequence: number
  occurred_at: string
  changed_symbol: string
  holding_count: number
  positions: Record<string, number>
}

export interface BacktestPositionEvolution {
  schema_version: '1.0'
  report_hash: string
  symbols: string[]
  source_trade_count: number
  sampled: boolean
  points: BacktestPositionEvolutionPoint[]
  evolution_sha256: string
  generated_at: string
  read_only: true
  executable: false
}

export interface BacktestDatasetManifest {
  dataset_id: string
  dataset_version: string
  object_ref: string
  sha256: string
  event_count: number
  frozen: boolean
  created_at: string
}

export interface BacktestJobSpec {
  schema_version: '1.0'
  job_kind: 'event_replay'
  dataset_version: string
  config_id: string
  config_version: string
  strategy_id: string
  strategy_version: string
  execution_environment: 'backtest'
  allow_live_external_calls: false
}

export interface BacktestJob {
  schema_version: '1.0'
  job_id: string
  spec: BacktestJobSpec
  request_sha256: string
  status: 'queued' | 'running' | 'stop_requested' | 'stopped' | 'succeeded' | 'failed'
  phase: 'queued' | 'loading' | 'verifying' | 'replaying' | 'persisting' | 'complete'
  total_events?: number | null
  processed_events: number
  stop_requested: boolean
  restart_count: number
  result_ref?: string | null
  result_hash?: string | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
  started_at?: string | null
  heartbeat_at?: string | null
  completed_at?: string | null
  evidence_refs: string[]
}

export interface BacktestJobCreateRequest extends BacktestJobSpec {
  reason: string
  idempotency_key: string
  confirmed: true
}

export interface BacktestJobStopRequest {
  schema_version: '1.0'
  reason: string
  idempotency_key: string
  expected_updated_at: string
  confirmed: true
}

export interface BacktestJobControlResult {
  schema_version: '1.0'
  job: BacktestJob
  audit_event_id: string
  replayed: boolean
}

export interface StrategyCapitalHistory {
  schema_version: 'strategy-capital-history-v1'
  strategy_id: string
  strategy_lineage_id: string
  genesis_epoch_id: string
  source_kind: 'strategy_capital_snapshots'
  calculation_method: 'return-on-contributed-principal-v1'
  /** Older servers omit this field and retain snapshots semantics. */
  sampling?: 'snapshots' | 'daily'
  window_start?: string | null
  window_end?: string | null
  points: Array<{ captured_at: string; valuation_at: string; strategy_version: string; net_asset_value: number; contributed_principal: number; capital_contributions_total: number; investment_pnl: number; status: 'ready' | 'blocked'; return_on_principal: number | null; drawdown: number | null }>
  truncated: boolean
  generated_at: string
  read_only: true
}
