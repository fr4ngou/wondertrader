import { beforeAll, describe, expect, it } from 'vitest'

import {
  operationalAlertPresentation,
  operationalAlertTitle,
  operationalAlertValue,
} from './operationalAlertPresentation'
import { installProblemDictionary } from './problemDictionary'

beforeAll(() => installProblemDictionary({
  schema_version: '1.0', definitions: [],
  alert_category_labels: {
    quote_stale: '行情报价过期', causal_accumulation: '因果样本积累',
    market_bar_collection: '行情采集',
    observability_stack_unavailable: '监控证据不可用',
  },
  alert_source_labels: { 'qmt-agent': 'AI_ETF 执行代理', minio_persistence: 'MinIO 持久化写入检查' },
  alert_titles: {
    'qmt:quote': 'QMT 实时报价新鲜度', 'market-bars:1m': '1 分钟行情采集状态',
    'observability:minio_persistence': 'MinIO 持久化写入尚未验证',
  },
  alert_value_labels: {
    'enabled,running,error-free': '启用、运行且无错误', unavailable: '不可用', verified: '已验证',
  },
}))

describe('operational alert presentation', () => {
  it('turns QMT quote freshness into a readable Chinese alert', () => {
    expect(operationalAlertPresentation({
      alert_key: 'qmt:quote',
      category: 'quote_stale',
      severity: 'warning',
      source: 'qmt-agent',
      active: true,
      observed_value: 113148.78,
      threshold: 15,
    })).toMatchObject({
      title: 'QMT 实时报价新鲜度',
      category: '行情报价过期',
      source: 'AI_ETF 执行代理',
      observed: '1.3 天',
      threshold: '15 秒',
      rawKey: 'qmt:quote',
    })
  })

  it('translates current causal and market worker values', () => {
    expect(operationalAlertValue(
      'enabled,running,error-free',
      'market_bar_collection',
    )).toBe('启用、运行且无错误')
    expect(operationalAlertTitle({
      alert_key: 'market-bars:1m',
      category: 'market_bar_collection',
    })).toBe('1 分钟行情采集状态')
  })

  it('keeps an auditable fallback for unknown alert codes', () => {
    expect(operationalAlertTitle({
      alert_key: 'future:unknown',
      category: 'future_category',
    })).toBe('未翻译类别：future_category告警')
  })

  

  it('translates observability checks and expected values', () => {
    expect(operationalAlertPresentation({
      alert_key: 'observability:minio_persistence',
      category: 'observability_stack_unavailable',
      severity: 'warning',
      source: 'minio_persistence',
      active: true,
      observed_value: 'unavailable',
      threshold: 'verified',
    })).toMatchObject({
      title: 'MinIO 持久化写入尚未验证',
      category: '监控证据不可用',
      source: 'MinIO 持久化写入检查',
      observed: '不可用',
      threshold: '已验证',
    })
  })
})
