import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, errorMessage } from '../api/client'
import { appsApi, questionsApi } from '../api'
import type {
  AppItem,
  ImportItem,
  ImportResult,
  Question,
  QuestionPage,
  SplitCounts,
  SplitName,
} from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import {
  Banner,
  EmptyBlock,
  ErrorBlock,
  NotWired,
  Skeleton,
} from '../components/Feedback'

type SplitTab = 'all' | SplitName

const SPLIT_LABEL: Record<SplitName, string> = {
  optimize: '优化集',
  valid: '验证集',
  test: '测试集',
}

const SPLIT_HINT: Record<SplitName, string> = {
  optimize: '用于诊断和提出修改',
  valid: '用于判断改动是否真的变好',
  test: '从未参与优化，用来验收',
}

const TABS: { key: SplitTab; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'optimize', label: '优化集' },
  { key: 'valid', label: '验证集' },
  { key: 'test', label: '测试集' },
]

const PAGE_SIZES = [10, 20, 50]

/**
 * 把粘贴的文本解析成 items。
 * 后端 raw_text 只按换行切、不认 Tab 分隔的出处，所以这里自己解析，
 * 再走 items 形式提交（后端对 items 的 {content, reference} 支持是实测过的）。
 * 这一步只是「输入解析」，切分比例仍由后端计算。
 */
function parsePasted(text: string): ImportItem[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      const tab = line.indexOf('\t')
      if (tab >= 0) {
        return { content: line.slice(0, tab).trim(), reference: line.slice(tab + 1).trim() }
      }
      return { content: line, reference: '' }
    })
    .filter((item) => item.content.length > 0)
}

function splitTotalOf(counts: SplitCounts, tab: SplitTab): number {
  return tab === 'all' ? counts.total : counts[tab]
}

/** 删单题失败时的文案：把「接口还没上」和「这题已经不在了」区分开 */
function deleteErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 404) {
    if (err.message === 'Not Found') return '后端还没有单题删除接口'
    if (err.message === 'question not found') return '这道题已经不存在了，刷新看看'
  }
  return errorMessage(err)
}

