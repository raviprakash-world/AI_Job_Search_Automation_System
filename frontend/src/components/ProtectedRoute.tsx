import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) return <div className="p-6 text-gray-500">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}
