import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { automationApi, notificationsApi } from '../api/endpoints'
import type { AutomationRun } from '../api/types'
import Section from '../components/Section'

const RUNS_KEY = ['automation-runs']
const NOTIFICATIONS_KEY = ['notifications']

function statusColor(status: string): string {
  if (status === 'completed') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
  if (status === 'failed') return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
}

function RunRow({ run }: { run: AutomationRun }) {
  const [expanded, setExpanded] = useState(false)
  const { data: detail } = useQuery({
    queryKey: ['automation-run', run.id],
    queryFn: () => automationApi.getRun(run.id),
    enabled: expanded,
  })

  return (
    <li className="rounded-md border border-gray-200 p-3 text-sm dark:border-gray-800">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-medium capitalize">{run.run_type}</span>
          <span className="ml-2 text-xs text-gray-500">{run.triggered_by}</span>
          <span className="ml-2 text-xs text-gray-500">{new Date(run.started_at).toLocaleString()}</span>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(run.status)}`}>{run.status}</span>
      </div>
      <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">
        {Object.entries(run.summary)
          .map(([k, v]) => `${k}: ${v}`)
          .join(' · ')}
      </p>
      <button onClick={() => setExpanded((v) => !v)} className="mt-1 text-xs text-indigo-600">
        {expanded ? 'Hide steps' : 'Show steps'}
      </button>
      {expanded && detail && (
        <ul className="mt-2 flex flex-col gap-1 border-t border-gray-100 pt-2 text-xs dark:border-gray-800">
          {detail.steps.map((s, i) => (
            <li key={i} className={s.status === 'failed' ? 'text-red-600' : 'text-gray-600 dark:text-gray-400'}>
              {s.step_name} — {s.status}
              {s.error && `: ${s.error}`}
            </li>
          ))}
          {detail.steps.length === 0 && <li className="text-gray-500">No steps recorded.</li>}
        </ul>
      )}
    </li>
  )
}

function RunHistory() {
  const queryClient = useQueryClient()
  const { data: runs, isLoading } = useQuery({ queryKey: RUNS_KEY, queryFn: () => automationApi.listRuns() })

  const discoveryMutation = useMutation({
    mutationFn: () => automationApi.runDiscovery(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RUNS_KEY }),
  })
  const digestMutation = useMutation({
    mutationFn: () => automationApi.runDigest(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: RUNS_KEY })
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY })
    },
  })

  return (
    <Section title="Automation runs">
      <div className="mb-4 flex gap-3">
        <button
          onClick={() => discoveryMutation.mutate()}
          disabled={discoveryMutation.isPending}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {discoveryMutation.isPending ? 'Running…' : 'Run discovery now'}
        </button>
        <button
          onClick={() => digestMutation.mutate()}
          disabled={digestMutation.isPending}
          className="rounded-md bg-gray-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {digestMutation.isPending ? 'Generating…' : 'Generate digest now'}
        </button>
      </div>

      {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {!isLoading && (runs ?? []).length === 0 && <p className="text-sm text-gray-500">No automation runs yet.</p>}
      <ul className="flex flex-col gap-2">
        {(runs ?? []).map((run) => (
          <RunRow key={run.id} run={run} />
        ))}
      </ul>
    </Section>
  )
}

function Notifications() {
  const queryClient = useQueryClient()
  const { data: notifications, isLoading } = useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: () => notificationsApi.list(),
  })

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  })
  const markAllReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  })

  const unreadCount = (notifications ?? []).filter((n) => !n.read).length

  return (
    <Section title="Notifications">
      {unreadCount > 0 && (
        <button onClick={() => markAllReadMutation.mutate()} className="mb-3 text-xs text-indigo-600">
          Mark all {unreadCount} as read
        </button>
      )}
      {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {!isLoading && (notifications ?? []).length === 0 && <p className="text-sm text-gray-500">No notifications yet.</p>}
      <ul className="flex flex-col gap-2">
        {(notifications ?? []).map((n) => (
          <li
            key={n.id}
            className={`rounded-md border p-3 text-sm ${n.read ? 'border-gray-100 dark:border-gray-800' : 'border-indigo-300'}`}
          >
            <p className="font-medium">{n.title}</p>
            <p className="whitespace-pre-wrap text-xs text-gray-600 dark:text-gray-400">{n.body}</p>
            <div className="mt-1 flex items-center justify-between">
              <span className="text-xs text-gray-400">{new Date(n.created_at).toLocaleString()}</span>
              {!n.read && (
                <button onClick={() => markReadMutation.mutate(n.id)} className="text-xs text-indigo-600">
                  Mark read
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Section>
  )
}

export default function AutomationCenter() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Automation Center</h1>
      <RunHistory />
      <Notifications />
    </div>
  )
}
