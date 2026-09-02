const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

export class ApiError extends Error {
  code: string
  status: number
  details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

function getToken(): string | null {
  return localStorage.getItem('access_token')
}

function getRefreshToken(): string | null {
  return localStorage.getItem('refresh_token')
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem('access_token', token)
  else localStorage.removeItem('access_token')
}

export function setRefreshToken(token: string | null) {
  if (token) localStorage.setItem('refresh_token', token)
  else localStorage.removeItem('refresh_token')
}

// Registered by AuthProvider so client.ts can force a logout when the access
// token has expired and the refresh token can't renew it either — without
// this, requests just fail silently 30 minutes after login with no path back
// to the login screen.
let onSessionExpired: (() => void) | null = null

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler
}

// Coalesce concurrent 401s into a single refresh call rather than one per request.
let refreshInFlight: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
        if (!response.ok) return false
        const data = await response.json()
        setToken(data.access_token)
        setRefreshToken(data.refresh_token)
        return true
      } catch {
        return false
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

const NO_REFRESH_PATHS = new Set(['/auth/login', '/auth/register', '/auth/refresh'])

async function handleUnauthorized(path: string): Promise<boolean> {
  if (NO_REFRESH_PATHS.has(path)) return false
  const refreshed = await tryRefresh()
  if (!refreshed) {
    setToken(null)
    setRefreshToken(null)
    onSessionExpired?.()
  }
  return refreshed
}

async function throwApiError(response: Response): Promise<never> {
  const data = await response.json().catch(() => ({}))
  const err = data?.error ?? {}
  throw new ApiError(response.status, err.code ?? 'unknown_error', err.message ?? 'Request failed', err.details ?? {})
}

async function request<T>(path: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const token = getToken()
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (response.status === 204) {
    return undefined as T
  }

  if (response.status === 401 && !isRetry) {
    const refreshed = await handleUnauthorized(path)
    if (refreshed) {
      return request<T>(path, options, true)
    }
  }

  if (!response.ok) {
    await throwApiError(response)
  }

  const data = await response.json().catch(() => ({}))
  return data as T
}

async function getBlob(path: string, isRetry = false): Promise<Blob> {
  const token = getToken()
  const headers = new Headers()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path}`, { headers })

  if (response.status === 401 && !isRetry) {
    const refreshed = await handleUnauthorized(path)
    if (refreshed) {
      return getBlob(path, true)
    }
  }

  if (!response.ok) {
    await throwApiError(response)
  }
  return response.blob()
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  getBlob,
}
