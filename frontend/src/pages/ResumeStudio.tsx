import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { resumesApi } from '../api/endpoints'
import { ApiError } from '../api/client'
import type { Resume, ResumeVersion, ResumeVersionStatus } from '../api/types'
import Section from '../components/Section'

const RESUMES_KEY = ['resumes']

function statusBadgeClass(status: ResumeVersionStatus): string {
  switch (status) {
    case 'ready':
      return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
    case 'qa_failed':
      return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
    case 'generation_failed':
      return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
  }
}

function statusLabel(status: ResumeVersionStatus): string {
  return { ready: 'Ready', qa_failed: 'Needs review', generation_failed: 'Generation failed' }[status]
}

async function triggerDownload(resumeId: string, version: ResumeVersion) {
  const blob = await resumesApi.downloadBlob(resumeId, version.id)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `resume_v${version.version_number}.docx`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function GenerateResumeForm() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const jobId = searchParams.get('jobId') ?? ''
  const [label, setLabel] = useState('')
  const [includeProjects, setIncludeProjects] = useState(true)
  const [includeCertifications, setIncludeCertifications] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      resumesApi.create({
        job_id: jobId || undefined,
        label: label || undefined,
        include_projects: includeProjects,
        include_certifications: includeCertifications,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: RESUMES_KEY })
      setLabel('')
      setError(null)
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : 'Failed to generate resume'),
  })

  return (
    <Section title="Generate a resume">
      {jobId && (
        <p className="mb-3 text-sm text-gray-600 dark:text-gray-400">
          Tailoring to a specific job.{' '}
          <button onClick={() => setSearchParams({})} className="text-indigo-600">
            Clear
          </button>
        </p>
      )}
      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          mutation.mutate()
        }}
        className="flex flex-col gap-3"
      >
        <input
          placeholder="Label (optional)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
        />
        <div className="flex gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeProjects} onChange={(e) => setIncludeProjects(e.target.checked)} />
            Include projects
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeCertifications}
              onChange={(e) => setIncludeCertifications(e.target.checked)}
            />
            Include certifications
          </label>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-fit rounded-md bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {mutation.isPending ? 'Generating…' : 'Generate resume'}
        </button>
      </form>
    </Section>
  )
}

function ResumeCard({ resume }: { resume: Resume }) {
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)

  const regenerateMutation = useMutation({
    mutationFn: () => resumesApi.regenerate(resume.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RESUMES_KEY }),
  })
  const deleteMutation = useMutation({
    mutationFn: () => resumesApi.remove(resume.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RESUMES_KEY }),
  })

  const latest = resume.latest_version

  return (
    <li className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-medium text-gray-900 dark:text-gray-100">{resume.label}</p>
          {latest && <p className="text-xs text-gray-500">Version {latest.version_number}</p>}
        </div>
        {latest && (
          <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${statusBadgeClass(latest.status)}`}>
            {statusLabel(latest.status)}
          </span>
        )}
      </div>

      {latest && latest.qa_report.ats_keyword_coverage != null && (
        <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
          ATS keyword coverage: {latest.qa_report.ats_keyword_coverage}%
        </p>
      )}

      {latest && (latest.qa_report.errors.length > 0 || latest.qa_report.warnings.length > 0) && (
        <div className="mt-2 text-xs">
          {latest.qa_report.errors.map((e) => (
            <p key={e} className="text-red-600">
              ⚠ {e}
            </p>
          ))}
          {latest.qa_report.warnings.map((w) => (
            <p key={w} className="text-amber-600">
              ⚠ {w}
            </p>
          ))}
        </div>
      )}

      {latest && latest.status !== 'generation_failed' && (
        <button onClick={() => setExpanded((v) => !v)} className="mt-2 text-xs text-indigo-600">
          {expanded ? 'Hide preview' : 'Show preview'}
        </button>
      )}

      {expanded && latest && latest.status !== 'generation_failed' && (
        <div className="mt-3 rounded-md bg-gray-50 p-3 text-sm dark:bg-gray-900">
          <p className="mb-2 italic text-gray-700 dark:text-gray-300">{latest.structured_content.professional_summary}</p>
          <p className="mb-2 text-gray-600 dark:text-gray-400">
            <span className="font-semibold">Skills: </span>
            {latest.structured_content.skills.join(', ')}
          </p>
          {latest.structured_content.experiences.map((exp) => (
            <div key={exp.experience_id} className="mb-2">
              <p className="font-semibold">
                {exp.title} — {exp.company}
              </p>
              <ul className="list-disc pl-5 text-gray-700 dark:text-gray-300">
                {exp.bullets.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-3">
        {latest && latest.status !== 'generation_failed' && (
          <button onClick={() => triggerDownload(resume.id, latest)} className="text-xs font-medium text-indigo-600">
            Download .docx
          </button>
        )}
        <button
          onClick={() => regenerateMutation.mutate()}
          disabled={regenerateMutation.isPending}
          className="text-xs text-gray-600 disabled:opacity-50"
        >
          {regenerateMutation.isPending ? 'Regenerating…' : 'Regenerate'}
        </button>
        <button onClick={() => deleteMutation.mutate()} className="text-xs text-red-600">
          Delete
        </button>
      </div>
    </li>
  )
}

export default function ResumeStudio() {
  const { data: resumes, isLoading } = useQuery({ queryKey: RESUMES_KEY, queryFn: resumesApi.list })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Resume Studio</h1>
      <GenerateResumeForm />
      <Section title="Your resumes">
        {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
        {!isLoading && (resumes ?? []).length === 0 && (
          <p className="text-sm text-gray-500">No resumes yet. Generate one above.</p>
        )}
        <ul className="flex flex-col gap-3">
          {(resumes ?? []).map((resume) => (
            <ResumeCard key={resume.id} resume={resume} />
          ))}
        </ul>
      </Section>
    </div>
  )
}
