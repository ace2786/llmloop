import type { ReactNode } from 'react'

/** 骨架屏。只在真正等待时出现，绝不用来占位假装有数据。 */
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton-wrap" aria-busy="true" aria-live="polite">
      {Array.from({ length: rows }).map((_, i) => (
        <div className="skeleton-row" key={i}>
          <div className="skeleton-bar" style={{ width: `${88 - i * 12}%` }} />
          <div className="skeleton-bar skeleton-bar-sm" style={{ width: `${40 + i * 8}%` }} />
        </div>
      ))}
      <span className="sr-only">加载中</span>
    </div>
  )
}

/** 请求失败。必须给出原因和重试入口，不能白屏。 */
export function ErrorBlock({
  title = '加载失败',
  message,
  onRetry,
  extra,
}: {
  title?: string
  message: string
  onRetry?: () => void
  extra?: ReactNode
}) {
  return (
    <div className="state-block state-error" role="alert">
      <div className="state-icon">!</div>
      <div className="state-body">
        <h3>{title}</h3>
        <p>{message}</p>
        {extra}
      </div>
      {onRetry && (
        <button type="button" className="btn btn-outline" onClick={onRetry}>
          重试
        </button>
      )}
    </div>
  )
}

/** 空状态。数字为 0 或列表为空时用它，而不是显示一排 0 装作正常。 */
export function EmptyBlock({
  title,
  message,
  action,
}: {
  title: string
  message?: string
  action?: ReactNode
}) {
  return (
    <div className="state-block state-empty">
      <div className="state-icon state-icon-muted">∅</div>
      <div className="state-body">
        <h3>{title}</h3>
        {message && <p>{message}</p>}
        {action}
      </div>
    </div>
  )
}

export function Banner({
  kind = 'info',
  children,
  onClose,
}: {
  kind?: 'info' | 'success' | 'warn' | 'error'
  children: ReactNode
  onClose?: () => void
}) {
  return (
    <div className={`banner banner-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <div className="banner-text">{children}</div>
      {onClose && (
        <button type="button" className="banner-close" onClick={onClose} aria-label="关闭">
          ×
        </button>
      )}
    </div>
  )
}

/** 按钮上的「功能未接入」小标签 */
export function NotWired() {
  return <span className="tag tag-muted">功能未接入</span>
}
