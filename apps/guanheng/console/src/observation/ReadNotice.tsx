type ReadState = {
  data?: unknown
  dataUpdatedAt: number
  isError: boolean
  isFetching: boolean
  error: Error | null
  refetch: () => unknown
}

/** 状态说明与已有数据独立渲染，时间表示最近成功读取而非当前进程存活。 */
export function ReadNotice({ label, query }: { label: string; query: ReadState }) {
  if (!query.isError && !(query.isFetching && query.data !== undefined)) return null
  const previous = query.data !== undefined
  return <div className="observation-message" role="status">
    <p>{label}{query.isError ? `读取失败：${query.error?.message || '请稍后重试'}。` : '正在刷新。'}
      {previous ? <>当前保留上次读取结果；读取时间：<time dateTime={new Date(query.dataUpdatedAt).toISOString()}>{new Date(query.dataUpdatedAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}（北京时间）</time>。</> : '本次尚未取得结果。'}</p>
    {query.isError ? <button onClick={() => void query.refetch()}>重新读取{label}</button> : null}
  </div>
}
