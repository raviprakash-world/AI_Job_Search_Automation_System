import { useState, type FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { applicationsApi, resumesApi } from '../api/endpoints'
import { ApiError } from '../api/client'
import Section from '../components/Section'

export default function NewApplication() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const jobId = searchParams.get('jobId') ?? ''

  const { data: resumes, isLoading } = useQuery({ queryKey: ['resumes'], queryFn: resumesApi.list })
  const resumesForJob = (resumes ?? []).filter((r) => r.job_id === jobId && r.latest_version?.status === 'ready')

  const [resumeVersionId, setResumeVersionId] = useState('')
  const [generateCoverLetter, setGenerateCoverLetter] = useState(true)
  const [questions, setQuestions] = useState<string[]>([])
  const [draftQuestion, setDraftQuestion] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      applicationsApi.create({
        job_id: jobId,
        resume_version_id: resumeVersionId,
        generate_cover_letter: generateCoverLetter,
        custom_questions: questions,
      }),
    onSuccess: (application) => navigate(`/applications/${application.id}`),
    onError: (err) => setError(err instanceof ApiError ? err.message : 'Failed to prepare application'),
  })

  if (!jobId) {
    return <div className="p-6 text-gray-500">Start this from a job in Job Discovery.</div>
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Prepare an application</h1>

      <Section title="Resume">
        {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
        {!isLoading && resumesForJob.length === 0 && (
          <p className="text-sm text-gray-600 dark:text-gray-400">
            No ready resume tailored to this job yet.{' '}
            <Link to={`/resumes?jobId=${jobId}`} className="text-indigo-600">
              Generate one first
            </Link>
            .
          </p>
        )}
        {resumesForJob.length > 0 && (
          <select
            value={resumeVersionId}
            onChange={(e) => setResumeVersionId(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
          >
            <option value="">Select a resume version…</option>
            {resumesForJob.map((r) => (
              <option key={r.id} value={r.latest_version!.id}>
                {r.label} (v{r.latest_version!.version_number})
              </option>
            ))}
          </select>
        )}
      </Section>

      <Section title="Cover letter">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={generateCoverLetter} onChange={(e) => setGenerateCoverLetter(e.target.checked)} />
          Generate a tailored cover letter
        </label>
      </Section>

      <Section title="Custom application questions (optional)">
        <p className="mb-3 text-sm text-gray-600 dark:text-gray-400">
          Add any questions the application form asks. We'll answer them from your profile where we truthfully can,
          and flag anything we can't for you to fill in yourself.
        </p>
        <ul className="mb-3 flex flex-col gap-2">
          {questions.map((q, i) => (
            <li key={q} className="flex items-center justify-between text-sm">
              <span>{q}</span>
              <button onClick={() => setQuestions(questions.filter((_, idx) => idx !== i))} className="text-xs text-red-600">
                Remove
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <input
            value={draftQuestion}
            onChange={(e) => setDraftQuestion(e.target.value)}
            placeholder="e.g. Why do you want to work here?"
            className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
          />
          <button
            onClick={() => {
              if (draftQuestion.trim()) {
                setQuestions([...questions, draftQuestion.trim()])
                setDraftQuestion('')
              }
            }}
            className="rounded-md bg-gray-800 px-3 py-1.5 text-sm text-white"
          >
            Add
          </button>
        </div>
      </Section>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          if (resumeVersionId) mutation.mutate()
        }}
      >
        <button
          type="submit"
          disabled={!resumeVersionId || mutation.isPending}
          className="w-fit rounded-md bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {mutation.isPending ? 'Preparing…' : 'Prepare application'}
        </button>
      </form>
    </div>
  )
}
