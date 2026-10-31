import { readdir, readFile, stat } from 'node:fs/promises'
import { resolve } from 'node:path'

const distRoot = resolve(process.argv[2] ?? 'dist')
const manifestPath = resolve(distRoot, '.vite', 'manifest.json')
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'))
const entry = manifest['index.html']

if (!entry?.isEntry) {
  throw new Error('Console build manifest does not contain the index.html entry')
}

const expectedDynamicPages = ['src/workspace/MinuteWorkspace.tsx', 'src/workspace/AccountWorkspace.tsx', 'src/workspace/StrategyWorkspace.tsx', 'src/workspace/BacktestWorkspace.tsx', 'src/observation/ObservationShell.tsx']
// 回测由策略工作区按tab懒加载；沿实际入口依赖图核查直达与嵌套分块。
const actualDynamicPages = new Set()
const visited = new Set()
const pending = ['index.html']
while (pending.length > 0) {
  const key = pending.pop()
  if (visited.has(key)) continue
  visited.add(key)
  const chunk = manifest[key]
  if (!chunk) throw new Error(`Console chunk reference is missing: ${key}`)
  for (const target of chunk.dynamicImports ?? []) actualDynamicPages.add(target)
  pending.push(...(chunk.imports ?? []), ...(chunk.dynamicImports ?? []))
}
const missingPages = expectedDynamicPages.filter((page) => !actualDynamicPages.has(page))

if (missingPages.length > 0) {
  throw new Error(`独立业务页面分块缺失; missing dynamic pages: ${missingPages.join(', ')}`)
}

const entryBytes = (await stat(resolve(distRoot, entry.file))).size
const maxEntryBytes = 500 * 1024
if (entryBytes > maxEntryBytes) {
  throw new Error(`Console entry bundle is ${entryBytes} bytes; limit is ${maxEntryBytes} bytes`)
}

// 已接通工作区分别懒加载，图表库保持在分钟分块；其他页面按实际能力登记。
const minute = manifest['src/workspace/MinuteWorkspace.tsx']
if (!minute || (await stat(resolve(distRoot, minute.file))).size > 900 * 1024) {
  throw new Error('独立分钟页（含图表库）必须保持单独分块且低于900 KiB')
}

const assetFiles = await readdir(resolve(distRoot, 'assets'))
const sourceMaps = assetFiles.filter((file) => file.endsWith('.map'))
if (sourceMaps.length > 0) {
  throw new Error(`Console production image cannot contain source maps: ${sourceMaps.join(', ')}`)
}

console.log(
  `console chunks verified: entry=${(entryBytes / 1024).toFixed(1)} KiB, available_dynamic_pages=${expectedDynamicPages.length}, chart=minute_lazy_chunk`,
)
