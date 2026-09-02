import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { dashboardApi, jobsApi } from '../api/endpoints'
import type { ActivityItem, AlertItem, DashboardPipeline } from '../api/types'
import Section from '../components/Section'

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">{value}</p>
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
    </div>
  )
}

const PIPELINE_STAGES: { key: keyof DashboardPipeline; label: string }[] = [
  { key: 'discovered', label: 'Discovered' },
  { key: 'shortlisted', label: 'Shortlisted' },
  { key: 'prepared', label: 'Prepared' },
  { key: 'applied', label: 'Applied' },
  { key: 'interview', label: 'Interview' },
  { key: 'offer', label: 'Offer' },
]

function PipelineFunnel({ pipeline }: { pipeline: DashboardPipeline }) {
  const max = Math.max(1, ...PIPELINE_STAGES.map((s) => pipeline[s.key]))
  return (
    <div className="flex flex-col gap-2">
      {PIPELINE_STAGES.map((stage) => {
        const value = pipeline[stage.key]
        const widthPct = Math.max(4, (value / max) * 100)
        return (
          <div key={stage.key} className="flex items-center gap-3">
            <span className="w-20 shrink-0 text-xs text-gray-600 dark:text-gray-400">{stage.label}</span>
            <div className="h-6 flex-1 rounded bg-gray-100 dark:bg-gray-800">
              <div
                className="flex h-6 items-center justify-end rounded bg-indigo-600 pr-2 text-xs font-medium text-white transition-all"
                style={{ width: `${widthPct}%` }}
              >
                {value}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function activityDotClass(status: ActivityItem['status']): string {
  if (status === 'error') return 'bg-red-500'
  if (status === 'success') return 'bg-green-500'
  return 'bg-gray-400'
}

function ActivityFeed() {
  const { data: activity, isLoading } = useQuery({ queryKey: ['dashboard-activity'], queryFn: () => dashboardApi.activity(20) })

  return (
    <Section title="Recent activity">
      {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {!isLoading && (activity ?? []).length === 0 && <p className="text-sm text-gray-500">No activity yet.</p>}
      <ul className="flex flex-col gap-2">
        {(activity ?? []).map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${activityDotClass(item.status)}`} />
            <div>
              <p className="text-gray-800 dark:text-gray-200">{item.title}</p>
              <p className="text-xs text-gray-500">
                {item.detail && `${item.detail} · `}
                {new Date(item.created_at).toLocaleString()}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  )
}

function alertHref(alert: AlertItem): string {
  if (alert.link.kind === 'application') return `/applications/${alert.link.id}`
  return '/resumes'
}

function Alerts() {
  const { data: alerts, isLoading } = useQuery({ queryKey: ['dashboard-alerts'], queryFn: dashboardApi.alerts })

  return (
    <Section title="Needs your attention">
      {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {!isLoading && (alerts ?? []).length === 0 && <p className="text-sm text-gray-500">Nothing needs attention right now.</p>}
      <ul className="flex flex-col gap-2">
        {(alerts ?? []).map((alert, i) => (
          <li key={i}>
            <Link
              to={alertHref(alert)}
              className="block rounded-md border border-amber-300 p-3 text-sm hover:bg-amber-50 dark:hover:bg-amber-950/20"
            >
              <p className="font-medium text-amber-800 dark:text-amber-400">{alert.title}</p>
              <p className="text-xs text-gray-600 dark:text-gray-400">{alert.detail}</p>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  )
}

function TopMatches() {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['dashboard-top-matches'],
    queryFn: () => jobsApi.list({ min_score: 1 }),
  })
  const top = (jobs ?? []).slice(0, 5)

  return (
    <Section title="Top matches">
      {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {!isLoading && top.length === 0 && (
        <p className="text-sm text-gray-500">
          No scored jobs yet. Track a company in{' '}
          <Link to="/jobs" className="text-indigo-600">
            Job Discovery
          </Link>
          .
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {top.map((job) => (
          <li key={job.id} className="flex items-center justify-between text-sm">
            <span>
              {job.title} {job.company_name && `· ${job.company_name}`}
            </span>
            <span className="font-semibold text-indigo-600">{Math.round(job.match?.fit_score ?? 0)}%</span>
          </li>
        ))}
      </ul>
      {top.length > 0 && (
        <Link to="/jobs" className="mt-3 inline-block text-xs text-indigo-600">
          View all in Job Discovery
        </Link>
      )}
    </Section>
  )
}

export default function Dashboard() {
  const { data: overview, isLoading } = useQuery({ queryKey: ['dashboard-overview'], queryFn: dashboardApi.overview })

  if (isLoading || !overview) return <div className="p-6 text-gray-500">Loading…</div>

  const { summary, pipeline } = overview

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Dashboard</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Jobs discovered" value={String(summary.jobs_discovered)} />
        <StatTile label="Shortlisted" value={String(summary.jobs_shortlisted)} />
        <StatTile label="Applications submitted" value={String(summary.applications_submitted)} />
        <StatTile label="Interviews" value={String(summary.interviews)} />
        <StatTile label="Offers" value={String(summary.offers)} />
        <StatTile label="Rejections" value={String(summary.rejections)} />
        <StatTile label="Response rate" value={`${Math.round(summary.response_rate * 100)}%`} />
        <StatTile label="Rejection rate" value={`${Math.round(summary.rejection_rate * 100)}%`} />
      </div>

      <Section title="Pipeline">
        <PipelineFunnel pipeline={pipeline} />
      </Section>

      <TopMatches />
      <Alerts />
      <ActivityFeed />
    </div>
  )
}
