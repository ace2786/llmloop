/**
 * 后端 A 区接口的数据结构。
 * 全部字段均与 http://127.0.0.1:8020/openapi.json 及实测响应逐一核对过。
 */

export type SplitName = 'optimize' | 'valid' | 'test'

/** 题目计数。后端在应用对象、列表响应、清空响应里都用这个结构。 */
export interface SplitCounts {
  optimize: number
  valid: number
  test: number
  total: number
}

export interface AuthResponse {
  user_id: number
  token: string
}

export interface Me {
  id: number
  email: string
  created_at: string
}

export interface AppItem {
  id: number
  user_id: number
  name: string
  /** 给被测应用接入用的密钥 */
  app_key: string
  base_url: string
  model: string
  description: string
  created_at: string
  questions: SplitCounts
}

export interface AppCreatePayload {
  name: string
  base_url: string
  model: string
  description: string
}

export interface Question {
  id: number
  app_id: number
  split: SplitName
  content: string
  reference: string
  created_at: string
}

/**
 * GET /apps/{id}/questions 的响应。
 * 注意：`total` 是该应用的**全部**题目数，不随 `split` 和 `q` 过滤；
 * 某一分类的题目数要看 `splits[split]`。
 */
export interface QuestionPage {
  total: number
  splits: SplitCounts
  /**
   * 当前 split + 关键词过滤后的条数。分页要用它。
   * 后端未升级时该字段为 undefined —— 此时不能用 `total` 冒充搜索结果。
   */
  matched?: number
  items: Question[]
}

/** DELETE /apps/{id}/questions/{question_id} 的响应，splits 是删除后的最新计数 */
export interface DeleteQuestionResult {
  deleted: number
  splits: SplitCounts
}

export interface ImportItem {
  content: string
  reference: string
}

export interface ImportPayload {
  items?: ImportItem[]
  raw_text?: string
  replace?: boolean
  seed?: number | null
}

export interface ImportResult {
  imported: number
  seed: number
  splits: SplitCounts
}
