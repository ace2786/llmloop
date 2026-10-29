/**
 * 极薄的 fetch 封装。只有三件事：
 * 1. 拼 base url 和 query
 * 2. 自动带上 Authorization
 * 3. 把「网络不可达 / 401 / 业务错误」区分成不同的异常，让页面能分别处理
 *
 * 刻意不做任何缓存 —— 页面上每个数字都必须来自当次请求。
 */

export const API_BASE = (
  import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8020'
).replace(/\/+$/, '')

const TOKEN_KEY = 'llmloop.token'

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* 隐私模式下 localStorage 可能不可写，忽略即可 */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* noop */
    }
  },
}

/** 后端返回了非 2xx */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** 请求根本没发出去 / 连不上后端 */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'NetworkError'
  }
}

/** 把任意异常转成可以直接显示给用户的一句话 */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError || err instanceof NetworkError) return err.message
  if (err instanceof Error) return err.message
  return '未知错误'
}

type Query = Record<string, string | number | boolean | undefined | null>

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH'
  body?: unknown
  /** 默认 true；登录/注册要显式传 false */
  auth?: boolean
  query?: Query
  signal?: AbortSignal
}

function buildUrl(path: string, query?: Query): string {
  let url = API_BASE + path
  if (!query) return url
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === '') continue
    qs.set(k, String(v))
  }
  const s = qs.toString()
  if (s) url += (url.includes('?') ? '&' : '?') + s
  return url
}

/** FastAPI 的 detail 可能是字符串，也可能是校验错误数组 */
function extractDetail(data: unknown, status: number): string {
  if (typeof data === 'string' && data.trim()) return data
  if (data && typeof data === 'object') {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => (d && typeof d === 'object' ? (d as { msg?: unknown }).msg : null))
        .filter((m): m is string => typeof m === 'string' && !!m)
      if (msgs.length) return msgs.join('；')
    }
  }
  if (status === 400) return '请求参数有误'
  if (status === 401) return '未登录或登录已失效'
  if (status === 404) return '资源不存在，或不属于当前账号'
  if (status === 409) return '资源冲突'
  if (status === 422) return '参数格式不正确'
  return `请求失败（HTTP ${status}）`
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, query, signal } = opts

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = tokenStore.get()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  let res: Response
  try {
    res = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new NetworkError(
      `连不上后端 ${API_BASE}，请确认服务已启动（uvicorn server.main:app --port 8020）`,
    )
  }

  const raw = await res.text()
  let data: unknown = null
  if (raw) {
    try {
      data = JSON.parse(raw)
    } catch {
      data = raw
    }
  }

  if (res.status === 401) {
    tokenStore.clear()
    // 让外壳知道该退回登录页
    window.dispatchEvent(new Event('llmloop:unauthorized'))
    throw new ApiError(401, extractDetail(data, 401))
  }

  if (!res.ok) {
    throw new ApiError(res.status, extractDetail(data, res.status))
  }

  return data as T
}
