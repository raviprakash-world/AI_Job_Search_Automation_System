import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { jobSourcesApi, jobsApi } from '../api/endpoints'
import { ApiError } from '../api/client'
import type { DiscoveryResult, Job, Provider, SavedStatus } from '../api/types'
import Section from '../components/Section'

const SOURCES_KEY = ['job-sources']
const JOBS_KEY = ['jobs']

function AddSourceForm() {
  const queryClient = useQueryClient()
  const [provider, setProvider] = useState<Provider>('greenhouse')
  const [slug, setSlug] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => jobSourcesApi.create(provider, slug, displayName || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SOURCES_KEY })
      setSlug('')
      setDisplayName('')
      setError(null)
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : 'Failed to add company'),
  })

  return (
    <form
      onSubmit={(e: FormEvent) => {
        e.preventDefault()
        if (slug) mutation.mutate()
      }}
      className="flex flex-wrap gap-2"
    >
      <select
        value={provider}
        onChange={(e) => setProvider(e.target.value as Provider)}
        className="rounded-md border border-gray-300 px-2 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
      >
        <option value="greenhouse">Greenhouse</option>
        <option value="lever">Lever</option>
      </select>
      <input
        placeholder="Board slug (e.g. figma)"
        value={slug}
        onChange={(e) => setSlug(e.target.value)}
        className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
      />
      <input
        placeholder="Display name (optional)"
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
      />
      <button type="submit" className="rounded-md bg-gray-800 px-3 py-1.5 text-sm text-white">
        Track
      </button>
      {error && <p className="w-full text-xs text-red-600">{error}</p>}
    </form>
  )
}

function TrackedSources() {
  const queryClient = useQueryClient()
  const { data: sources } = useQuery({ queryKey: SOURCES_KEY, queryFn: jobSourcesApi.list })
  const [discovering, setDiscovering] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<Record<string, DiscoveryResult>>({})

  const removeMutation = useMutation({
    mutationFn: (id: string) => jobSourcesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SOURCES_KEY }),
  })

  async function handleDiscover(id: string) {
    setDiscovering(id)
    try {
      const result = await jobSourcesApi.discover(id)
      setLastResult((prev) => ({ ...prev, [id]: result }))
      queryClient.invalidateQueries({ queryKey: JOBS_KEY })
      queryClient.invalidateQueries({ queryKey: SOURCES_KEY })
    } finally {
      setDiscovering(null)
    }
  }

  return (
    <Section title="Tracked companies">
      <AddSourceForm />
      <ul className="mt-4 flex flex-col gap-2">
        {(sources ?? []).map((source) => (
          <li key={source.id} className="flex items-center justify-between rounded-md border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
            <div>
              <span className="font-medium">{source.display_name || source.company_slug}</span>
              <span className="ml-2 text-xs text-gray-500">{source.provider}</span>
              {lastResult[source.id] && (
                <span className="ml-2 text-xs text-gray-500">
                  — fetched {lastResult[source.id].fetched}, new {lastResult[source.id].new_jobs}, matched{' '}
                  {lastResult[source.id].matched}
                </span>
              )}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => handleDiscover(source.id)}
                disabled={discovering === source.id}
                className="text-xs font-medium text-indigo-600 disabled:opacity-50"
              >
                {discovering === source.id ? 'Discovering…' : 'Discover jobs'}
              </button>
              <button onClick={() => removeMutation.mutate(source.id)} className="text-xs text-red-600">
                Remove
              </button>
            </div>
          </li>
        ))}
        {(sources ?? []).length === 0 && (
          <p className="text-sm text-gray-500">No companies tracked yet. Add a Greenhouse or Lever board slug above.</p>
        )}
      </ul>
    </Section>
  )
}

function fitScoreColor(score: number): string {
  if (score >= 90) return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
  if (score >= 80) return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
  if (score >= 70) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
}

