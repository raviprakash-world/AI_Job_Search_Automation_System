import { useState } from 'react'
import type { ProfileChange, ProfileExtraction } from '../api/types'

type Decision = 'accept' | 'reject' | null

function describeChange(change: ProfileChange): string {
  switch (change.kind) {
    case 'field_update':
      return `Field: ${change.field}`
    case 'new_experience':
      return 'New work experience found in document'
    case 'new_education':
      return 'New education entry found in document'
    case 'new_skill':
      return 'New skill found in document'
    case 'new_certification':
      return 'New certification found in document'
    case 'new_project':
      return 'New project found in document'
    default:
      return change.kind
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '(empty)'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

interface Props {
  extraction: ProfileExtraction
  onSubmit: (resolutions: { change_id: string; action: 'accept' | 'reject' }[]) => Promise<void>
  onClose: () => void
}

export default function ExtractionReviewModal({ extraction, onSubmit, onClose }: Props) {
  const [decisions, setDecisions] = useState<Record<string, Decision>>({})
  const [submitting, setSubmitting] = useState(false)

  const decidedCount = Object.values(decisions).filter(Boolean).length

  function setDecision(changeId: string, action: Decision) {
    setDecisions((prev) => ({ ...prev, [changeId]: action }))
  }

  async function handleSubmit() {
    const resolutions = Object.entries(decisions)
      .filter((entry): entry is [string, 'accept' | 'reject'] => entry[1] !== null)
      .map(([change_id, action]) => ({ change_id, action }))

    if (resolutions.length === 0) return
    setSubmitting(true)
    try {
      await onSubmit(resolutions)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl dark:bg-gray-900">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Review extracted profile data</h2>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Nothing below has been applied to your Master Profile yet. Accept or reject each item — the system never
          overwrites your profile silently.
        </p>

        {extraction.conflicts.length === 0 ? (
          <p className="mt-6 text-sm text-gray-500">No new or differing information was found in this document.</p>
        ) : (
          <ul className="mt-6 flex flex-col gap-4">
            {extraction.conflicts.map((change) => (
              <li
                key={change.change_id}
                className="rounded-md border border-gray-200 p-4 dark:border-gray-700"
                data-testid={`change-${change.change_id}`}
              >
                <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{describeChange(change)}</p>
                <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="mb-1 font-semibold text-gray-500">Existing</p>
                    <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                      {formatValue(change.existing_value)}
                    </pre>
                  </div>
                  <div>
                    <p className="mb-1 font-semibold text-gray-500">Proposed</p>
                    <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                      {formatValue(change.proposed_value)}
                    </pre>
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => setDecision(change.change_id, 'accept')}
                    className={`rounded px-3 py-1 text-xs font-medium ${
                      decisions[change.change_id] === 'accept'
                        ? 'bg-green-600 text-white'
                        : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                    }`}
                  >
                    Accept
                  </button>
                  <button
                    onClick={() => setDecision(change.change_id, 'reject')}
                    className={`rounded px-3 py-1 text-xs font-medium ${
                      decisions[change.change_id] === 'reject'
                        ? 'bg-red-600 text-white'
                        : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                    }`}
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-6 flex items-center justify-between">
          <span className="text-xs text-gray-500">
            {decidedCount} of {extraction.conflicts.length} decided
          </span>
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded px-4 py-2 text-sm text-gray-600 dark:text-gray-400">
              Close
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting || decidedCount === 0}
              className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {submitting ? 'Applying…' : 'Apply decisions'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
