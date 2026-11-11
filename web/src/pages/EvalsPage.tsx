/**
 * 评测列表页：发起评测 + 看历史。
 *
 * 页面上每个数字都来自 /apps/{id}/evals 和 /evals/{run_id}，没有任何写死值。
 * 有任务在跑时每 2 秒轮询一次，跑完自动停。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { evalApi, type EvalRunBrief, type EvalStatus } from '../api'
import { errorMessage } from '../api/client'
import { navigate } from '../router'

const MODELS = [
  { value: 'qwen3-4b-local', label: 'Qwen3-4B（本地）' },
  { value: 'glm-4-flash', label: 'GLM-4-Flash（云端免费）' },
]

const STATUS_LABEL: Record<EvalStatus, string> = {
  pending: '排队中',
  running: '运行中',
  done: '完成',
  failed: '失败',
  canceled: '已终止',
}

function pct(v: number | null): string {
  return v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`
}

export default function EvalsPage({ appId }: { appId: number }) {
  const [runs, setRuns] = useState<EvalRunBrief[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [model, setModel] = useState(MODELS[0].value)
  const [notice, setNotice] = useState<string | null>(null)
  const timer = useRef<number | null>(null)

  const load = useCallback(async () => {
    try {
      const r = await evalApi.list(appId, 20)
      setRuns(r.items)
      setErr(null)
      return r.items
    } catch (e) {
      setErr(errorMessage(e))
      return []
    } finally {
      setLoading(false)
    }
  }, [appId])

  // 首次加载 + 有任务在跑时轮询
  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const active = runs.some((r) => r.status === 'pending' || r.status === 'running')
    if (timer.current) {
      window.clearTimeout(timer.current)
      timer.current = null
    }
    if (!active) return
    timer.current = window.setTimeout(() => void load(), 2000)
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [runs, load])

  const latest = useMemo(
    () => runs.find((r) => r.status === 'done') ?? runs[0],
    [runs],
  )

  const start = useCallback(async () => {
    setStarting(true)
    setNotice(null)
    try {
      const r = await evalApi.start(appId, { model, split: 'test', topk: 3 })
      setNotice(`已发起评测 #${r.run_id}，约 1 分钟`)
      await load()
    } catch (e) {
      setNotice(errorMessage(e))
    } finally {
      setStarting(false)
    }
  }, [appId, model, load])

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <h1 className="page-title">评测</h1>
          <p className="page-sub">
            在<strong>锁住的最终测试集</strong>上跑一次，结果逐题落库，可点开查看判分依据。
          </p>
        </div>
        <div className="page-actions">
          <select
            className="select"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={starting}
          >
            {MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-primary" onClick={() => void start()} disabled={starting}>
            {starting ? '发起中…' : '发起评测'}
          </button>
        </div>
      </header>

      {notice && <div className="notice">{notice}</div>}
      {err && <div className="notice notice-error">加载失败：{err}</div>}

      <section className="stat-row">
        <Stat label="题数" value={latest ? String(latest.total || '—') : '—'} />
        <Stat label="严格正确率" value={pct(latest?.strict_acc ?? null)} tone="primary" />
        <Stat label="宽松正确率" value={pct(latest?.loose_acc ?? null)} />
        <Stat
          label="耗时"
          value={latest?.duration_sec ? `${latest.duration_sec.toFixed(0)} 秒` : '—'}
        />
      </section>

      <section className="card">
        <div className="card-head">
          <h2 className="card-title">历史评测</h2>
          <span className="card-hint">最近 20 次</span>
        </div>

        {loading ? (
          <div className="empty-line">加载中…</div>
        ) : runs.length === 0 ? (
          <div className="empty-line">还没有评测记录，点右上角「发起评测」</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 90 }}>状态</th>
                <th>模型</th>
                <th style={{ width: 70 }}>题数</th>
                <th style={{ width: 100 }}>严格</th>
                <th style={{ width: 100 }}>宽松</th>
                <th style={{ width: 150 }}>时间</th>
                <th style={{ width: 80 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id}>
                  <td>
                    <span className={`pill pill-${r.status}`}>{STATUS_LABEL[r.status]}</span>
                  </td>
                  <td className="mono">{r.model}</td>
                  <td>{r.total || '—'}</td>
                  <td>{pct(r.strict_acc)}</td>
                  <td>{pct(r.loose_acc)}</td>
                  <td className="muted">{r.created_at?.replace('T', ' ').slice(5, 16)}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-mini"
                      onClick={() => navigate(`/evals/${r.run_id}`)}
                    >
                      查看
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'primary' }) {
  return (
    <div className={`stat${tone ? ' stat-' + tone : ''}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
