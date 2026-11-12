import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { ObserverLayout } from './ObserverLayout'
import { ObserverThemeProvider } from './ObserverTheme'
import { observerThemeKey } from './observerAppearance'

afterEach(() => {
  cleanup()
  window.localStorage.removeItem(observerThemeKey)
  delete document.documentElement.dataset.observerTheme
})

function Location() {
  const location = useLocation()
  return <output aria-label="搜索目的地">{location.pathname + location.search}</output>
}

test('全局搜索携带原查询词进入行情，保留中文和代码前缀', () => {
  render(<MemoryRouter initialEntries={['/account']}>
    <ObserverLayout connected><Location /></ObserverLayout>
  </MemoryRouter>)
  const input = screen.getByRole('combobox', { name: '全局证券搜索' })
  fireEvent.change(input, { target: { value: ' 68817 ' } })
  fireEvent.submit(screen.getByRole('search', { name: '证券搜索' }))
  expect(screen.getByLabelText('搜索目的地')).toHaveTextContent('/market?search=68817')
  fireEvent.change(input, { target: { value: '中际旭创' } })
  fireEvent.submit(screen.getByRole('search', { name: '证券搜索' }))
  expect(screen.getByLabelText('搜索目的地')).toHaveTextContent('/market?search=%E4%B8%AD%E9%99%85%E6%97%AD%E5%88%9B')
})

test('服务刷新失败保留当前工作区和完整导航，状态说明不冒充行情或账户在线', () => {
  render(<MemoryRouter initialEntries={['/account']}>
    <ObserverLayout connected failed><h1>账户</h1><p>已读取的账户结果</p></ObserverLayout>
  </MemoryRouter>)
  expect(screen.getByRole('status')).toHaveTextContent('刷新待重试')
  expect(screen.getByRole('heading', { name: '账户' })).toBeVisible()
  expect(screen.getByText('已读取的账户结果')).toBeVisible()
  expect(screen.getByRole('link', { name: '账户' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('navigation', { name: '主要工作区' }).querySelectorAll('a')).toHaveLength(8)
})

test('可切换三套主题并恢复保存的外观，无效存储值回到白色', () => {
  const workspace = <MemoryRouter><ObserverThemeProvider><ObserverLayout connected>工作区</ObserverLayout></ObserverThemeProvider></MemoryRouter>
  window.localStorage.setItem(observerThemeKey, 'unknown')
  const mounted = render(workspace)
  expect(screen.getByRole('button', { name: '白色', pressed: true })).toBeVisible()
  for (const [name, theme] of [['护眼黄', 'yellow'], ['黑色', 'black'], ['白色', 'white'], ['护眼黄', 'yellow']]) {
    fireEvent.click(screen.getByRole('button', { name }))
    expect(screen.getByRole('button', { name, pressed: true })).toBeVisible()
    expect(document.documentElement).toHaveAttribute('data-observer-theme', theme)
    expect(window.localStorage.getItem(observerThemeKey)).toBe(theme)
  }
  mounted.unmount()
  render(workspace)
  expect(screen.getByRole('button', { name: '护眼黄', pressed: true })).toBeVisible()
})
