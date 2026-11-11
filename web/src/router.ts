/**
 * 一个 30 行的 hash 路由。不引 react-router —— 只有三条路由，
 * 少一个依赖就少一个装不上的风险。
 */
import { useEffect, useState } from 'react'

export type Route =
  | { name: 'apps' }
  | { name: 'questions'; appId: number }
  | { name: 'assistant'; appId: number }
  | { name: 'evals'; appId: number }
  | { name: 'evalDetail'; runId: number }
  | { name: 'login' }

function readHash(): string {
  return window.location.hash || ''
}

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, '')

  const questions = path.match(/^\/apps\/(\d+)\/questions\/?$/)
  if (questions) return { name: 'questions', appId: Number(questions[1]) }

  const assistant = path.match(/^\/apps\/(\d+)\/assistant\/?$/)
  if (assistant) return { name: 'assistant', appId: Number(assistant[1]) }

  const evals = path.match(/^\/apps\/(\d+)\/evals\/?$/)
  if (evals) return { name: 'evals', appId: Number(evals[1]) }

  const evalDetail = path.match(/^\/evals\/(\d+)\/?$/)
  if (evalDetail) return { name: 'evalDetail', runId: Number(evalDetail[1]) }

  if (path === '/login') return { name: 'login' }
  return { name: 'apps' }
}

export function navigate(path: string) {
  const target = '#' + path
  if (window.location.hash === target) return
  window.location.hash = path
}

export function useRoute(): Route {
  const [hash, setHash] = useState(readHash)

  useEffect(() => {
    const onChange = () => setHash(readHash())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  return parseRoute(hash)
}
