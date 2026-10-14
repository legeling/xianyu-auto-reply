import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

// 执行实际 TS 模块，注入网络/存储/时钟；无需另装浏览器或测试框架。
function load(relative, dependencies, globals = {}) {
  const filename = new URL(`../src/${relative}`, import.meta.url)
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText
  const exports = {}
  vm.runInNewContext(code, {
    exports, require: (id) => {
      assert.ok(id in dependencies, `unexpected import ${id}`)
      return dependencies[id]
    }, ...globals,
  }, { filename: filename.pathname })
  return exports
}

function environment() {
  const storage = new Map([['auth_token', 'expired'], ['refresh_token', 'refresh']])
  const localStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: (key) => storage.delete(key),
  }
  let calls = 0
  let post = async () => ({ data: { success: true, token: 'valid', refresh_token: 'rotated' } })
  const state = {
    clearAuth() { storage.clear() },
    updateTokens(token, refresh) { storage.set('auth_token', token); storage.set('refresh_token', refresh) },
    updateUser() {},
  }
  const instance = Object.assign(() => {}, {
    defaults: { timeout: 90000 },
    interceptors: { request: { use() {} }, response: { use() {} } },
    get: async () => ({ data: { authenticated: storage.get('auth_token') === 'valid', user_id: 4 } }),
  })
  const axios = {
    create: () => instance,
    post: async (...args) => { calls++; return post(...args) },
    isAxiosError: (error) => error?.isAxiosError === true,
  }
  const request = load('utils/request.ts', {
    axios: { __esModule: true, default: axios },
    '@/store/authStore': { useAuthStore: { getState: () => state } },
    './apiError': { getApiErrorMessage() {} },
  }, { localStorage, Error, FormData })
  return { storage, localStorage, state, request, calls: () => calls, setPost: (value) => { post = value } }
}

test('expired access token on reopening refreshes and verifies the new token', async () => {
  const env = environment()
  const auth = load('api/auth.ts', {
    '@/utils/request': env.request,
    '@/api/settings': { normalizeLoginBrandingSettings() {} },
  }, { localStorage: env.localStorage })
  assert.equal((await auth.verifyToken()).authenticated, true)
  assert.equal(env.storage.get('auth_token'), 'valid')
  assert.equal(env.storage.get('refresh_token'), 'rotated')
  assert.equal(env.calls(), 1)
})

test('concurrent refreshes share one network request', async () => {
  const env = environment()
  let finish
  env.setPost(() => new Promise((resolve) => { finish = resolve }))
  const first = env.request.refreshAccessToken()
  const second = env.request.refreshAccessToken()
  finish({ data: { success: true, token: 'valid', refresh_token: 'rotated' } })
  assert.deepEqual(await Promise.all([first, second]), ['valid', 'valid'])
  assert.equal(env.calls(), 1)
})

test('network errors preserve login and release all concurrent waiters', async () => {
  const env = environment()
  env.setPost(async () => { throw new Error('network disconnected') })
  const results = await Promise.allSettled([env.request.refreshAccessToken(), env.request.refreshAccessToken()])
  assert.ok(results.every((result) => result.status === 'rejected'))
  assert.equal(env.storage.get('refresh_token'), 'refresh')
  env.setPost(async () => ({ data: { success: true, token: 'valid', refresh_token: 'rotated' } }))
  assert.equal(await env.request.refreshAccessToken(), 'valid')
})

test('explicitly rejected refresh clears login', async () => {
  const env = environment()
  env.setPost(async () => ({ data: { success: false, message: '刷新令牌无效' } }))
  await assert.rejects(env.request.refreshAccessToken())
  assert.equal(env.storage.size, 0)
})

test('logout while refresh is in flight cannot restore the old login', async () => {
  const env = environment()
  let finish
  env.setPost(() => new Promise((resolve) => { finish = resolve }))
  const refreshing = env.request.refreshAccessToken()
  env.state.clearAuth()
  finish({ data: { success: true, token: 'valid', refresh_token: 'rotated' } })
  await assert.rejects(refreshing)
  assert.equal(env.storage.size, 0)
})

test('online session renews from expiry, rolls again and cleans timers/listeners', async () => {
  const env = environment()
  const timers = new Map()
  const listeners = new Map()
  let timerId = 0
  let now = 0
  const jwt = (exp) => `header.${Buffer.from(JSON.stringify({ iat: now / 1000, exp })).toString('base64url')}.signature`
  env.storage.set('auth_token', jwt(3600))
  const events = {
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: (name) => listeners.delete(name),
    visibilityState: 'visible',
  }
  const session = load('utils/sessionRenewal.ts', {}, {
    localStorage: env.localStorage, atob,
    Date: { now: () => now }, document: events, window: events,
    setTimeout: (fn, delay) => { timers.set(++timerId, { fn, at: now + delay }); return timerId },
    clearTimeout: (id) => timers.delete(id),
  })
  let renewals = 0
  const stop = session.startSessionRenewal(async () => {
    renewals++
    env.storage.set('auth_token', jwt(now / 1000 + 3600))
    return env.storage.get('auth_token')
  })
  assert.equal(timers.size, 1)
  for (let iteration = 0; iteration < 2; iteration++) {
    const [id, timer] = [...timers][0]
    assert.ok(timer.at > now)
    now = timer.at
    timers.delete(id)
    timer.fn()
    await new Promise(setImmediate)
    assert.equal(timers.size, 1)
  }
  assert.equal(renewals, 2)
  stop()
  assert.equal(timers.size, 0)
  assert.equal(listeners.size, 0)
})

test('background page resumes expiry checking on visibility without polling', async () => {
  const env = environment()
  const listeners = new Map()
  const events = { visibilityState: 'visible', addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: (name) => listeners.delete(name) }
  const expired = `header.${Buffer.from(JSON.stringify({ exp: 1 })).toString('base64url')}.signature`
  env.storage.set('auth_token', expired)
  const session = load('utils/sessionRenewal.ts', {}, {
    localStorage: env.localStorage, atob, Date: { now: () => 60000 },
    document: events, window: events, setTimeout: () => 1, clearTimeout() {},
  })
  let calls = 0
  const stop = session.startSessionRenewal(async () => { calls++; throw new Error('offline') })
  listeners.get('visibilitychange')()
  await new Promise(setImmediate)
  assert.equal(calls, 1)
  assert.equal(env.storage.get('refresh_token'), 'refresh')
  listeners.get('online')()
  await new Promise(setImmediate)
  assert.equal(calls, 2)
  stop()
})
