import { afterEach, expect, test, vi } from 'vitest'
import { fetchSourceMarketStatus } from './sourceMarketApi'
import { sourceMarketFixture } from './operations.fixture'

afterEach(() => vi.unstubAllGlobals())

test.each([{ read_only: false }, { schema_version: 'old' }, { data_qualification: 'qualified' },
  { observed_at: 'invalid' }, { process: { ...sourceMarketFixture.process, pending: 'false' } }])(
  '拒绝会混淆进程和来源资格的合同 %j', async change => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...sourceMarketFixture, ...change })))
    await expect(fetchSourceMarketStatus(new AbortController().signal)).rejects.toThrow('历史查询进程状态格式无效')
  },
)
