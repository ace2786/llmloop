/** 后端接口的语义化包装。页面只调这里，不直接拼路径。 */
import { request } from './client'
import type {
  AppCreatePayload,
  AppItem,
  AuthResponse,
  DeleteQuestionResult,
  ImportPayload,
  ImportResult,
  Me,
  QuestionPage,
  SplitCounts,
  SplitName,
} from './types'

export const authApi = {
  login: (email: string, password: string) =>
    request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    }),

  register: (email: string, password: string) =>
    request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: { email, password },
      auth: false,
    }),

  me: () => request<Me>('/auth/me'),

  logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
}

export const appsApi = {
  list: () => request<AppItem[]>('/apps'),

  get: (appId: number) => request<AppItem>(`/apps/${appId}`),

  create: (payload: AppCreatePayload) =>
    request<AppItem>('/apps', { method: 'POST', body: payload }),

  remove: (appId: number) =>
    request<{ deleted: number }>(`/apps/${appId}`, { method: 'DELETE' }),
}

export const questionsApi = {
  /**
   * total / splits 都是全量统计，不随 q 变化；
   * 过滤后的条数看返回里的 matched。
   */
  list: (
    appId: number,
    params: { split?: SplitName; q?: string; limit?: number; offset?: number },
  ) => request<QuestionPage>(`/apps/${appId}/questions`, { query: params }),

  stats: (appId: number) => request<SplitCounts>(`/apps/${appId}/questions/stats`),

  import: (appId: number, payload: ImportPayload) =>
    request<ImportResult>(`/apps/${appId}/questions/import`, {
      method: 'POST',
      body: payload,
    }),

  /** 不传 split 就是清空全部 */
  clear: (appId: number, split?: SplitName) =>
    request<SplitCounts>(`/apps/${appId}/questions`, {
      method: 'DELETE',
      query: split ? { split } : undefined,
    }),

  /** 删单题。返回里带最新 splits，前端不必再请求 /stats */
  remove: (appId: number, questionId: number) =>
    request<DeleteQuestionResult>(`/apps/${appId}/questions/${questionId}`, {
      method: 'DELETE',
    }),
}

// ---------------------------------------------------------------- 助手（被测应用）

export interface ChatReference {
  path: string
  heading: string
  snippet: string
  score: number
}

export interface ChatReply {
  message_id: number
  answer: string
  references: ChatReference[]
  latency_ms: number
}

export type ChatRating = 'useful' | 'useless' | 'wrong'

export const chatApi = {
  ask: (appId: number, question: string, topk = 3) =>
    request<ChatReply>(`/apps/${appId}/chat`, {
      method: 'POST',
      body: { question, topk },
    }),

  feedback: (messageId: number, rating: ChatRating, comment = '') =>
    request<{ ok: boolean; message_id: number; rating: string }>(
      `/chat/${messageId}/feedback`,
      { method: 'POST', body: { rating, comment } },
    ),
}

// ---------------------------------------------------------------- 评测

export type EvalStatus = 'pending' | 'running' | 'done' | 'failed' | 'canceled'

export interface EvalRunBrief {
  run_id: number
  model: string
  split: string
  status: EvalStatus
  total: number
  strict_acc: number | null
  loose_acc: number | null
  duration_sec: number | null
  created_at: string
  error?: string | null
}

export interface EvalRunDetail extends EvalRunBrief {
  app_id: number
  topk: number
  correct: number
  partial: number
  wrong: number
  finished_at: string | null
  by_source: Record<string, { total: number; correct: number }>
}

export interface EvalCase {
  case_id: number
  question: string
  reference: string | null
  answer: string | null
  verdict: '对' | '部分对' | '错' | null
  reason: string | null
  source: string | null
  doc_location: string | null
  latency_ms: number | null
}

export interface EvalCasePage {
  total: number
  page: number
  page_size: number
  items: EvalCase[]
}

export const evalApi = {
  start: (appId: number, body: { model?: string; split?: string; topk?: number }) =>
    request<{ run_id: number; status: string }>(`/apps/${appId}/eval`, {
      method: 'POST',
      body,
    }),

  list: (appId: number, limit = 20) =>
    request<{ items: EvalRunBrief[] }>(`/apps/${appId}/evals`, { query: { limit } }),

  detail: (runId: number) => request<EvalRunDetail>(`/evals/${runId}`),

  cases: (
    runId: number,
    params: { verdict?: string; source?: string; page?: number; page_size?: number } = {},
  ) => request<EvalCasePage>(`/evals/${runId}/cases`, { query: params }),
}