function JobCard({ job }: { job: Job }) {
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)

  const actionMutation = useMutation({
    mutationFn: (action: 'shortlist' | 'save_for_later' | 'reject' | 'ignore') => jobsApi.act(job.id, action),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: JOBS_KEY }),
  })

  return (
    <li className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-medium text-gray-900 dark:text-gray-100">{job.title}</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {job.company_name} {job.location ? `· ${job.location}` : ''} {job.remote_status ? `· ${job.remote_status}` : ''}
          </p>
          {job.saved_status && (
            <span className="mt-1 inline-block rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              {job.saved_status.replace(/_/g, ' ')}
            </span>
          )}
        </div>
        {job.match && (
          <span className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold ${fitScoreColor(job.match.fit_score)}`}>
            {Math.round(job.match.fit_score)}%
          </span>
        )}
      </div>

      {job.match && (
        <>
          <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">{job.match.summary}</p>
          <button onClick={() => setExpanded((v) => !v)} className="mt-1 text-xs text-indigo-600">
            {expanded ? 'Hide details' : 'Show match details'}
          </button>
          {expanded && (
            <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="mb-1 font-semibold text-green-700 dark:text-green-400">Strong matches</p>
                <ul className="list-disc pl-4 text-gray-700 dark:text-gray-300">
                  {job.match.strong_matches.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                  {job.match.strong_matches.length === 0 && <li className="list-none text-gray-500">None</li>}
                </ul>
              </div>
              <div>
                <p className="mb-1 font-semibold text-amber-700 dark:text-amber-400">Gaps</p>
                <ul className="list-disc pl-4 text-gray-700 dark:text-gray-300">
                  {job.match.gaps.map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                  {job.match.gaps.length === 0 && <li className="list-none text-gray-500">None</li>}
                </ul>
              </div>
              {job.match.hard_disqualifiers.length > 0 && (
                <div className="col-span-2">
                  <p className="mb-1 font-semibold text-red-700 dark:text-red-400">Flagged</p>
                  <ul className="list-disc pl-4 text-gray-700 dark:text-gray-300">
                    {job.match.hard_disqualifiers.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {job.posting_url && (
          <a href={job.posting_url} target="_blank" rel="noreferrer" className="text-xs text-indigo-600">
            View posting
          </a>
        )}
        <button onClick={() => actionMutation.mutate('shortlist')} className="text-xs font-medium text-green-700">
          Shortlist
        </button>
        <button onClick={() => actionMutation.mutate('save_for_later')} className="text-xs text-gray-600">
          Save for later
        </button>
        <button onClick={() => actionMutation.mutate('reject')} className="text-xs text-red-600">
          Reject
        </button>
        <button onClick={() => actionMutation.mutate('ignore')} className="text-xs text-gray-400">
          Ignore
        </button>
        <Link to={`/resumes?jobId=${job.id}`} className="text-xs font-medium text-indigo-600">
          Tailor resume
        </Link>
        <Link to={`/applications/new?jobId=${job.id}`} className="text-xs font-medium text-indigo-600">
          Prepare application
        </Link>
      </div>
    </li>
  )
}

function JobList() {
  const [minScore, setMinScore] = useState<number | ''>('')
  const [savedStatus, setSavedStatus] = useState<SavedStatus | ''>('')

  const { data: jobs, isLoading } = useQuery({
    queryKey: [...JOBS_KEY, minScore, savedStatus],
    queryFn: () => jobsApi.list({ min_score: minScore === '' ? undefined : minScore, saved_status: savedStatus || undefined }),
  })

  return (
    <Section title="Discovered jobs">
      <div className="mb-4 flex gap-3">
        <input
          type="number"
          placeholder="Min fit score"
          value={minScore}
          onChange={(e) => setMinScore(e.target.value === '' ? '' : Number(e.target.value))}
          className="w-36 rounded-md border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
        />
        <select
          value={savedStatus}
          onChange={(e) => setSavedStatus(e.target.value as SavedStatus | '')}
          className="rounded-md border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
        >
          <option value="">All statuses</option>
          <option value="shortlisted">Shortlisted</option>
          <option value="saved_for_later">Saved for later</option>
          <option value="rejected">Rejected</option>
          <option value="ignored">Ignored</option>
        </select>
      </div>

      {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {!isLoading && (jobs ?? []).length === 0 && (
        <p className="text-sm text-gray-500">No jobs yet. Track a company above and click "Discover jobs".</p>
      )}
      <ul className="flex flex-col gap-3">
        {(jobs ?? []).map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
      </ul>
    </Section>
  )
}

export default function JobDiscovery() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Job Discovery</h1>
      <TrackedSources />
      <JobList />
    </div>
  )
}
