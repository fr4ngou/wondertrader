type ReadState = {
  data?: unknown // 同一查询最近成功的结果；缺失表示尚未成功。
  dataUpdatedAt: number // 最近成功读取的 Unix 毫秒时间，展示为北京时间。
  isError: boolean // 当前轮次已失败；重试在途沿用失败提示。
  error: Error | null // 读取失败原因，缺失时使用通用提示。
  refetch: () => unknown // 用户主动发起同查询的下一轮读取。
}

/** 只在读取失败时提示；后台刷新沿用已有结果，避免横幅反复推挤页面。 */
export function ReadNotice({ label, query }: { label: string; query: ReadState }) {
  if (!query.isError) return null
  const previous = query.data !== undefined
  return <div className="observation-message" role="status">
    <p>{label}读取失败：{query.error?.message || '请稍后重试'}。
      {previous ? <>当前保留上次读取结果；读取时间：<time dateTime={new Date(query.dataUpdatedAt).toISOString()}>{new Date(query.dataUpdatedAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}（北京时间）</time>。</> : '本次尚未取得结果。'}</p>
    <button onClick={() => void query.refetch()}>重新读取{label}</button>
  </div>
}
