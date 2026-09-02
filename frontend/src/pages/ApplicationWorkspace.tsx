import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { applicationsApi, jobsApi, resumesApi } from '../api/endpoints'
import type { ApplicationAnswer, ApplicationDetail, OutcomeStatus } from '../api/types'
import Section from '../components/Section'

function statusBadgeClass(status: string): string {
  if (status === 'ready_for_review' || status === 'approved' || status === 'staged')
    return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
  if (status === 'submitted' || status === 'interview' || status === 'offer')
    return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
  if (status === 'error' || status === 'rejected' || status === 'submission_blocked')
    return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
}

function StagingScreenshot({ applicationId }: { applicationId: string }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    applicationsApi.stagingScreenshotBlob(applicationId).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      setImageUrl(objectUrl)
    })
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [applicationId])

  if (!imageUrl) return <p className="text-xs text-gray-500">Loading screenshot…</p>
  return <img src={imageUrl} alt="Staged application form" className="w-full rounded-md border border-gray-200 dark:border-gray-800" />
}

function AnswerRow({ applicationId, answer }: { applicationId: string; answer: ApplicationAnswer }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState(answer.answer ?? '')
  const needsReview = !answer.is_grounded && !answer.reviewed

  const mutation = useMutation({
    mutationFn: () => applicationsApi.reviewAnswer(applicationId, answer.id, draft),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['application', applicationId] }),
  })

  return (
    <li className={`rounded-md border p-3 text-sm ${needsReview ? 'border-amber-400' : 'border-gray-200 dark:border-gray-800'}`}>
      <p className="font-medium text-gray-800 dark:text-gray-200">{answer.question}</p>
      {needsReview && (
        <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
          ⚠ Could not answer truthfully from your profile: {answer.flag_reason}. Please fill this in yourself.
        </p>
      )}
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={2}
        className="mt-2 w-full rounded-md border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
      />
      <button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="mt-1 text-xs text-indigo-600 disabled:opacity-50"
      >
        {answer.reviewed ? 'Update' : 'Confirm answer'}
      </button>
    </li>
  )
}

