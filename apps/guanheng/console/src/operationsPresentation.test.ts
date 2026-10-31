import { describe, expect, test } from 'vitest'

import {
  historyJobErrorLabel,
  operationalErrorStateLabel,
  operationIdLabel,
  operationPolicyLabel,
} from './operationsPresentation'
import { orderFailureReasonLabel } from './orderPresentation'

describe('operations presentation', () => {
  test('gives operation policies and native reads user-facing Chinese names', () => {
    expect(operationPolicyLabel('qmt.history.v1')).toBe('QMT 历史行情读取')
    expect(operationPolicyLabel('qmt.standard-read.v1')).toBe('QMT 标准只读调用')
    expect(operationIdLabel('market.market_data_ex')).toBe('扩展历史行情')
    expect(operationIdLabel('*')).toBe('全部标准只读操作')
  })

  test('translates the persisted history runner failure without hiding its exit code', () => {
    expect(historyJobErrorLabel('history_runner_failed', 'marketdata exited with code 2')).toBe(
      '历史行情运行器失败：行情数据进程退出，退出码 2',
    )
  })

  test('keeps unknown diagnostics auditable', () => {
    expect(historyJobErrorLabel('future_error', 'future message')).toBe(
      '未识别错误（future_error）：保留原始诊断 future message',
    )
    expect(operationIdLabel('future.operation')).toBe('未识别只读操作（future.operation）')
  })

  test('separates current errors, recovered history, and short startup-window bursts', () => {
    const now = Date.parse('2026-09-19T06:00:00Z')
    expect(operationalErrorStateLabel({
      firstEventAt: '2026-09-19T05:58:00Z', lastEventAt: '2026-09-19T05:59:00Z', serviceReady: true, now,
    })).toBe('仍在发生')
    expect(operationalErrorStateLabel({
      firstEventAt: '2026-09-19T01:00:00Z', lastEventAt: '2026-09-19T01:01:00Z', serviceReady: true, now,
    })).toBe('启动窗口/历史瞬时事件 · 服务已恢复')
    expect(operationalErrorStateLabel({
      firstEventAt: '2026-09-19T01:00:00Z', lastEventAt: '2026-09-19T02:00:00Z', serviceReady: true, now,
    })).toBe('已恢复')
  })
})

describe('order failure presentation', () => {
  test('translates the known m_bTrade route proof while preserving its meaning', () => {
    expect(orderFailureReasonLabel(
      'QMT strategy m_bTrade=0: signal recorded but no broker order routed; operator verified empty broker order view',
    )).toBe('QMT 策略处于 m_bTrade=0：只记录信号，未向柜台路由订单；操作员已确认柜台委托列表为空。')
  })

  test('retains an unknown broker reason for audit', () => {
    expect(orderFailureReasonLabel('future broker reason')).toBe(
      '柜台返回未识别原因（保留原文）：future broker reason',
    )
  })
})
