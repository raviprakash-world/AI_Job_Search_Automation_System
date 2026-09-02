import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { preferencesApi } from '../api/endpoints'
import Section from '../components/Section'

const PREFERENCES_KEY = ['preferences']

function ListEditor({ label, values, onChange }: { label: string; values: string[]; onChange: (values: string[]) => void }) {
  const [draft, setDraft] = useState('')

  return (
    <div>
      <p className="mb-1 text-sm font-medium text-gray-700 dark:text-gray-300">{label}</p>
      <div className="mb-2 flex flex-wrap gap-2">
        {values.map((v) => (
          <span key={v} className="flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-xs dark:bg-gray-800">
            {v}
            <button onClick={() => onChange(values.filter((x) => x !== v))} className="text-red-600">
              ×
            </button>
          </span>
        ))}
        {values.length === 0 && <span className="text-xs text-gray-500">None</span>}
      </div>
      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add…"
          className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
        />
        <button
          onClick={() => {
            if (draft.trim()) {
              onChange([...values, draft.trim()])
              setDraft('')
            }
          }}
          className="rounded-md bg-gray-800 px-3 py-1.5 text-sm text-white"
        >
          Add
        </button>
      </div>
    </div>
  )
}

export default function Settings() {
  const queryClient = useQueryClient()
  const { data: preferences } = useQuery({ queryKey: PREFERENCES_KEY, queryFn: preferencesApi.get })

  const [weights, setWeights] = useState<Record<string, number>>({})
  const [blacklistedCompanies, setBlacklistedCompanies] = useState<string[]>([])
  const [blacklistedRoles, setBlacklistedRoles] = useState<string[]>([])
  const [prioritizedCompanies, setPrioritizedCompanies] = useState<string[]>([])

  useEffect(() => {
    if (!preferences) return
    setWeights(preferences.scoring_weights)
    setBlacklistedCompanies(preferences.blacklisted_companies)
    setBlacklistedRoles(preferences.blacklisted_roles)
    setPrioritizedCompanies(preferences.prioritized_companies)
  }, [preferences])

  const saveMutation = useMutation({
    mutationFn: () =>
      preferencesApi.update({
        scoring_weights: weights,
        blacklisted_companies: blacklistedCompanies,
        blacklisted_roles: blacklistedRoles,
        prioritized_companies: prioritizedCompanies,
      }),
    onSuccess: (updated) => queryClient.setQueryData(PREFERENCES_KEY, updated),
  })

  if (!preferences) return <div className="p-6 text-gray-500">Loading…</div>

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Settings</h1>

      <Section title="Scoring weights">
        <p className="mb-3 text-sm text-gray-600 dark:text-gray-400">
          Weights are renormalized automatically over whichever dimensions have data for a given job — you don't
          need them to sum to 1.
        </p>
        <div className="flex flex-col gap-2">
          {Object.entries(weights).map(([dim, value]) => (
            <label key={dim} className="flex items-center justify-between gap-3 text-sm">
              <span className="capitalize">{dim}</span>
              <input
                type="number"
                step={0.05}
                min={0}
                max={1}
                value={value}
                onChange={(e) => setWeights((prev) => ({ ...prev, [dim]: Number(e.target.value) }))}
                className="w-24 rounded-md border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-900"
              />
            </label>
          ))}
        </div>
      </Section>

      <Section title="Company & role filters">
        <div className="flex flex-col gap-4">
          <ListEditor label="Blacklisted companies" values={blacklistedCompanies} onChange={setBlacklistedCompanies} />
          <ListEditor label="Blacklisted roles" values={blacklistedRoles} onChange={setBlacklistedRoles} />
          <ListEditor label="Prioritized companies" values={prioritizedCompanies} onChange={setPrioritizedCompanies} />
        </div>
      </Section>

      <button
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending}
        className="w-fit rounded-md bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {saveMutation.isPending ? 'Saving…' : 'Save preferences'}
      </button>
    </div>
  )
}