export default function QuestionsPage({ appId }: { appId: number }) {
  // ---- 应用信息 ----
  const [app, setApp] = useState<AppItem | null>(null)
  const [appError, setAppError] = useState('')

  // ---- 题目列表 ----
  const [split, setSplit] = useState<SplitTab>('all')
  const [limit, setLimit] = useState(10)
  const [page, setPage] = useState(0)
  const [data, setData] = useState<QuestionPage | null>(null)
  const [listState, setListState] = useState<'loading' | 'error' | 'ready'>('loading')
  const [listError, setListError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  /** 静默重取：删除后同步分页，但不闪骨架屏 */
  const silentRef = useRef(false)

  // ---- 搜索 ----
  const [searchInput, setSearchInput] = useState('')
  /** 防抖后真正发给后端的词 */
  const [query, setQuery] = useState('')

  // ---- 删除单题 ----
  const [pendingDelete, setPendingDelete] = useState<Question | null>(null)
  const [deletingQuestion, setDeletingQuestion] = useState(false)

  // ---- 导入 ----
  const [rawText, setRawText] = useState('')
  const [seedText, setSeedText] = useState('')
  const [replace, setReplace] = useState(true)
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)

  // ---- 清空 ----
  const [clearTarget, setClearTarget] = useState<SplitTab | null>(null)
  const [clearing, setClearing] = useState(false)
  const [flash, setFlash] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), [])

  // 应用详情（名称、密钥、计数）
  useEffect(() => {
    let cancelled = false
    setAppError('')
    appsApi
      .get(appId)
      .then((a) => {
        if (!cancelled) setApp(a)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setApp(null)
        setAppError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [appId, refreshKey])

  // 题目分页列表
  useEffect(() => {
    let cancelled = false
    // 静默重取不闪骨架屏；普通取数才进 loading
    const silent = silentRef.current
    silentRef.current = false
    if (!silent) {
      setListState('loading')
      setListError('')
    }
    questionsApi
      .list(appId, {
        split: split === 'all' ? undefined : split,
        q: query || undefined,
        limit,
        offset: page * limit,
      })
      .then((res) => {
        if (cancelled) return
        setData(res)
        setListState('ready')
        setListError('')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setData(null) // 失败清空，不留旧数字
        setListError(errorMessage(err))
        setListState('error')
      })
    return () => {
      cancelled = true
    }
  }, [appId, split, limit, page, query, refreshKey])

  // 搜索防抖 300ms：连打 4 个字母只发 1 次请求
  useEffect(() => {
    if (searchInput === query) return
    const timer = window.setTimeout(() => {
      setQuery(searchInput.trim())
      setPage(0) // 搜索词变了必须回到第一页，否则会停在越界页
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchInput, query])

  // 后端没升级（响应里没有 matched）时，q 会被忽略，必须禁用搜索而不是假装搜到了
  const searchSupported = data !== null && typeof data.matched === 'number'
  const searchUnsupported = data !== null && typeof data.matched !== 'number'

  useEffect(() => {
    if (!searchUnsupported || !query) return
    setQuery('')
    setSearchInput('')
  }, [searchUnsupported, query])

  // 分页总数：优先用 matched（受 split + q 影响），没有则回退到 splits
  const currentTotal = data ? (data.matched ?? splitTotalOf(data.splits, split)) : 0
  const pageCount = Math.max(1, Math.ceil(currentTotal / limit))

  // 清空 / 删题后当前页可能越界，拉回最后一页
  useEffect(() => {
    if (!data) return
    const maxPage = Math.max(0, Math.ceil(currentTotal / limit) - 1)
    if (page > maxPage) setPage(maxPage)
  }, [data, currentTotal, limit, page])

  const parsed = useMemo(() => parsePasted(rawText), [rawText])
  const parsedWithRef = useMemo(() => parsed.filter((p) => p.reference).length, [parsed])

  const switchTab = (next: SplitTab) => {
    if (next === split) return
    setSplit(next)
    setPage(0)
  }

  const changeLimit = (next: number) => {
    setLimit(next)
    setPage(0)
  }

  const onImport = async () => {
    setImportError(null)
    setImportResult(null)

    if (parsed.length === 0) {
      setImportError('请先粘贴题目，一行一道')
      return
    }

    let seed: number | undefined
    if (seedText.trim()) {
      const n = Number(seedText.trim())
      if (!Number.isInteger(n)) {
        setImportError('seed 必须是整数，留空则由后端随机生成')
        return
      }
      seed = n
    }

    setImporting(true)
    try {
      const res = await questionsApi.import(appId, {
        items: parsed,
        replace,
        ...(seed === undefined ? {} : { seed }),
      })
      setImportResult(res)
      setRawText('')
      setSeedText('')
      setSplit('all')
      setPage(0)
      refresh()
    } catch (err) {
      setImportError(errorMessage(err))
    } finally {
      setImporting(false)
    }
  }

  const onClear = async () => {
    if (!clearTarget) return
    setClearing(true)
    try {
      const res = await questionsApi.clear(
        appId,
        clearTarget === 'all' ? undefined : clearTarget,
      )
      setFlash({
        kind: 'success',
        text:
          clearTarget === 'all'
            ? '已清空全部题目'
            : `已清空${SPLIT_LABEL[clearTarget]}，剩余 ${res.total} 道`,
      })
      setClearTarget(null)
      refresh()
    } catch (err) {
      setFlash({ kind: 'error', text: errorMessage(err) })
      setClearTarget(null)
    } finally {
      setClearing(false)
    }
  }

  const onDeleteQuestion = async () => {
    if (!pendingDelete || !data) return
    const target = pendingDelete
    setDeletingQuestion(true)
    try {
      const res = await questionsApi.remove(appId, target.id)

      // 统计卡直接用接口返回的 splits 更新，不再多发一次 /stats
      const base = data.matched ?? splitTotalOf(data.splits, split)
      const nextMatched = Math.max(0, base - 1)
      setData({
        ...data,
        splits: res.splits,
        matched: typeof data.matched === 'number' ? nextMatched : data.matched,
        items: data.items.filter((q) => q.id !== target.id),
      })
      setPendingDelete(null)
      setFlash({ kind: 'success', text: '已删除 1 道题目' })

      // 删掉的是本页最后一条 → 交给已有的越界回退逻辑自动翻页
      const maxPage = Math.max(0, Math.ceil(nextMatched / limit) - 1)
      if (page > maxPage) {
        setPage(maxPage)
      } else {
        // 否则静默重取一次，保证 offset 平移后不漏题（不闪骨架屏）
        silentRef.current = true
        setRefreshKey((k) => k + 1)
      }
    } catch (err) {
      setFlash({ kind: 'error', text: deleteErrorMessage(err) })
      setPendingDelete(null)
    } finally {
      setDeletingQuestion(false)
    }
  }

  const clearSearch = () => {
    setSearchInput('')
    setQuery('')
    setPage(0)
  }

  // 应用都拿不到（404 / 后端挂了），直接给错误页，不渲染空壳
  if (appError) {
    return (
      <div className="page">
        <a className="back-link" href="#/apps">
          ← 返回应用列表
        </a>
        <ErrorBlock
          title="打不开这个应用"
          message={appError}
          onRetry={refresh}
          extra={
            <p className="state-note">
              如果后端刚被停掉，这里会一直报错 —— 这是预期行为，不会显示任何缓存数字。
            </p>
          }
        />
      </div>
    )
  }

  const counts = data?.splits ?? null
  const pageStart = currentTotal === 0 ? 0 : page * limit + 1
  const pageEnd = Math.min((page + 1) * limit, currentTotal)

  return (
    <div className="page">
      <a className="back-link" href="#/apps">
        ← 返回应用列表
      </a>

      <div className="page-head">
        <div>
          <h1 className="page-title">{app ? app.name : '测试集管理'}</h1>
          <p className="page-sub">
            导入题目后由后端按 <strong>6:2:2</strong> 洗牌切分；这里看到的每个数字都来自接口。
          </p>
        </div>
        <div className="page-head-actions">
          <button type="button" className="btn btn-outline" onClick={refresh}>
            刷新
          </button>
          <button
            type="button"
            className="btn btn-sm btn-disabled"
            disabled
            title="F3 回答检查模型尚未接成服务"
          >
            回答检查 <NotWired />
          </button>
        </div>
      </div>

      {flash && (
        <Banner kind={flash.kind} onClose={() => setFlash(null)}>
          {flash.text}
        </Banner>
      )}

      {/* ---- 统计卡：全部来自 splits ---- */}
      <section className="stat-row">
        {counts ? (
          <>
            <StatCard label="优化集" hint={SPLIT_HINT.optimize} value={counts.optimize} tone="a" />
            <StatCard label="验证集" hint={SPLIT_HINT.valid} value={counts.valid} tone="b" />
            <StatCard label="测试集" hint={SPLIT_HINT.test} value={counts.test} tone="c" />
            <StatCard label="题目总数" hint="三份之和" value={counts.total} tone="d" />
          </>
        ) : listState === 'error' ? (
          <div className="stat-row-error">统计不可用 —— {listError}</div>
        ) : (
          <>
            <StatCard label="优化集" hint="" value={null} tone="a" />
            <StatCard label="验证集" hint="" value={null} tone="b" />
            <StatCard label="测试集" hint="" value={null} tone="c" />
            <StatCard label="题目总数" hint="" value={null} tone="d" />
          </>
        )}
      </section>

      {/* ---- 导入 ---- */}
      <section className="card">
        <div className="card-head">
          <div>
            <h2 className="card-title">导入题目</h2>
            <p className="card-sub">
              一行一道题；同一行用 <kbd>Tab</kbd> 隔开的第二段会当作「出处」。
            </p>
          </div>
        </div>

        <textarea
          className="textarea"
          rows={7}
          value={rawText}
          spellCheck={false}
          placeholder={'lora_rank 默认是多少？\tlora.md\n怎么开启 deepspeed？\tdeepspeed.md\n多卡训练怎么启动？'}
          onChange={(e) => setRawText(e.target.value)}
        />

        <div className="import-meta">
          {rawText.trim() ? (
            <span>
              本地解析：<strong>{parsed.length}</strong> 道题
              {parsedWithRef > 0 && (
                <>
                  ，其中 <strong>{parsedWithRef}</strong> 道带出处
                </>
              )}
            </span>
          ) : (
            <span className="muted">粘贴后自动按行解析，切分结果由后端返回</span>
          )}
          <span className="import-meta-hint">前端不预设任何比例数字</span>
        </div>

        <div className="import-options">
          <label className="field field-inline">
            <span className="field-label">
              seed <span className="field-hint">留空由后端随机生成</span>
            </span>
            <input
              className="input input-narrow"
              value={seedText}
              inputMode="numeric"
              placeholder="20261020"
              onChange={(e) => setSeedText(e.target.value)}
            />
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={replace}
              onChange={(e) => setReplace(e.target.checked)}
            />
            <span>
              覆盖现有题目
              <span className="field-hint">不勾选则追加到现有题目后面</span>
            </span>
          </label>
        </div>

        {replace && (
          <p className="inline-warn">
            勾选「覆盖」时，导入会先清空该应用的全部题目再写入，历史切分结果不保留。
          </p>
        )}

        {importError && <Banner kind="error">{importError}</Banner>}

        <div className="form-actions form-actions-left">
          <button
            type="button"
            className="btn btn-primary"
            onClick={onImport}
            disabled={importing || parsed.length === 0}
          >
            {importing ? '导入中…' : '导入并切分'}
          </button>
          {rawText && (
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => {
                setRawText('')
                setImportError(null)
              }}
              disabled={importing}
            >
              清空输入框
            </button>
          )}
        </div>

        {importResult && (
          <div className="import-result">
            <div className="import-result-head">
              <h3>导入完成</h3>
              <span className="mono">
                导入 {importResult.imported} 道 · seed {importResult.seed}
              </span>
            </div>
            <SplitBar counts={importResult.splits} />
            <div className="split-legend">
              <LegendItem label="优化集" value={importResult.splits.optimize} total={importResult.splits.total} tone="a" />
              <LegendItem label="验证集" value={importResult.splits.valid} total={importResult.splits.total} tone="b" />
              <LegendItem label="测试集" value={importResult.splits.test} total={importResult.splits.total} tone="c" />
            </div>
            <p className="import-result-note">
              同样的 seed 会得到同样的切分；换个 seed 重新导入即可换一种分法。
            </p>
          </div>
        )}
      </section>

      {/* ---- 题目列表 ---- */}
      <section className="card">
        <div className="card-head">
          <div>
            <h2 className="card-title">题目列表</h2>
            <p className="card-sub">按分类查看，分页参数直接透传给后端。</p>
          </div>
          <div className="card-head-actions">
            <div className="search-box">
              <input
                className="input input-search"
                type="search"
                value={searchInput}
                placeholder="搜索题目或出处"
                aria-label="搜索题目或出处"
                disabled={searchUnsupported}
                onChange={(e) => setSearchInput(e.target.value)}
              />
              {searchInput && (
                <button
                  type="button"
                  className="search-clear"
                  onClick={clearSearch}
                  aria-label="清除搜索"
                >
                  ×
                </button>
              )}
            </div>
            {searchUnsupported && <span className="search-hint">后端未支持搜索</span>}
            <label className="inline-select">
              每页
              <select
                value={limit}
                onChange={(e) => changeLimit(Number(e.target.value))}
                disabled={listState === 'loading'}
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
              条
            </label>
            <button
              type="button"
              className="btn btn-sm btn-danger-ghost"
              onClick={() => setClearTarget(split)}
              disabled={listState !== 'ready' || currentTotal === 0}
            >
              清空{split === 'all' ? '全部' : SPLIT_LABEL[split]}
            </button>
          </div>
        </div>

        <div className="tabs" role="tablist">
          {TABS.map((tab) => {
            const count = counts ? splitTotalOf(counts, tab.key) : null
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={split === tab.key}
                className={`tab ${split === tab.key ? 'is-active' : ''}`}
                onClick={() => switchTab(tab.key)}
              >
                {tab.label}
                {count !== null && <span className="tab-count">{count}</span>}
              </button>
            )
          })}
        </div>

        {listState === 'loading' && <Skeleton rows={5} />}

        {listState === 'ready' && searchSupported && data && query && (
          <div className="search-summary">
            搜索「<strong>{query}</strong>」，命中 <strong>{data.matched}</strong> 条
            <button type="button" className="link-btn search-summary-clear" onClick={clearSearch}>
              清除搜索
            </button>
          </div>
        )}

        {listState === 'error' && (
          <ErrorBlock
            title="题目列表加载失败"
            message={listError}
            onRetry={refresh}
            extra={
              <p className="state-note">
                所有计数与题目都来自 <code>GET /apps/{appId}/questions</code>，请求失败时不会回退到缓存。
              </p>
            }
          />
        )}

        {listState === 'ready' && data && data.items.length === 0 && (
          <EmptyBlock
            title={
              query
                ? '没有匹配的题目'
                : currentTotal === 0
                  ? '这个分类还没有题目'
                  : '这一页没有内容'
            }
            message={
              query
                ? `没有包含「${query}」的题目，换个关键词试试。`
                : currentTotal === 0
                  ? '在上面粘贴题目并导入，后端会自动切分成 6:2:2。'
                  : '当前页超出范围，试试回到第一页。'
            }
            action={
              query ? (
                <button type="button" className="btn btn-outline" onClick={clearSearch}>
                  清除搜索
                </button>
              ) : page > 0 ? (
                <button type="button" className="btn btn-outline" onClick={() => setPage(0)}>
                  回到第一页
                </button>
              ) : undefined
            }
          />
        )}

        {listState === 'ready' && data && data.items.length > 0 && (
          <>
            <div className="q-table">
              <div className="q-row q-head">
                <div className="q-cell">#</div>
                <div className="q-cell">题目</div>
                <div className="q-cell">出处</div>
                <div className="q-cell">分类</div>
                <div className="q-cell">创建时间</div>
                <div className="q-cell" />
              </div>
              {data.items.map((q, i) => (
                <div className="q-row" key={q.id}>
                  <div className="q-cell q-idx" data-label="#">
                    {page * limit + i + 1}
                  </div>
                  <div className="q-cell q-content" data-label="题目">
                    {q.content}
                  </div>
                  <div className="q-cell q-ref" data-label="出处">
                    {q.reference ? (
                      <span className="mono">{q.reference}</span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </div>
                  <div className="q-cell q-split" data-label="分类">
                    <span className={`pill pill-${q.split}`}>{SPLIT_LABEL[q.split]}</span>
                  </div>
                  <div className="q-cell q-time" data-label="创建时间">
                    {q.created_at}
                  </div>
                  <div className="q-cell q-del">
                    <button
                      type="button"
                      className="btn-row-del"
                      onClick={() => setPendingDelete(q)}
                      aria-label={`删除第 ${page * limit + i + 1} 题`}
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="pager">
              <span className="pager-info">
                第 <strong>{pageStart}</strong>–<strong>{pageEnd}</strong> 条 / 共{' '}
                <strong>{currentTotal}</strong> 条
                <span className="pager-split">
                  （{split === 'all' ? '全部' : SPLIT_LABEL[split]}）
                </span>
              </span>
              <div className="pager-btns">
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => setPage(0)}
                  disabled={page === 0}
                >
                  首页
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  上一页
                </button>
                <span className="pager-page">
                  {page + 1} / {pageCount}
                </span>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  disabled={page >= pageCount - 1}
                >
                  下一页
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => setPage(pageCount - 1)}
                  disabled={page >= pageCount - 1}
                >
                  末页
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <ConfirmDialog
        open={clearTarget !== null}
        title={clearTarget === 'all' ? '清空全部题目' : `清空${clearTarget ? SPLIT_LABEL[clearTarget] : ''}`}
        danger
        busy={clearing}
        confirmText="确认清空"
        onConfirm={onClear}
        onCancel={() => setClearTarget(null)}
      >
        {clearTarget !== null && counts && (
          <>
            <p>
              将从「{app?.name ?? '该应用'}」删除{' '}
              <strong>{splitTotalOf(counts, clearTarget)}</strong> 道题目
              {clearTarget === 'all' ? '（全部三个分类）' : `（仅${SPLIT_LABEL[clearTarget]}）`}。
            </p>
            <p className="modal-warn">此操作不可撤销，删除后该分类计数会立刻归零。</p>
          </>
        )}
      </ConfirmDialog>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除这道题"
        danger
        busy={deletingQuestion}
        confirmText="确认删除"
        onConfirm={onDeleteQuestion}
        onCancel={() => setPendingDelete(null)}
      >
        {pendingDelete && (
          <>
            <p className="modal-quote">
              {pendingDelete.content.length > 40
                ? pendingDelete.content.slice(0, 40) + '…'
                : pendingDelete.content}
            </p>
            <p className="modal-warn">此操作不可撤销。</p>
          </>
        )}
      </ConfirmDialog>
    </div>
  )
}

function StatCard({
  label,
  hint,
  value,
  tone,
}: {
  label: string
  hint: string
  value: number | null
  tone: string
}) {
  return (
    <div className={`stat-card stat-${tone}`}>
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${value === null ? 'is-pending' : ''}`}>
        {value === null ? '—' : value}
      </div>
      <div className="stat-hint">{hint}</div>
    </div>
  )
}

function SplitBar({ counts }: { counts: SplitCounts }) {
  const total = counts.total
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0)
  return (
    <div className="split-bar" role="img" aria-label="切分比例">
      {total === 0 ? (
        <div className="split-seg split-seg-empty" style={{ width: '100%' }} />
      ) : (
        <>
          <div className="split-seg seg-a" style={{ width: `${pct(counts.optimize)}%` }} />
          <div className="split-seg seg-b" style={{ width: `${pct(counts.valid)}%` }} />
          <div className="split-seg seg-c" style={{ width: `${pct(counts.test)}%` }} />
        </>
      )}
    </div>
  )
}

function LegendItem({
  label,
  value,
  total,
  tone,
}: {
  label: string
  value: number
  total: number
  tone: string
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div className="legend-item">
      <span className={`legend-dot seg-${tone}`} />
      <span className="legend-label">{label}</span>
      <span className="legend-value">{value}</span>
      <span className="legend-pct">{pct}%</span>
    </div>
  )
}
