import { useState, type FormEvent } from 'react'
import { ApiError, NetworkError, errorMessage } from '../api/client'
import { useAuth } from '../auth'
import { navigate } from '../router'
import { Banner } from '../components/Feedback'

type Mode = 'login' | 'register'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function friendlyAuthError(err: unknown, mode: Mode): string {
  if (err instanceof NetworkError) return err.message
  if (err instanceof ApiError) {
    if (err.status === 401) return '邮箱或密码不正确'
    if (err.status === 409) return '该邮箱已注册，请直接登录'
    if (err.status === 400) {
      // 后端对短密码返回 "password must be >= 8 chars"
      if (/password/i.test(err.message)) return '密码至少 8 位'
      if (/email/i.test(err.message)) return '邮箱格式不正确'
      return err.message
    }
    return err.message
  }
  if (mode === 'register') return errorMessage(err)
  return errorMessage(err)
}

export default function LoginPage() {
  const { login, register, notice, clearNotice } = useAuth()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const switchMode = (next: Mode) => {
    setMode(next)
    setError(null)
    setConfirm('')
    clearNotice()
  }

  const fillDemo = () => {
    setEmail('tester@llmloop.dev')
    setPassword('pw12345678')
    setMode('login')
    setError(null)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    clearNotice()

    if (!EMAIL_RE.test(email.trim())) {
      setError('请输入有效的邮箱地址')
      return
    }
    if (password.length < 8) {
      setError('密码至少 8 位')
      return
    }
    if (mode === 'register' && password !== confirm) {
      setError('两次输入的密码不一致')
      return
    }

    setBusy(true)
    try {
      if (mode === 'login') {
        await login(email.trim(), password)
      } else {
        await register(email.trim(), password)
      }
      navigate('/apps')
    } catch (err) {
      setError(friendlyAuthError(err, mode))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-aside">
        <div className="auth-brand">
          <span className="brand-mark brand-mark-lg">LL</span>
          <div>
            <div className="auth-brand-name">LLMLoop</div>
            <div className="auth-brand-sub">大模型应用自动调优平台</div>
          </div>
        </div>
        <h1 className="auth-headline">
          设定质量目标，
          <br />
          让平台自己把应用调好。
        </h1>
        <ul className="auth-points">
          <li>
            <span className="dot" />
            接入你的 RAG 应用，拿到专属 <code>app_key</code>
          </li>
          <li>
            <span className="dot" />
            导入测试题，自动按 6:2:2 切成优化 / 验证 / 测试三份
          </li>
          <li>
            <span className="dot" />
            评测 → 找失败原因 → 提修改 → 在没见过的题上重测
          </li>
        </ul>
        <p className="auth-foot">
          当前版本已接入：登录注册、应用接入、测试集管理。
          <br />
          评测与优化循环尚未接入后端。
        </p>
      </div>

      <div className="auth-main">
        <div className="auth-card">
          <div className="auth-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'login'}
              className={`auth-tab ${mode === 'login' ? 'is-active' : ''}`}
              onClick={() => switchMode('login')}
            >
              登录
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'register'}
              className={`auth-tab ${mode === 'register' ? 'is-active' : ''}`}
              onClick={() => switchMode('register')}
            >
              注册
            </button>
          </div>

          {notice && (
            <Banner kind="warn" onClose={clearNotice}>
              {notice}
            </Banner>
          )}

          <form className="auth-form" onSubmit={onSubmit} noValidate>
            <label className="field">
              <span className="field-label">邮箱</span>
              <input
                type="email"
                className="input"
                value={email}
                autoComplete="username"
                placeholder="you@example.com"
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>

            <label className="field">
              <span className="field-label">
                密码
                <span className="field-hint">至少 8 位</span>
              </span>
              <div className="input-with-action">
                <input
                  type={showPw ? 'text' : 'password'}
                  className="input"
                  value={password}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  placeholder="••••••••"
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="input-action"
                  onClick={() => setShowPw((v) => !v)}
                  aria-label={showPw ? '隐藏密码' : '显示密码'}
                >
                  {showPw ? '隐藏' : '显示'}
                </button>
              </div>
            </label>

            {mode === 'register' && (
              <label className="field">
                <span className="field-label">确认密码</span>
                <input
                  type={showPw ? 'text' : 'password'}
                  className="input"
                  value={confirm}
                  autoComplete="new-password"
                  placeholder="再输入一次"
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </label>
            )}

            {error && <Banner kind="error">{error}</Banner>}

            <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
              {busy ? '请稍候…' : mode === 'login' ? '登录' : '注册并登录'}
            </button>
          </form>

          <div className="auth-demo">
            <span>联调测试账号</span>
            <button type="button" className="link-btn" onClick={fillDemo}>
              tester@llmloop.dev / pw12345678
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
