import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { documentsApi, profileApi } from '../api/endpoints'
import { ApiError } from '../api/client'
import type { CandidateProfile, ProfileExtraction } from '../api/types'
import ExtractionReviewModal from '../components/ExtractionReviewModal'
import Section from '../components/Section'

const PROFILE_KEY = ['profile']

function SummaryForm({ profile }: { profile: CandidateProfile }) {
  const queryClient = useQueryClient()
  const [fullName, setFullName] = useState(profile.full_name ?? '')
  const [location, setLocation] = useState(profile.location ?? '')
  const [summary, setSummary] = useState(profile.professional_summary ?? '')

  const mutation = useMutation({
    mutationFn: () => profileApi.update({ full_name: fullName, location, professional_summary: summary }),
    onSuccess: (updated) => queryClient.setQueryData(PROFILE_KEY, updated),
  })

  return (
    <form
      onSubmit={(e: FormEvent) => {
        e.preventDefault()
        mutation.mutate()
      }}
      className="flex flex-col gap-3"
    >
      <input
        placeholder="Full name"
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
        className="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
      />
      <input
        placeholder="Location"
        value={location}
        onChange={(e) => setLocation(e.target.value)}
        className="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
      />
      <textarea
        placeholder="Professional summary"
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        rows={3}
        className="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
      />
      <button
        type="submit"
        disabled={mutation.isPending}
        className="w-fit rounded-md bg-indigo-600 px-4 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {mutation.isPending ? 'Saving…' : 'Save'}
      </button>
    </form>
  )
}

function ExperienceSection({ profile }: { profile: CandidateProfile }) {
  const queryClient = useQueryClient()
  const [company, setCompany] = useState('')
  const [title, setTitle] = useState('')

  const addMutation = useMutation({
    mutationFn: () =>
      profileApi.addExperience({
        company,
        title,
        location: null,
        start_date: null,
        end_date: null,
        is_current: false,
        responsibilities: [],
        achievements: [],
        display_order: profile.experiences.length,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROFILE_KEY })
      setCompany('')
      setTitle('')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => profileApi.deleteExperience(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_KEY }),
  })

  return (
    <Section title="Experience">
      <ul className="mb-4 flex flex-col gap-2">
        {profile.experiences.map((exp) => (
          <li key={exp.id} className="flex items-center justify-between text-sm">
            <span>
              {exp.title} · {exp.company}
            </span>
            <button onClick={() => deleteMutation.mutate(exp.id)} className="text-xs text-red-600">
              Remove
            </button>
          </li>
        ))}
        {profile.experiences.length === 0 && <p className="text-sm text-gray-500">No experience added yet.</p>}
      </ul>
      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          if (company && title) addMutation.mutate()
        }}
        className="flex gap-2"
      >
        <input
          placeholder="Company"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
        />
        <input
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
        />
        <button type="submit" className="rounded-md bg-gray-800 px-3 py-1.5 text-sm text-white">
          Add
        </button>
      </form>
    </Section>
  )
}

function SkillsSection({ profile }: { profile: CandidateProfile }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')

  const addMutation = useMutation({
    mutationFn: () => profileApi.addSkill({ name, category: 'technical', proficiency: null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROFILE_KEY })
      setName('')
    },
  })
  const deleteMutation = useMutation({
    mutationFn: (id: string) => profileApi.deleteSkill(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_KEY }),
  })

  return (
    <Section title="Skills">
      <div className="mb-4 flex flex-wrap gap-2">
        {profile.skills.map((skill) => (
          <span
            key={skill.id}
            className="flex items-center gap-2 rounded-full bg-gray-100 px-3 py-1 text-xs dark:bg-gray-800"
          >
            {skill.name}
            <button onClick={() => deleteMutation.mutate(skill.id)} className="text-red-600">
              ×
            </button>
          </span>
        ))}
        {profile.skills.length === 0 && <p className="text-sm text-gray-500">No skills added yet.</p>}
      </div>
      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          if (name) addMutation.mutate()
        }}
        className="flex gap-2"
      >
        <input
          placeholder="Add a skill"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
        />
        <button type="submit" className="rounded-md bg-gray-800 px-3 py-1.5 text-sm text-white">
          Add
        </button>
      </form>
    </Section>
  )
}

function DocumentUpload({ onExtraction }: { onExtraction: (extraction: ProfileExtraction) => void }) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFileChange() {
    const file = fileInput.current?.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const extraction = await documentsApi.upload(file)
      onExtraction(extraction)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  return (
    <Section title="Upload a resume or supporting document">
      <p className="mb-3 text-sm text-gray-600 dark:text-gray-400">
        Accepts DOCX or PDF. Extracted data is never applied automatically — you review and approve every change.
      </p>
      <input
        ref={fileInput}
        type="file"
        accept=".docx,.pdf"
        onChange={handleFileChange}
        disabled={uploading}
        className="text-sm"
      />
      {uploading && <p className="mt-2 text-sm text-gray-500">Parsing and analyzing document…</p>}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </Section>
  )
}

export default function MasterProfile() {
  const { data: profile, isLoading } = useQuery({ queryKey: PROFILE_KEY, queryFn: profileApi.get })
  const [activeExtraction, setActiveExtraction] = useState<ProfileExtraction | null>(null)
  const queryClient = useQueryClient()

  if (isLoading || !profile) {
    return <div className="p-6 text-gray-500">Loading profile…</div>
  }

  async function handleResolve(resolutions: { change_id: string; action: 'accept' | 'reject' }[]) {
    if (!activeExtraction) return
    await documentsApi.resolve(activeExtraction.document_id, resolutions)
    setActiveExtraction(null)
    queryClient.invalidateQueries({ queryKey: PROFILE_KEY })
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Master Profile</h1>

      <Section title="Summary">
        <SummaryForm profile={profile} />
      </Section>

      <ExperienceSection profile={profile} />
      <SkillsSection profile={profile} />
      <DocumentUpload onExtraction={setActiveExtraction} />

      {activeExtraction && (
        <ExtractionReviewModal
          extraction={activeExtraction}
          onSubmit={handleResolve}
          onClose={() => setActiveExtraction(null)}
        />
      )}
    </div>
  )
}
