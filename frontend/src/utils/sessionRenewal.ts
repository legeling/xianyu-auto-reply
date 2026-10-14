// JWT 到期时间只用于安排续期；是否有权访问仍由服务端验证。
const MILLISECONDS_PER_SECOND = 1000
const REFRESH_LEAD_SECONDS = 60
const REFRESH_LEAD_RATIO = 0.1
const BROWSER_MAX_TIMER_MS = 2 ** 31 - 1

export function renewalTime(token: string): number | null {
  try {
    const encoded = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, '=')))
    if (typeof payload.exp !== 'number' || !Number.isFinite(payload.exp)) return null
    const lifetime = typeof payload.iat === 'number' ? payload.exp - payload.iat : REFRESH_LEAD_SECONDS / REFRESH_LEAD_RATIO
    const lead = Math.min(REFRESH_LEAD_SECONDS, Math.max(0, lifetime * REFRESH_LEAD_RATIO))
    return (payload.exp - lead) * MILLISECONDS_PER_SECOND
  } catch {
    return null
  }
}

export function startSessionRenewal(refresh: () => Promise<string>): () => void {
  let stopped = false
  let pending = false
  let timer: ReturnType<typeof setTimeout> | undefined

  const schedule = () => {
    clearTimeout(timer)
    if (stopped || !localStorage.getItem('refresh_token')) return
    const token = localStorage.getItem('auth_token')
    const due = token ? renewalTime(token) : null
    if (due === null) return
    timer = setTimeout(() => { void renewIfDue() }, Math.min(Math.max(0, due - Date.now()), BROWSER_MAX_TIMER_MS))
  }
  const renewIfDue = async () => {
    if (stopped || pending || !localStorage.getItem('refresh_token')) return
    const token = localStorage.getItem('auth_token')
    const due = token ? renewalTime(token) : null
    if (due === null) return
    if (due > Date.now()) {
      schedule()
      return
    }
    pending = true
    try {
      await refresh()
      schedule()
    } catch {
      // 网络中断保留登录；恢复网络、返回页面或下次 API 请求时再次检查。
    } finally {
      pending = false
    }
  }
  const onVisible = () => { if (document.visibilityState === 'visible') void renewIfDue() }
  const onOnline = () => { void renewIfDue() }
  document.addEventListener('visibilitychange', onVisible)
  window.addEventListener('online', onOnline)
  schedule()
  return () => {
    stopped = true
    clearTimeout(timer)
    document.removeEventListener('visibilitychange', onVisible)
    window.removeEventListener('online', onOnline)
  }
}
