/**
 * 评测详情页：概览 + 逐题。
 *
 * 逐题点「详情」开右侧抽屉，不跳页 —— 参考阿里云百炼评测结果页的做法：
 * 表格里看结论，抽屉里看判分依据，不用来回跳。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { evalApi, type EvalCase, type EvalCasePage, type EvalRunDetail } from '../api'
import { errorMessage } from '../api/client'
import { navigate } from '../router'

const VERDICTS = ['', '对', '部分对', '错'] as const
const SOURCES = ['', 'real-issue', 'real-operation', 'real-param', 'real-supplement', 'doc-synth'] as const

function pct(v: number | null): string {
  return v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`
}

export default function EvalDetailPage({ runId }: { runId: number }) {
  const [detail, setDetail] = useState<EvalRunDetail | null>(null)
  const [cases, setCases] = useState<EvalCasePage | null>(null)
  const [tab, setTab] = useState<'overview' | 'cases'>('overview')
  const [verdict, setVerdict] = useState<string>('')
  const [source, setSource] = useState<string>('')
  const [page, setPage] = useState(1)
  const [err, setErr] = useState<string | null>(null)
  const [open, setOpen] = useState<EvalCase | null>(null)

  useEffect(() => {
    evalApi
      .detail(runId)
      .then(setDetail)
      .catch((e) => setErr(errorMessage(e)))
  }, [runId])

  const loadCases = useCallback(async () => {
    try {
      const r = await evalApi.cases(runId, {
        verdict: verdict || undefined,
        source: source || undefined,
        page,
        page_size: 50,
      })
      setCases(r)
    } catch (e) {
      setErr(errorMessage(e))
    }
  }, [runId, verdict, source, page])

  useEffect(() => {
    if (tab === 'cases') void loadCases()
  }, [tab, loadCases])

  const pages = useMemo(
    () => (cases ? Math.max(1, Math.ceil(cases.total / cases.page_size)) : 1),
    [cases],
  )

  if (err) return <div className="notice notice-error">加载失败：{err}</div>
  if (!detail) return <div className="empty-line">加载中…</div>

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <button type="button" className="link-back" onClick={() => navigate(`/apps/${detail.app_id}/evals`)}>
            ← 返回评测列表
          </button>
          <h1 className="page-title">评测 #{detail.run_id}</h1>
          <p className="page-sub">
            {detail.model} · {detail.split} 集 · 检索 top-{detail.topk} ·{' '}
            {detail.created_at?.replace('T', ' ').slice(0, 16)}
          </p>
        </div>
      </header>

      <div className="tabs">
        <button
          type="button"
          className={`tab${tab === 'overview' ? ' is-on' : ''}`}
          onClick={() => setTab('overview')}
        >
          概览
        </button>
        <button
          type="button"
          className={`tab${tab === 'cases' ? ' is-on' : ''}`}
          onClick={() => setTab('cases')}
        >
          逐题 {detail.total ? `(${detail.total})` : ''}
        </button>
      </div>

      {tab === 'overview' ? (
        <>
          <section className="stat-row">
            <Stat label="题数" value={String(detail.total)} />
            <Stat label="严格正确率" value={pct(detail.strict_acc)} tone />
            <Stat label="宽松正确率" value={pct(detail.loose_acc)} />
            <Stat
              label="耗时"
              value={detail.duration_sec ? `${detail.duration_sec.toFixed(0)} 秒` : '—'}
            />
          </section>

          <section className="card">
            <div className="card-head">
              <h2 className="card-title">判定分布</h2>
            </div>
            <table className="table">
              <tbody>
                <tr>
                  <td style={{ width: 120 }}>对</td>
                  <td className="mono">{detail.correct}</td>
                </tr>
                <tr>
                  <td>部分对</td>
                  <td className="mono">{detail.partial}</td>
                </tr>
                <tr>
                  <td>错</td>
                  <td className="mono">{detail.wrong}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section className="card">
            <div className="card-head">
              <h2 className="card-title">分来源</h2>
              <span className="card-hint">真实提问与文档反推分开看</span>
            </div>
            {Object.keys(detail.by_source).length === 0 ? (
              <div className="empty-line">暂无数据</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>来源</th>
                    <th style={{ width: 100 }}>题数</th>
                    <th style={{ width: 100 }}>答对</th>
                    <th style={{ width: 120 }}>严格正确率</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(detail.by_source).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td>{v.total}</td>
                      <td>{v.correct}</td>
                      <td>{v.total ? pct(v.correct / v.total) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      ) : (
        <>
          <div className="filter-row">
            <label>
              判定
              <select
                className="select"
                value={verdict}
                onChange={(e) => {
                  setVerdict(e.target.value)
                  setPage(1)
                }}
              >
                {VERDICTS.map((v) => (
                  <option key={v} value={v}>
                    {v || '全部'}
                  </option>
                ))}
              </select>
            </label>
            <label>
              来源
              <select
                className="select"
                value={source}
                onChange={(e) => {
                  setSource(e.target.value)
                  setPage(1)
                }}
              >
                {SOURCES.map((s) => (
                  <option key={s} value={s}>
                    {s || '全部'}
                  </option>
                ))}
              </select>
            </label>
            <span className="filter-count">
              共 {cases?.total ?? '—'} 条
            </span>
          </div>

          <section className="card">
            {!cases ? (
              <div className="empty-line">加载中…</div>
            ) : cases.items.length === 0 ? (
              <div className="empty-line">这个筛选条件下没有题目</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 90 }}>判定</th>
                    <th style={{ width: 130 }}>来源</th>
                    <th>问题</th>
                    <th style={{ width: 80 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.items.map((c) => (
                    <tr key={c.case_id}>
                      <td>
                        <span className={`pill pill-v-${c.verdict ?? 'none'}`}>{c.verdict ?? '—'}</span>
                      </td>
                      <td className="muted">{c.source ?? '—'}</td>
                      <td className="cell-clip">{c.question}</td>
                      <td>
                        <button type="button" className="btn btn-mini" onClick={() => setOpen(c)}>
                          详情
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {pages > 1 && (
              <div className="pager">
                <button
                  type="button"
                  className="btn btn-mini"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  上一页
                </button>
                <span>
                  {page} / {pages}
                </span>
                <button
                  type="button"
                  className="btn btn-mini"
                  disabled={page >= pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                </button>
              </div>
            )}
          </section>
        </>
      )}

      {open && (
        <>
          <button type="button" className="drawer-scrim" aria-label="关闭" onClick={() => setOpen(null)} />
          <aside className="drawer">
            <div className="drawer-head">
              <h2>第 {open.case_id} 条</h2>
              <button type="button" className="btn btn-mini" onClick={() => setOpen(null)}>
                关闭
              </button>
            </div>
            <div className="drawer-body">
              <Block title="问题">{open.question}</Block>
              <Block title="标准答案">{open.reference || '—'}</Block>
              <Block title="模型回答">{open.answer || '（空回答）'}</Block>
              <Block title="判分依据">{open.reason || '—'}</Block>
              <Block title="文档出处">{open.doc_location || '—'}</Block>
              <Block title="耗时">{open.latency_ms ? `${open.latency_ms} ms` : '—'}</Block>
            </div>
          </aside>
        </>
      )}
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: boolean }) {
  return (
    <div className={`stat${tone ? ' stat-primary' : ''}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="drawer-block">
      <div className="drawer-block-title">{title}</div>
      <div className="drawer-block-body">{children}</div>
    </div>
  )
}
