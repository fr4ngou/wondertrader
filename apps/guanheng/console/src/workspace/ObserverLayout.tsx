import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Activity, BarChart3, CandlestickChart, Circle, LayoutDashboard, Lightbulb, ReceiptText, ServerCog, UserRound } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import brand from '../../config/project-branding.json'
import './observer-theme.css'
import { SecurityAutocomplete } from './SecurityAutocomplete'

const destinations = [
  { id: 'dashboard', label: '总览', icon: LayoutDashboard },
  { id: 'market', label: '行情', icon: CandlestickChart },
  { id: 'observation', label: '市场观察', icon: Activity },
  { id: 'strategies', label: '策略', icon: Lightbulb },
  { id: 'account', label: '账户', icon: UserRound },
  { id: 'orders', label: '交易记录', icon: ReceiptText },
  { id: 'operations', label: '系统状态', icon: ServerCog },
] as const

function chinaDate(now: Date) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'long',
  }).format(now)
}

/** 统一只读工作区外壳；连接标识仅代表观衡接口，账户/行情状态由各页事实说明。 */
export function ObserverLayout({ children, connected, failed = false }: {
  children: ReactNode; connected: boolean; failed?: boolean
}) {
  const [today, setToday] = useState(() => new Date())
  const location = useLocation()
  const navigate = useNavigate()
  const observation = location.pathname === '/observation' || location.pathname.startsWith('/observation/')
  // ObservationShell保留自己的主内容地标，其余独立页面由统一外壳提供main。
  const Content = observation ? 'div' : 'main'
  useEffect(() => {
    const timer = window.setInterval(() => setToday(new Date()), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  return <div className={`app-shell independent-shell observer-design${observation ? ' observer-design-observation' : ''}`}>
    <a className="skip-link" href="#workspace-content">跳到主要内容</a>
    <aside className="sidebar" aria-label="工作区侧边栏">
      <NavLink className="brand-lockup" to="/dashboard" aria-label={brand.display_name}>
        <strong>{brand.short_name}</strong><span>量化观察平台</span>
      </NavLink>
      <nav aria-label="主要工作区">{destinations.map(({ id, label, icon: Icon }) =>
        <NavLink key={id} to={`/${id}`} className={({ isActive }) => isActive ? 'nav-item nav-item-active' : 'nav-item'}>
          <Icon size={18} strokeWidth={1.7} aria-hidden="true" /><span>{label}</span>
        </NavLink>)}
      </nav>
      <div className="sidebar-footer"><BarChart3 size={15} aria-hidden="true" /><span>观衡 · 数据与策略观察</span></div>
    </aside>
    <header className="topbar">
      <SecurityAutocomplete onSelect={term => navigate(`/market?${new URLSearchParams({ search: term })}`)} />
      <div className="observer-header-meta">
        <span className={`observer-service-state${failed ? ' observer-service-warning' : ''}`} role="status" title="表示观衡接口的读取状态；具体账户和行情时间见对应页面。">
          <Circle size={8} fill="currentColor" aria-hidden="true" />{failed ? connected ? '刷新待重试' : '连接待恢复' : connected ? '服务在线' : '正在连接'}
        </span>
        <span className="observer-mode">只读</span>
        <time dateTime={today.toISOString()}>{chinaDate(today)}</time>
      </div>
    </header>
    <Content className="workspace-main" id="workspace-content" tabIndex={-1}>
      {observation ? <header className="observer-section-heading"><h1>市场观察</h1></header> : null}
      {children}
    </Content>
  </div>
}
