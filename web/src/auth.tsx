import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { ApiError, errorMessage, tokenStore } from './api/client'
import { authApi } from './api'
import type { Me } from './api/types'

type Phase =
  /** 没有 token，显示登录页 */
  | 'anon'
  /** 有 token，正在用 /auth/me 验证 */
  | 'checking'
  /** token 有效，me 已拿到 */
  | 'ready'
  /** 有 token 但连不上后端，无法验证 */
  | 'offline'

interface AuthValue {
  phase: Phase
  me: Me | null
  notice: string | null
  clearNotice: () => void
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  retry: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>(() => (tokenStore.get() ? 'checking' : 'anon'))
  const [me, setMe] = useState<Me | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  // 启动时用 /auth/me 校验 token。宁可多一次请求，也不要拿过期 token 装成已登录。
  useEffect(() => {
    if (!tokenStore.get()) {
      setPhase('anon')
      setMe(null)
      return
    }
    let cancelled = false
    setPhase('checking')
    authApi
      .me()
      .then((profile) => {
        if (cancelled) return
        setMe(profile)
        setPhase('ready')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          setMe(null)
          setPhase('anon')
          setNotice('登录已失效，请重新登录')
        } else {
          // 连不上后端：不能假装已登录，也不能假装没登录
          setPhase('offline')
        }
      })
    return () => {
      cancelled = true
    }
  }, [nonce])

  // 任何一次请求拿到 401，都退回登录页
  useEffect(() => {
    const onUnauthorized = () => {
      setMe(null)
      setPhase('anon')
      setNotice('登录已失效，请重新登录')
    }
    window.addEventListener('llmloop:unauthorized', onUnauthorized)
    return () => window.removeEventListener('llmloop:unauthorized', onUnauthorized)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login(email, password)
    tokenStore.set(res.token)
    const profile = await authApi.me()
    setMe(profile)
    setPhase('ready')
    setNotice(null)
  }, [])

  const register = useCallback(async (email: string, password: string) => {
    const res = await authApi.register(email, password)
    tokenStore.set(res.token)
    const profile = await authApi.me()
    setMe(profile)
    setPhase('ready')
    setNotice(null)
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // 后端已经失效也无所谓，本地照样清干净
    }
    tokenStore.clear()
    setMe(null)
    setPhase('anon')
    setNotice(null)
  }, [])

  const retry = useCallback(() => setNonce((n) => n + 1), [])
  const clearNotice = useCallback(() => setNotice(null), [])

  const value = useMemo<AuthValue>(
    () => ({ phase, me, notice, clearNotice, login, register, logout, retry }),
    [phase, me, notice, clearNotice, login, register, logout, retry],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}

/** 页面里统一用这个把异常转文案 */
export { errorMessage }
