import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { authApi } from '../api/endpoints'
import { setSessionExpiredHandler, setRefreshToken, setToken } from '../api/client'
import type { User } from '../api/types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setSessionExpiredHandler(logout)
    return () => setSessionExpiredHandler(null)
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setLoading(false)
      return
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => logout())
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const tokens = await authApi.login(email, password)
    setToken(tokens.access_token)
    setRefreshToken(tokens.refresh_token)
    setUser(await authApi.me())
  }

  async function register(email: string, password: string, name: string) {
    const tokens = await authApi.register(email, password, name)
    setToken(tokens.access_token)
    setRefreshToken(tokens.refresh_token)
    setUser(await authApi.me())
  }

  function logout() {
    setToken(null)
    setRefreshToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