export default function ApplicationWorkspace() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: application, isLoading } = useQuery({
    queryKey: ['application', id],
    queryFn: () => applicationsApi.get(id!),
    enabled: !!id,
  })
  const { data: job } = useQuery({
    queryKey: ['job', application?.job_id],
    queryFn: () => jobsApi.get(application!.job_id),
    enabled: !!application,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['application', id] })
  const retryMutation = useMutation({ mutationFn: () => applicationsApi.retryPreparation(id!), onSuccess: invalidate })
  const approveMutation = useMutation({ mutationFn: () => applicationsApi.approve(id!), onSuccess: invalidate })
  const stageMutation = useMutation({ mutationFn: () => applicationsApi.stage(id!), onSuccess: invalidate })
  const submitMutation = useMutation({ mutationFn: () => applicationsApi.markSubmitted(id!), onSuccess: invalidate })
  const outcomeMutation = useMutation({
    mutationFn: (status: OutcomeStatus) => applicationsApi.updateStatus(id!, status),
    onSuccess: invalidate,
  })
  const deleteMutation = useMutation({
    mutationFn: () => applicationsApi.remove(id!),
    onSuccess: () => navigate('/applications'),
  })

  if (isLoading || !application) return <div className="p-6 text-gray-500">Loading…</div>

  const app: ApplicationDetail = application

  async function downloadResume() {
    if (!app.resume_version) return
    const blob = await resumesApi.downloadBlob(app.resume_version.resume_id, app.resume_version.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'resume.docx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  async function downloadCoverLetter() {
    const blob = await applicationsApi.downloadCoverLetterBlob(app.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'cover_letter.docx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
            {app.job_title} {app.company_name && `· ${app.company_name}`}
          </h1>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-semibold ${statusBadgeClass(app.status)}`}>
          {app.status.replace(/_/g, ' ')}
        </span>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-6">
          <Section title="Job & match">
            {job?.match && (
              <p className="mb-2 text-sm text-gray-700 dark:text-gray-300">
                Fit score: <span className="font-semibold">{Math.round(job.match.fit_score)}%</span> — {job.match.summary}
              </p>
            )}
            {job?.posting_url && (
              <a href={job.posting_url} target="_blank" rel="noreferrer" className="text-xs text-indigo-600">
                View original posting
              </a>
            )}
          </Section>

          <Section title="Gate results">
            <ul className="flex flex-col gap-2 text-sm">
              {app.gate_report.gates.map((gate) => (
                <li key={gate.name} className="flex items-start gap-2">
                  <span className={gate.passed ? 'text-green-600' : 'text-red-600'}>{gate.passed ? '✓' : '✗'}</span>
                  <span>
                    {gate.message}
                    {gate.overridden && <span className="ml-1 text-xs text-amber-600">(overridden)</span>}
                  </span>
                </li>
              ))}
            </ul>
            {app.status === 'error' && (
              <button
                onClick={() => retryMutation.mutate()}
                disabled={retryMutation.isPending}
                className="mt-3 text-xs font-medium text-indigo-600 disabled:opacity-50"
              >
                {retryMutation.isPending ? 'Retrying…' : 'Retry preparation'}
              </button>
            )}
          </Section>

          <Section title="Timeline">
            <ul className="flex flex-col gap-1 text-xs text-gray-600 dark:text-gray-400">
              {app.events.map((e, i) => (
                <li key={i}>
                  {new Date(e.created_at).toLocaleString()} — {e.from_status ?? 'created'} → {e.to_status}
                  {e.note && <span className="text-gray-400"> ({e.note})</span>}
                </li>
              ))}
            </ul>
          </Section>
        </div>

        <div className="flex flex-col gap-6">
          <Section title="Actions">
            <div className="flex flex-wrap gap-3">
              {app.status === 'ready_for_review' && (
                <button
                  onClick={() => approveMutation.mutate()}
                  disabled={approveMutation.isPending}
                  className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  Approve
                </button>
              )}
              {(app.status === 'approved' || app.status === 'submission_blocked') && (
                <button
                  onClick={() => stageMutation.mutate()}
                  disabled={stageMutation.isPending}
                  className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {stageMutation.isPending
                    ? 'Filling out the real application form…'
                    : app.status === 'submission_blocked'
                      ? 'Retry staging'
                      : 'Stage on employer site'}
                </button>
              )}
              {['approved', 'staged', 'submission_blocked'].includes(app.status) && (
                <button
                  onClick={() => submitMutation.mutate()}
                  disabled={submitMutation.isPending}
                  className="rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
                >
                  Mark as submitted (after you click submit on the company site)
                </button>
              )}
              {['submitted', 'interview', 'offer'].includes(app.status) && (
                <>
                  <button onClick={() => outcomeMutation.mutate('interview')} className="text-sm text-blue-700">
                    Interview
                  </button>
                  <button onClick={() => outcomeMutation.mutate('offer')} className="text-sm text-green-700">
                    Offer
                  </button>
                  <button onClick={() => outcomeMutation.mutate('rejected')} className="text-sm text-red-700">
                    Rejected
                  </button>
                </>
              )}
              {app.status !== 'submitted' && (
                <button onClick={() => outcomeMutation.mutate('withdrawn')} className="text-sm text-gray-500">
                  Withdraw
                </button>
              )}
              {app.status !== 'submitted' && (
                <button onClick={() => deleteMutation.mutate()} className="text-sm text-red-600">
                  Delete
                </button>
              )}
            </div>
          </Section>

          {(app.status === 'staged' || app.status === 'submission_blocked' || app.has_staged_screenshot) && (
            <Section title="Staging">
              {app.status === 'submission_blocked' && app.staging_notes.blocked_reason && (
                <p className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/30 dark:text-red-400">
                  Staging stopped: {app.staging_notes.blocked_reason}. {job?.posting_url && 'You can still apply manually.'}
                </p>
              )}
              {app.status === 'staged' && (
                <p className="mb-3 text-sm text-gray-700 dark:text-gray-300">
                  The real application form has been filled out below. Review it, then open the application page and
                  click Submit yourself — nothing has been sent to the employer yet.
                </p>
              )}
              {job?.posting_url && (
                <a
                  href={job.posting_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mb-3 inline-block text-xs font-medium text-indigo-600"
                >
                  Open the application page →
                </a>
              )}
              {app.staging_notes.fields_filled.length > 0 && (
                <div className="mb-2">
                  <p className="text-xs font-semibold text-green-700 dark:text-green-400">Filled automatically</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">{app.staging_notes.fields_filled.join(', ')}</p>
                </div>
              )}
              {app.staging_notes.fields_needing_manual_input.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs font-semibold text-amber-700 dark:text-amber-400">Needs your input on the real page</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    {app.staging_notes.fields_needing_manual_input.join(', ')}
                  </p>
                </div>
              )}
              {app.has_staged_screenshot && <StagingScreenshot applicationId={app.id} />}
            </Section>
          )}

          {app.resume_version && (
            <Section title="Resume">
              <p className="mb-2 italic text-sm text-gray-700 dark:text-gray-300">
                {app.resume_version.structured_content.professional_summary}
              </p>
              <button onClick={downloadResume} className="text-xs text-indigo-600">
                Download .docx
              </button>
            </Section>
          )}

          {app.cover_letter_version && (
            <Section title="Cover letter">
              <p className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                {app.cover_letter_version.body_text}
              </p>
              <button onClick={downloadCoverLetter} className="mt-2 text-xs text-indigo-600">
                Download .docx
              </button>
            </Section>
          )}

          {app.answers.length > 0 && (
            <Section title="Application answers">
              <ul className="flex flex-col gap-3">
                {app.answers.map((a) => (
                  <AnswerRow key={a.id} applicationId={app.id} answer={a} />
                ))}
              </ul>
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}
