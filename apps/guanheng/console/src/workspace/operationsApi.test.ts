import { afterEach, expect, test, vi } from 'vitest'
import { fetchOperations } from './operationsApi'
import { operationsFixture } from './operations.fixture'
afterEach(() => vi.unstubAllGlobals())
test.each([
  { read_only: false }, { schema_version: 'old' }, { observed_at: 'unknown' },
  { telemetry: { ...operationsFixture.telemetry, received_ticks: -1 } },
  { telemetry: { ...operationsFixture.telemetry, received_at: 'not-a-time' } },
  { query: { ...operationsFixture.query, history_supported: 'yes' } },
  { collection: { ...operationsFixture.collection, pending: 'false' } },
])('拒绝失配的状态合同 %j', async (change) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...operationsFixture, ...change })))
  await expect(fetchOperations(new AbortController().signal)).rejects.toThrow('系统状态格式无效')
})
