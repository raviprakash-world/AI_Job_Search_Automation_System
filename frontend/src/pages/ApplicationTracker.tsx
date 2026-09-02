import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { applicationsApi } from '../api/endpoints'
import type { ApplicationStatus } from '../api/types'
import Section from '../components/Section'

const STATUSES: ApplicationStatus[] = [
  'preparing',
  'ready_for_review',
  'approved',
  'submitted',
  'interview',
  'offer',
  'rejected',
  'withdrawn',
  'error',
]

function statusColor(status: string): string {
  if (['ready_for_review', 'approved'].includes(status)) return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
  if (['submitted', 'interview', 'offer'].includes(status))
    return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
  if (['error', 'rejected'].includes(status)) return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
}

export default function ApplicationTracker() {
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | ''>('')
  const { data: applications, isLoading } = useQuery({ queryKey: ['applications'], queryFn: applicationsApi.list })

  const filtered = (applications ?? []).filter((a) => !statusFilter || a.status === statusFilter)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Application Tracker</h1>

      <Section title="Applications">
        <div className="mb-4">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ApplicationStatus | '')}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>

        {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
        {!isLoading && filtered.length === 0 && (
          <p className="text-sm text-gray-500">No applications yet. Prepare one from a job in Job Discovery.</p>
        )}
        <ul className="flex flex-col gap-2">
          {filtered.map((a) => (
            <li key={a.id}>
              <Link
                to={`/applications/${a.id}`}
                className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-900"
              >
                <span>
                  {a.job_title} {a.company_name && `· ${a.company_name}`}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(a.status)}`}>
                  {a.status.replace(/_/g, ' ')}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}
