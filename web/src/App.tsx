import { useCallback, useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './auth'
import { navigate, useRoute } from './router'
import { Sidebar } from './components/Sidebar'
import LoginPage from './pages/LoginPage'
import AppsPage from './pages/AppsPage'
import QuestionsPage from './pages/QuestionsPage'
import AssistantPage from './pages/AssistantPage'
import EvalsPage from './pages/EvalsPage'
import EvalDetailPage from './pages/EvalDetailPage'
import LoopPage from './pages/LoopPage'

const LAST_APP_KEY = 'llmloop.lastAppId'

function readLastAppId(): number | null {
  const raw = localStorage.getItem(LAST_APP_KEY)
  const n = raw ? Number(raw) : NaN
  return Number.isInteger(n) && n > 0 ? n : null
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  )
}

function Root() {
  const { phase, me, logout, retry } = useAuth()
  const route = useRoute()

  const [navOpen, setNavOpen] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [lastAppId, setLastAppId] = useState<number | null>(readLastAppId)

  // useRoute 每次渲染都返回新对象，依赖里只能用稳定的字符串
  const activeAppId =
    route.name === 'questions' ||
    route.name === 'assistant' ||
    route.name === 'evals' ||
    route.name === 'loop'
      ? route.appId
      : null
  const routeKey = activeAppId ? `questions:${activeAppId}` : route.name

  // 已登录却停在 /login（或根路径）时，直接送进应用列表
  useEffect(() => {
    if (phase !== 'ready') return
    if (route.name === 'login') navigate('/apps')
    else if (!window.location.hash || window.location.hash === '#/') navigate('/apps')
  }, [phase, route.name])

  // 记住最后打开的应用，侧边栏「题库」才有落点
  useEffect(() => {
    if (activeAppId === null) return
    localStorage.setItem(LAST_APP_KEY, String(activeAppId))
    setLastAppId(activeAppId)
  }, [activeAppId])

  // 抽屉里点了导航就自动收起
  useEffect(() => {
    setNavOpen(false)
  }, [routeKey])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 2600)
    return () => window.clearTimeout(timer)
  }, [toast])

  const showSoon = useCallback((text: string) => setToast(text), [])

  if (phase === 'checking') {
    return (
      <div className="fullscreen-state">
        <div className="spinner" />
        <p>正在校验登录状态…</p>
      </div>
    )
  }

  if (phase === 'offline') {
    return (
      <div className="fullscreen-state">
        <div className="state-icon state-icon-muted">!</div>
        <h2>连不上后端</h2>
        <p className="fullscreen-note">
          登录状态需要 <code>GET /auth/me</code> 确认，现在请求发不出去。
          <br />
          请先启动后端，再点重试。
        </p>
        <div className="fullscreen-actions">
          <button type="button" className="btn btn-primary" onClick={retry}>
            重试
          </button>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => {
              void logout()
            }}
          >
            退出登录
          </button>
        </div>
      </div>
    )
  }

  if (phase === 'anon') {
    return <LoginPage />
  }

  return (
    <div className="shell">
      <Sidebar
        route={route}
        email={me?.email ?? null}
        lastAppId={lastAppId}
        open={navOpen}
        onClose={() => setNavOpen(false)}
        onLogout={() => {
          setNavOpen(false)
          void logout()
        }}
        onSoon={showSoon}
      />

      {navOpen && (
        <button
          type="button"
          className="nav-scrim"
          aria-label="关闭导航"
          onClick={() => setNavOpen(false)}
        />
      )}

      <div className="content">
        <div className="mobile-bar">
          <button
            type="button"
            className="nav-toggle"
            aria-label="打开导航"
            aria-expanded={navOpen}
            onClick={() => setNavOpen(true)}
          >
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <span className="mobile-brand">LLMLoop</span>
        </div>

        <main className="main">
          {route.name === 'questions' ? (
            <QuestionsPage key={route.appId} appId={route.appId} />
          ) : route.name === 'assistant' ? (
            <AssistantPage key={route.appId} appId={route.appId} />
          ) : route.name === 'evals' ? (
            <EvalsPage key={route.appId} appId={route.appId} />
          ) : route.name === 'evalDetail' ? (
            <EvalDetailPage key={route.runId} runId={route.runId} />
          ) : route.name === 'loop' ? (
            <LoopPage key={route.appId} appId={route.appId} />
          ) : (
            <AppsPage />
          )}
        </main>

        <footer className="site-foot">
          <span>
            接口基地址 <code>{import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8020'}</code>
          </span>
          <span className="site-foot-dot">·</span>
          <span>页面数据全部来自后端实时请求</span>
        </footer>
      </div>

      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  )
}
