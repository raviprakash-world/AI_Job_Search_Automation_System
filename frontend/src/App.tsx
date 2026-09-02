import { Navigate, Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar'
import ProtectedRoute from './components/ProtectedRoute'
import ApplicationTracker from './pages/ApplicationTracker'
import ApplicationWorkspace from './pages/ApplicationWorkspace'
import AutomationCenter from './pages/AutomationCenter'
import Dashboard from './pages/Dashboard'
import JobDiscovery from './pages/JobDiscovery'
import Login from './pages/Login'
import MasterProfile from './pages/MasterProfile'
import NewApplication from './pages/NewApplication'
import Register from './pages/Register'
import ResumeStudio from './pages/ResumeStudio'
import Settings from './pages/Settings'
import { useAuth } from './lib/auth'

export default function App() {
  const { user, loading } = useAuth()

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <NavBar />
      <Routes>
        <Route path="/login" element={!loading && user ? <Navigate to="/dashboard" replace /> : <Login />} />
        <Route path="/register" element={!loading && user ? <Navigate to="/dashboard" replace /> : <Register />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <MasterProfile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/jobs"
          element={
            <ProtectedRoute>
              <JobDiscovery />
            </ProtectedRoute>
          }
        />
        <Route
          path="/resumes"
          element={
            <ProtectedRoute>
              <ResumeStudio />
            </ProtectedRoute>
          }
        />
        <Route
          path="/applications"
          element={
            <ProtectedRoute>
              <ApplicationTracker />
            </ProtectedRoute>
          }
        />
        <Route
          path="/applications/new"
          element={
            <ProtectedRoute>
              <NewApplication />
            </ProtectedRoute>
          }
        />
        <Route
          path="/applications/:id"
          element={
            <ProtectedRoute>
              <ApplicationWorkspace />
            </ProtectedRoute>
          }
        />
        <Route
          path="/automation"
          element={
            <ProtectedRoute>
              <AutomationCenter />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </div>
  )
}
