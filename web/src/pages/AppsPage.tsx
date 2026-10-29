import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import { appsApi } from '../api'
import type { AppItem } from '../api/types'
import { useAuth } from '../auth'
import { navigate } from '../router'
import { ConfirmDialog } from '../components/ConfirmDialog'
import {
  Banner,
  EmptyBlock,
  ErrorBlock,
  NotWired,
  Skeleton,
} from '../components/Feedback'

type LoadState = 'loading' | 'error' | 'ready'

const EMPTY_FORM = { name: '', base_url: '', model: '', description: '' }

export default function AppsPage() {
  const { me } = useAuth()

  const [apps, setApps] = useState<AppItem[] | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [loadError, setLoadError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [revealed, setRevealed] = useState<Record<number, boolean>>({})
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [flash, setFlash] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  const [pendingDelete, setPendingDelete] = useState<AppItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  // 列表永远来自 GET /apps，不做本地累加、不做缓存
  useEffect(() => {
    let cancelled = false
    setState('loading')
    setLoadError('')
    appsApi
      .list()
      .then((data) => {
        if (cancelled) return
        setApps(data)
        setState('ready')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setApps(null) // 关键：失败就清空，绝不留下上一次的数字
        setLoadError(errorMessage(err))
        setState('error')
      })
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const reload = useCallback(() => setReloadKey((k) => k + 1), [])

  const copyKey = useCallback(async (app: AppItem) => {
    const text = app.app_key
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text)
      } else {
        const ta = document.createElement('textarea')
        ta.value = text
        ta.setAttribute('readonly', '')
        ta.style.position = 'fixed'
        ta.style.top = '-1000px'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        const ok = document.execCommand('copy')
        document.body.removeChild(ta)
        if (!ok) throw new Error('copy failed')
      }
      setCopiedId(app.id)
      window.setTimeout(() => setCopiedId((cur) => (cur === app.id ? null : cur)), 1800)
    } catch {
      setFlash({ kind: 'error', text: '复制失败，请手动选中密钥复制' })
      setRevealed((prev) => ({ ...prev, [app.id]: true }))
    }
  }, [])

  const onCreate = async (e: FormEvent) => {
    e.preventDefault()
    setFormError(null)
    const name = form.name.trim()
    if (!name) {
      setFormError('应用名称不能为空')
      return
    }
    if (name.length > 64) {
      setFormError('应用名称最多 64 个字符')
      return
    }
    setCreating(true)
    try {
      const created = await appsApi.create({
        name,
        base_url: form.base_url.trim(),
        model: form.model.trim(),
        description: form.description.trim(),
      })
      setForm(EMPTY_FORM)
      setFormOpen(false)
      setFlash({ kind: 'success', text: `已接入「${created.name}」，请把 app_key 填进被测应用` })
      // 新建后自动展开密钥，省一次点击
      setRevealed((prev) => ({ ...prev, [created.id]: true }))
      reload()
    } catch (err) {
      setFormError(errorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const onDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await appsApi.remove(pendingDelete.id)
      setFlash({ kind: 'success', text: `已删除「${pendingDelete.name}」及其全部题目` })
      setPendingDelete(null)
      reload()
    } catch (err) {
      setFlash({ kind: 'error', text: errorMessage(err) })
      setPendingDelete(null)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">应用接入</h1>
          <p className="page-sub">
            把被测应用接进来，拿到 <code>app_key</code>，再给它准备测试题。
          </p>
        </div>
        <div className="page-head-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={reload}
            disabled={state === 'loading'}
          >
            刷新
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setFormOpen((v) => !v)
              setFormError(null)
            }}
          >
            {formOpen ? '收起表单' : '新建应用'}
          </button>
        </div>
      </div>

      {flash && (
        <Banner kind={flash.kind} onClose={() => setFlash(null)}>
          {flash.text}
        </Banner>
      )}

      {formOpen && (
        <section className="card form-card">
          <h2 className="card-title">新建应用</h2>
          <form className="grid-form" onSubmit={onCreate} noValidate>
            <label className="field">
              <span className="field-label">
                应用名称 <span className="req">*</span>
              </span>
              <input
                className="input"
                value={form.name}
                maxLength={64}
                placeholder="例如：LlamaFactory 文档助手"
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>

            <label className="field">
              <span className="field-label">
                接口地址 <span className="field-hint">OpenAI 兼容的 base_url</span>
              </span>
              <input
                className="input"
                value={form.base_url}
                placeholder="http://127.0.0.1:11434/v1"
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              />
            </label>

            <label className="field">
              <span className="field-label">
                模型名 <span className="field-hint">可选</span>
              </span>
              <input
                className="input"
                value={form.model}
                placeholder="qwen3-4b"
                onChange={(e) => setForm({ ...form, model: e.target.value })}
              />
            </label>

            <label className="field field-wide">
              <span className="field-label">
                备注 <span className="field-hint">可选</span>
              </span>
              <input
                className="input"
                value={form.description}
                placeholder="这套应用是干什么的"
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>

            {formError && (
              <div className="field-wide">
                <Banner kind="error">{formError}</Banner>
              </div>
            )}

            <div className="field-wide form-actions">
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => {
                  setFormOpen(false)
                  setForm(EMPTY_FORM)
                  setFormError(null)
                }}
                disabled={creating}
              >
                取消
              </button>
              <button type="submit" className="btn btn-primary" disabled={creating}>
                {creating ? '提交中…' : '创建应用'}
              </button>
            </div>
          </form>
        </section>
      )}

      {state === 'loading' && (
        <section className="card">
          <Skeleton rows={3} />
        </section>
      )}

      {state === 'error' && (
        <ErrorBlock
          title="拿不到应用列表"
          message={loadError}
          onRetry={reload}
          extra={
            <p className="state-note">
              页面上的所有数字都来自 <code>GET /apps</code>。后端不可用时这里不会有任何数据。
            </p>
          }
        />
      )}

      {state === 'ready' && apps && apps.length === 0 && (
        <EmptyBlock
          title="还没有接入任何应用"
          message="创建第一个应用，拿到 app_key 后就能导入测试题了。"
          action={
            <button type="button" className="btn btn-primary" onClick={() => setFormOpen(true)}>
              新建应用
            </button>
          }
        />
      )}

      {state === 'ready' && apps && apps.length > 0 && (
        <>
          <div className="list-meta">
            共 <strong>{apps.length}</strong> 个应用
            {me && <span className="list-meta-sub">账号 {me.email}</span>}
          </div>

          <div className="app-grid">
            {apps.map((app) => {
              const isRevealed = !!revealed[app.id]
              return (
                <article className="card app-card" key={app.id}>
                  <header className="app-card-head">
                    <div>
                      <h2 className="app-name">{app.name}</h2>
                      <div className="app-meta">
                        <span className="mono">{app.model || '未填模型'}</span>
                        <span className="sep">·</span>
                        <span className="mono ellipsis" title={app.base_url || '未填接口地址'}>
                          {app.base_url || '未填接口地址'}
                        </span>
                      </div>
                    </div>
                    <span className="chip chip-id">#{app.id}</span>
                  </header>

                  {app.description && <p className="app-desc">{app.description}</p>}

                  <div className="key-box">
                    <div className="key-label">
                      app_key
                      <span className="field-hint">给被测应用接入用</span>
                    </div>
                    <div className="key-row">
                      <code className={`key-value ${isRevealed ? '' : 'is-masked'}`}>
                        {isRevealed ? app.app_key : '•'.repeat(Math.min(28, app.app_key.length))}
                      </code>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() =>
                          setRevealed((prev) => ({ ...prev, [app.id]: !prev[app.id] }))
                        }
                      >
                        {isRevealed ? '隐藏' : '显示'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        onClick={() => copyKey(app)}
                      >
                        {copiedId === app.id ? '已复制' : '复制'}
                      </button>
                    </div>
                  </div>

                  <div className="counts">
                    <CountItem label="优化集" value={app.questions.optimize} tone="a" />
                    <CountItem label="验证集" value={app.questions.valid} tone="b" />
                    <CountItem label="测试集" value={app.questions.test} tone="c" />
                    <CountItem label="合计" value={app.questions.total} tone="d" />
                  </div>

                  <div className="app-created">创建于 {app.created_at}</div>

                  <footer className="app-foot">
                    <div className="app-actions">
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => navigate(`/apps/${app.id}/questions`)}
                      >
                        测试集管理
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-danger-ghost"
                        onClick={() => setPendingDelete(app)}
                      >
                        删除
                      </button>
                    </div>

                    <div className="app-pending">
                      <span className="app-pending-label">待接入</span>
                      <button
                        type="button"
                        className="btn btn-sm btn-disabled"
                        disabled
                        title="后端还没有 /apps/{id}/evaluate 接口"
                      >
                        发起评测 <NotWired />
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-disabled"
                        disabled
                        title="F1 引擎尚未接入"
                      >
                        优化循环 <NotWired />
                      </button>
                    </div>
                  </footer>
                </article>
              )
            })}
          </div>

          <p className="page-note">
            「发起评测」「优化循环」依赖后端 B 区接口（尚未排期），因此按钮置灰。
            页面不会用任何假数据填充这些区域。
          </p>
        </>
      )}

      <ConfirmDialog
        open={!!pendingDelete}
        title="删除应用"
        danger
        busy={deleting}
        confirmText="确认删除"
        onConfirm={onDelete}
        onCancel={() => setPendingDelete(null)}
      >
        {pendingDelete && (
          <>
            <p>
              将删除应用 <strong>{pendingDelete.name}</strong>，以及它名下的{' '}
              <strong>{pendingDelete.questions.total}</strong> 道题目。
            </p>
            <p className="modal-warn">此操作不可撤销。</p>
          </>
        )}
      </ConfirmDialog>
    </div>
  )
}

function CountItem({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`count-item count-${tone}`}>
      <div className="count-value">{value}</div>
      <div className="count-label">{label}</div>
    </div>
  )
}
