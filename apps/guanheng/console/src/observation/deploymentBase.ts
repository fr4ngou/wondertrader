/** One canonical prefix for assets, browser routing and same-origin API calls. */
export function observationBase(raw = ''): string {
  const value=raw.trim().replace(/\/+$/,'')
  if(value && !/^\/[a-zA-Z0-9_-]+$/.test(value))throw new Error('观察部署前缀须为一个站内路径')
  return value
}
