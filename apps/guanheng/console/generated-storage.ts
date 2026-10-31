import { resolve, relative, isAbsolute } from 'node:path'
import { fileURLToPath } from 'node:url'

const generatedRoot = fileURLToPath(new URL('./build/', import.meta.url))

/** 生成物由本应用拥有；拒绝越界目录，避免调用宿主或旧工程脚本。 */
export function generatedStoragePath(name: string, _portableDefault?: string): string {
  const target = resolve(generatedRoot, name)
  const suffix = relative(generatedRoot, target)
  if (suffix.startsWith('..') || isAbsolute(suffix)) throw new Error('生成物路径超出本应用目录')
  return target
}
