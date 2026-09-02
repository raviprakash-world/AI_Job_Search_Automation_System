import { useQuery } from '@tanstack/react-query'
import { NavLink } from 'react-router-dom'
import { notificationsApi } from '../api/endpoints'
import { useAuth } from '../lib/auth'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm ${isActive ? 'font-medium text-indigo-600' : 'text-gray-600 dark:text-gray-400'}`

export default function NavBar() {
  const { user, logout } = useAuth()
  const { data: unread } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => notificationsApi.list(true),
    enabled: !!user,
    refetchInterval: 60_000,
  })
  const unreadCount = unread?.length ?? 0

  return (
    <nav className="flex items-center justify-between border-b border-gray-200 px-6 py-3 dark:border-gray-800">
      <div className="flex items-center gap-6">
        <span className="font-semibold text-gray-900 dark:text-gray-100">Job Search OS</span>
        <NavLink to="/dashboard" className={navLinkClass}>
          Dashboard
        </NavLink>
        <NavLink to="/profile" className={navLinkClass}>
          Master Profile
        </NavLink>
        <NavLink to="/jobs" className={navLinkClass}>
          Job Discovery
        </NavLink>
        <NavLink to="/resumes" className={navLinkClass}>
          Resume Studio
        </NavLink>
        <NavLink to="/applications" className={navLinkClass}>
          Applications
        </NavLink>
        <NavLink to="/automation" className={navLinkClass}>
          Automation
          {unreadCount > 0 && (
            <span className="ml-1 rounded-full bg-indigo-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
              {unreadCount}
            </span>
          )}
        </NavLink>
        <NavLink to="/settings" className={navLinkClass}>
          Settings
        </NavLink>
      </div>
      {user && (
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600 dark:text-gray-400">{user.email}</span>
          <button onClick={logout} className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400">
            Sign out
          </button>
        </div>
      )}
    </nav>
  )
}
