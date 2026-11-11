/**
 * 助手页：给最终用户用的问答界面（任务书第 4 节第 11 个页面）。
 *
 * 这是「被测应用」本身，不是评测工具 —— 评测循环优化的就是它。
 * 每条回答下面可以点「有用 / 没用 / 有错误」，反馈会存进 chat_messages，
 * 以后接「反馈值守」用。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { chatApi, type ChatRating, type ChatReference } from '../api'
import { errorMessage } from '../api/client'

interface Turn {
  id: number
  question: string
  answer: string
  references: ChatReference[]
  latency: number
  rating: ChatRating | null
  error?: string
}

const SUGGESTIONS = [
  '训练时 save_epochs 这个参数是干什么的？',
  'LoRA 的 rank 设多少合适？',
  'DeepSpeed 训练保存 checkpoint 报错怎么办？',
]

export default function AssistantPage({ appId }: { appId: number }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns.length, busy])

  const send = useCallback(
    async (text: string) => {
      const q = text.trim()
      if (!q || busy) return
      setInput('')
      setBusy(true)
      const pendingId = Date.now()
      try {
        const r = await chatApi.ask(appId, q, 3)
        setTurns((prev) => [
          ...prev,
          {
            id: r.message_id,
            question: q,
            answer: r.answer,
            references: r.references,
            latency: r.latency_ms,
            rating: null,
          },
        ])
      } catch (err) {
        setTurns((prev) => [
          ...prev,
          {
            id: pendingId,
            question: q,
            answer: '',
            references: [],
            latency: 0,
            rating: null,
            error: errorMessage(err),
          },
        ])
      } finally {
        setBusy(false)
      }
    },
    [appId, busy],
  )

  const rate = useCallback(async (turn: Turn, rating: ChatRating) => {
    if (turn.error) return
    try {
      await chatApi.feedback(turn.id, rating)
      setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, rating } : t)))
    } catch {
      /* 反馈失败不打断对话，静默即可 */
    }
  }, [])

  return (
    <div className="chat-wrap">
      <header className="chat-head">
        <h1 className="page-title">LlamaFactory 助手</h1>
        <p className="page-sub">
          用中文问 LlamaFactory 的配置、训练和报错问题。回答来自文档检索，
          <strong>每条都会列出引用的文档段落</strong>，可以点开核对。
        </p>
      </header>

      <div className="chat-scroll">
        {turns.length === 0 && (
          <div className="chat-empty">
            <p>试着问：</p>
            <div className="chat-suggests">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="chip" onClick={() => void send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t) => (
          <div key={t.id} className="turn">
            <div className="turn-q">{t.question}</div>

            {t.error ? (
              <div className="turn-a turn-a-error">请求失败：{t.error}</div>
            ) : (
              <>
                <div className="turn-a">{t.answer || '（空回答）'}</div>

                {t.references.length > 0 && (
                  <details className="turn-refs">
                    <summary>引用 {t.references.length} 段文档 · {t.latency} ms</summary>
                    <ul>
                      {t.references.map((r, i) => (
                        <li key={i}>
                          <div className="ref-path">
                            {r.path} &gt; {r.heading}
                            <span className="ref-score">{r.score}</span>
                          </div>
                          <div className="ref-snippet">{r.snippet}</div>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}

                <div className="turn-actions">
                  {(
                    [
                      ['useful', '有用'],
                      ['useless', '没用'],
                      ['wrong', '有错误'],
                    ] as [ChatRating, string][]
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      className={`btn btn-mini${t.rating === key ? ' is-on' : ''}`}
                      onClick={() => void rate(t, key)}
                      disabled={t.rating !== null}
                    >
                      {label}
                    </button>
                  ))}
                  {t.rating && <span className="turn-thanks">已记录反馈</span>}
                </div>
              </>
            )}
          </div>
        ))}

        {busy && (
          <div className="turn">
            <div className="turn-a turn-a-busy">
              <span className="spinner spinner-sm" /> 正在检索文档并生成回答…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault()
          void send(input)
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入问题，回车发送"
          disabled={busy}
        />
        <button type="submit" className="btn btn-primary" disabled={busy || !input.trim()}>
          发送
        </button>
      </form>
    </div>
  )
}
