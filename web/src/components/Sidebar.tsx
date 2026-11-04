import type { ReactNode } from 'react'
import { navigate, type Route } from '../router'

export type NavKey = 'apps' | 'questions' | 'evals' | 'loop' | 'settings'

const ICONS: Record<NavKey, ReactNode> = {
  apps: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  questions: (
    <>
      <path d="M9 6h11M9 12h11M9 18h7" />
      <circle cx="4.5" cy="6" r="1.1" />
      <circle cx="4.5" cy="12" r="1.1" />
      <circle cx="4.5" cy="18" r="1.1" />
    </>
  ),
  evals: (
    <>
      <path d="M3.5 17.5a8.5 8.5 0 1 1 17 0" />
      <path d="M12 13.5l3.8-3.8" />
      <circle cx="12" cy="17.5" r="1.3" />
    </>
  ),
  loop: (
    <>
      <path d="M20 12a8 8 0 1 1-2.4-5.7" />
      <path d="M20.5 4v5h-5" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h9M19 7h1M4 17h4M13 17h7" />
      <circle cx="16" cy="7" r="2.1" />
      <circle cx="10.5" cy="17" r="2.1" />
    </>
  ),
}

interface SidebarProps {
  route: Route
  email: string | null
  /** 题库导航目标：上一次进入的应用 */
  lastAppId: number | null
  open: boolean
  onClose: () => void
  onLogout: () => void
  /** 还没做的功能统一提示「下一阶段」 */
  onSoon: (label: string) => void
}

export function Sidebar({
  route,
  email,
  lastAppId,
  open,
  onClose,
  onLogout,
  onSoon,
}: SidebarProps) {
  const active = (
    route.name === 'questions' ? 'questions' : route.name === 'apps' ? 'apps' : null
  ) as NavKey | null

  const go = (path: string) => {
    navigate(path)
    onClose()
  }

  return (
    <aside className={`sidebar${open ? ' is-open' : ''}`} aria-label="主导航">
      <div className="sidebar-brand">
        <span className="brand-mark">LL</span>
        <span className="brand-text">
          <span className="brand-name">LLMLoop</span>
          <span className="brand-sub">大模型应用自动调优</span>
        </span>
      </div>

      <nav className="side-nav">
        <NavItem
          item="apps"
          label="应用"
          active={active === 'apps'}
          onClick={() => go('/apps')}
        />

        <NavItem
          item="questions"
          label="题库"
          active={active === 'questions'}
          onClick={() => {
            if (lastAppId) go(`/apps/${lastAppId}/questions`)
            else onSoon('先从「应用」里选一个应用，再进题库')
          }}
        />

        <NavItem
          item="evals"
          label="评测"
          active={active === 'evals'}
          tag="阶段 2"
          onClick={() => onSoon('评测页面在阶段 2 接入')}
        />

        <NavItem
          item="loop"
          label="循环"
          disabled
          onClick={() => onSoon('优化循环下一阶段接入')}
        />

        <NavItem
          item="settings"
          label="设置"
          disabled
          onClick={() => onSoon('设置页下一阶段接入')}
        />
      </nav>

      <div className="sidebar-foot">
        {email && (
          <span className="side-user" title={email}>
            {email}
          </span>
        )}
        <button type="button" className="btn btn-outline btn-sm" onClick={onLogout}>
          退出登录
        </button>
      </div>
    </aside>
  )
}

function NavItem({
  item,
  label,
  active = false,
  disabled = false,
  tag,
  onClick,
}: {
  item: NavKey
  label: string
  active?: boolean
  disabled?: boolean
  tag?: string
  onClick: () => void
}) {
  const cls = [
    'nav-item',
    active ? 'is-active' : '',
    disabled ? 'is-disabled' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button
      type="button"
      className={cls}
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
    >
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {ICONS[item]}
      </svg>
      <span className="nav-label">{label}</span>
      {tag && <span className="nav-tag">{tag}</span>}
    </button>
  )
}
