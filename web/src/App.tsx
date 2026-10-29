import { useEffect } from 'react'
import { AuthProvider, useAuth } from './auth'
import { navigate, useRoute } from './router'
import LoginPage from './pages/LoginPage'
import AppsPage from './pages/AppsPage'
import QuestionsPage from './pages/QuestionsPage'

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

  // 已登录却停在 /login（或根路径）时，直接送进应用列表
  useEffect(() => {
    if (phase !== 'ready') return
    if (route.name === 'login') navigate('/apps')
    else if (!window.location.hash || window.location.hash === '#/') navigate('/apps')
  }, [phase, route.name])

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
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="#/apps">
            <span className="brand-mark">LL</span>
            <span className="brand-name">LLMLoop</span>
            <span className="brand-sub">大模型应用自动调优平台</span>
          </a>

          <nav className="topnav">
            <a href="#/apps" className={route.name === 'apps' ? 'is-active' : ''}>
              应用接入
            </a>
            <span className={`topnav-item ${route.name === 'questions' ? 'is-active' : ''}`}>
              测试集管理
            </span>
          </nav>

          <div className="topbar-right">
            {me && <span className="user-email" title={me.email}>{me.email}</span>}
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                void logout()
              }}
            >
              退出登录
            </button>
          </div>
        </div>
      </header>

      <main className="main">
        {route.name === 'questions' ? (
          <QuestionsPage key={route.appId} appId={route.appId} />
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
  )
}
