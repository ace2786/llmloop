/** 优化循环页：看每次实验的起点、终点、每一轮提了什么、为什么保留或退回。 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  optApi,
  type OptConfig,
  type OptDecision,
  type OptRunBrief,
  type OptRunDetail,
} from '../api'
import { errorMessage } from '../api/client'

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`
}

function delta(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)} 点`
}

function cfgText(c: OptConfig | null): string {
  if (!c) return '—'
  return `topk=${c.topk} · ${c.use_rerank ? '重排' : '纯 BM25'} · ${c.prompt_style}`
}

const DECISION_LABEL: Record<OptDecision, string> = {
  kept: '保留',
  reverted: '退回',
  skipped: '跳过',
  error: '出错',
}

const DECISION_CLASS: Record<OptDecision, string> = {
  kept: 'pill pill-ok',
  reverted: 'pill pill-warn',
  skipped: 'pill pill-muted',
  error: 'pill pill-danger',
}

const STATUS_CLASS: Record<string, string> = {
  done: 'pill pill-done',
  running: 'pill pill-running',
  failed: 'pill pill-failed',
}

const STATUS_LABEL: Record<string, string> = {
  done: '已完成',
  running: '运行中',
  failed: '失败',
}

export default function LoopPage({ appId }: { appId: number }) {
  const [runs, setRuns] = useState<OptRunBrief[]>([])
  const [selected, setSelected] = useState<OptRunDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const d = await optApi.list(appId)
      setRuns(d.items)
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [appId])

  const pick = useCallback(async (runId: number) => {
    setLoadingDetail(true)
    try {
      const d = await optApi.detail(runId)
      setSelected(d)
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (runs.length > 0 && !selected) {
      // 优先选已经跑出轮次的实验——正在跑的那次点开是空的
      const target = runs.find((r) => r.rounds_done > 0) || runs[0]
      void pick(target.run_id)
    }
  }, [runs, selected, pick])

  const stats = useMemo(() => {
    const done = runs.filter((r) => r.status === 'done')
    const best = done.reduce<number | null>(
      (acc, r) => (r.best_score !== null && (acc === null || r.best_score > acc) ? r.best_score : acc),
      null,
    )
    const kept = done.reduce((n, r) => n + (r.best_score !== null && r.base_score !== null && r.best_score > r.base_score ? 1 : 0), 0)
    const rounds = done.reduce((n, r) => n + r.rounds_done, 0)
    return { total: runs.length, best, kept, rounds }
  }, [runs])

  // 当前选中的实验：快速筛选净省下的模型调用（拦下省 39/个，放行多花 30/个）
  const netSaved = useMemo(
    () => (selected?.rounds ?? []).reduce((n, r) => n + (r.calls_saved ?? 0), 0),
    [selected],
  )

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <h1 className="page-title">优化循环</h1>
          <p className="page-sub">
            五步闭环：<strong>评测 → 诊断 → 提议 → 验证 → 决策</strong>。
            循环由命令行触发（<span className="mono">scripts/loop_min.py</span>），这里看每次跑的结果。
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn" onClick={() => void load()} disabled={loading}>
            {loading ? '刷新中…' : '刷新'}
          </button>
        </div>
      </header>

      {err && <div className="notice notice-error">加载失败：{err}</div>}

      <section className="stat-row">
        <Stat label="实验次数" value={String(stats.total)} />
        <Stat label="最好成绩" value={pct(stats.best)} tone="primary" />
        <Stat label="有提升的" value={`${stats.kept} 次`} />
        <Stat label="累计轮数" value={`${stats.rounds} 轮`} />
      </section>

      <section className="card">
        <div className="card-head">
          <h2 className="card-title">实验列表</h2>
          <span className="card-hint">点一行看每一轮的细节</span>
        </div>

        {loading ? (
          <div className="empty-line">加载中…</div>
        ) : runs.length === 0 ? (
          <div className="empty-line">
            还没有优化实验。在终端跑一次：
            <span className="mono"> python scripts/loop_min.py --app {appId} --rounds 2</span>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>状态</th>
                <th>起点</th>
                <th>终点</th>
                <th>优化集</th>
                <th>验证集</th>
                <th>轮数</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.run_id}
                  onClick={() => void pick(r.run_id)}
                  style={{ cursor: 'pointer' }}
                  className={selected?.run_id === r.run_id ? 'row-active' : undefined}
                >
                  <td className="mono">{r.run_id}</td>
                  <td>
                    <span className={STATUS_CLASS[r.status] || 'pill pill-muted'}>
                      {STATUS_LABEL[r.status] || r.status}
                    </span>
                  </td>
                  <td className="mono">{pct(r.base_score)}</td>
                  <td className="mono">
                    <strong>{pct(r.best_score)}</strong>
                  </td>
                  <td className="mono">{r.best_valid === null ? '—' : pct(r.best_valid)}</td>
                  <td className="mono">
                    {r.rounds_done}/{r.rounds_planned}
                  </td>
                  <td className="mono">{r.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {loadingDetail && <div className="empty-line">加载实验详情…</div>}

      {selected && !loadingDetail && (
        <section className="card">
          <div className="card-head">
            <h2 className="card-title">实验 #{selected.run_id} 的每一轮</h2>
            <span className="card-hint">{selected.stop_reason || ''}</span>
          </div>

          <div className="loop-summary">
            <div>
              <span className="loop-k">起点</span>
              <span className="mono">{cfgText(selected.base_config)}</span>
              <span className="mono loop-strong">{pct(selected.base_score)}</span>
            </div>
            <div>
              <span className="loop-k">终点</span>
              <span className="mono">{cfgText(selected.best_config)}</span>
              <span className="mono loop-strong">{pct(selected.best_score)}</span>
            </div>
            {netSaved !== 0 && (
              <div>
                <span className="loop-k">快速筛选</span>
                <span className="mono">
                  净{netSaved > 0 ? '省' : '多花'} {Math.abs(netSaved)} 次模型调用
                </span>
              </div>
            )}
          </div>

          {selected.rounds.length === 0 ? (
            <div className="empty-line">这次实验还没跑完，没有轮次记录</div>
          ) : (
            selected.rounds.map((r) => (
              <div className="loop-round" key={r.round_no}>
                <div className="loop-round-head">
                  <span className="loop-round-no">第 {r.round_no} 轮</span>
                  <span className={DECISION_CLASS[r.decision]}>{DECISION_LABEL[r.decision]}</span>
                  <span className="mono loop-round-cfg">{cfgText(r.config)}</span>
                </div>

                {r.reason && (
                  <p className="loop-line">
                    <span className="loop-k">模型理由</span>
                    {r.reason}
                  </p>
                )}
                {r.expect && (
                  <p className="loop-line">
                    <span className="loop-k">预期修好</span>
                    {r.expect}
                  </p>
                )}
                {r.diagnosis && (
                  <p className="loop-line">
                    <span className="loop-k">诊断</span>
                    {r.diagnosis.n} 道错 {r.diagnosis.wrong}：检索没命中 {r.diagnosis.miss}、命中但没答对{' '}
                    {r.diagnosis.gen}（命中率 {pct(r.diagnosis.hit_rate)}）
                  </p>
                )}

                <div className="loop-scores">
                  <span>
                    优化集 <strong>{pct(r.opt_score)}</strong>
                    <em>{delta(r.opt_delta)}</em>
                  </span>
                  <span>
                    验证集 <strong>{pct(r.valid_score)}</strong>
                    <em>{delta(r.valid_delta)}</em>
                  </span>
                  {r.screen_score !== null && r.screen_score !== undefined && (
                    <span>
                      快速筛选 <strong>{pct(r.screen_score)}</strong>
                      <em>
                        {r.screened
                          ? `拦下，省 ${r.calls_saved ?? 0} 次调用`
                          : `放行（多花 ${Math.abs(r.calls_saved ?? 0)} 次）`}
                      </em>
                    </span>
                  )}
                  <span className="loop-note">{r.decision_note}</span>
                </div>
              </div>
            ))
          )}
        </section>
      )}

      <p className="page-note">
        循环一次要跑几百次模型调用（约 10 分钟），所以不在页面上触发。
        要跑新的实验，在终端执行 <span className="mono">scripts/loop_min.py</span>，跑完刷新这里。
      </p>
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'primary' }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={tone === 'primary' ? 'stat-value stat-primary' : 'stat-value'}>{value}</span>
    </div>
  )
}
