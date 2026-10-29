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
