export interface Experience {
  id: string
  company: string
  title: string
  location?: string | null
  start_date?: string | null
  end_date?: string | null
  is_current: boolean
  responsibilities: string[]
  achievements: string[]
  display_order: number
}

export interface Education {
  id: string
  institution: string
  degree?: string | null
  field_of_study?: string | null
  start_date?: string | null
  end_date?: string | null
  gpa?: string | null
  display_order: number
}

export interface Skill {
  id: string
  name: string
  category: string
  proficiency?: string | null
}

export interface Certification {
  id: string
  name: string
  issuer?: string | null
  issue_date?: string | null
  expiry_date?: string | null
  credential_url?: string | null
}

export interface Project {
  id: string
  name: string
  description?: string | null
  technologies: string[]
  url?: string | null
  start_date?: string | null
  end_date?: string | null
}

export interface CandidateProfile {
  id: string
  full_name?: string | null
  phone?: string | null
  location?: string | null
  preferred_locations: string[]
  work_authorization?: string | null
  professional_summary?: string | null
  target_roles: string[]
  salary_expectation_min?: number | null
  salary_expectation_max?: number | null
  notice_period?: string | null
  remote_preference?: string | null
  links: Record<string, string>
  version: number
  experiences: Experience[]
  education: Education[]
  skills: Skill[]
  certifications: Certification[]
  projects: Project[]
}

export type ChangeKind =
  | 'field_update'
  | 'new_experience'
  | 'new_education'
  | 'new_skill'
  | 'new_certification'
  | 'new_project'

export interface ProfileChange {
  change_id: string
  kind: ChangeKind
  field?: string | null
  existing_value: unknown
  proposed_value: unknown
}

export interface ProfileExtraction {
  id: string
  document_id: string
  status: 'pending' | 'approved' | 'rejected' | 'partially_applied' | 'failed'
  extracted_data: Record<string, unknown>
  conflicts: ProfileChange[]
  reviewed_at?: string | null
}

export interface User {
  id: string
  email: string
  name: string
}

export type Provider = 'greenhouse' | 'lever'

export interface JobSource {
  id: string
  provider: Provider
  company_slug: string
  display_name?: string | null
  is_active: boolean
  last_polled_at?: string | null
}

export interface DiscoveryResult {
  fetched: number
  new_jobs: number
  updated_jobs: number
  duplicates_merged: number
  matched: number
}

export interface JobMatch {
  fit_score: number
  dimension_scores: Record<string, number | null>
  hard_disqualifiers: string[]
  strong_matches: string[]
  gaps: string[]
  summary: string
  computed_at: string
}

export interface JobSnapshot {
  provider_job_id: string
  fetched_at: string
}

export type SavedStatus = 'shortlisted' | 'saved_for_later' | 'rejected' | 'ignored'

export interface Job {
  id: string
  company_name?: string | null
  title: string
  location?: string | null
  remote_status?: string | null
  employment_type?: string | null
  salary_min?: number | null
  salary_max?: number | null
  salary_currency?: string | null
  posting_url?: string | null
  analysis_status: string
  status: string
  first_seen_at: string
  last_seen_at: string
  match?: JobMatch | null
  saved_status?: SavedStatus | null
}

export interface JobDetail extends Job {
  description_text?: string | null
  structured_requirements: Record<string, unknown>
  snapshots: JobSnapshot[]
}

export interface Preferences {
  automation_mode: string
  notification_settings: Record<string, unknown>
  scoring_weights: Record<string, number>
  shortlist_thresholds: Record<string, number>
  blacklisted_companies: string[]
  blacklisted_roles: string[]
  prioritized_companies: string[]
}

export type ResumeVersionStatus = 'ready' | 'qa_failed' | 'generation_failed'

export interface ResumeExperienceEntry {
  experience_id: string
  company: string
  title: string
  location?: string | null
  start_date?: string | null
  end_date?: string | null
  is_current: boolean
  bullets: string[]
}

export interface ResumeEducationEntry {
  institution: string
  degree?: string | null
  field_of_study?: string | null
  start_date?: string | null
  end_date?: string | null
}

export interface ResumeProjectEntry {
  name: string
  description?: string | null
  technologies: string[]
}

export interface ResumeCertificationEntry {
  name: string
  issuer?: string | null
}

export interface StructuredResumeContent {
  full_name?: string | null
  phone?: string | null
  email?: string | null
  location?: string | null
  links: Record<string, string>
  professional_summary: string
  skills: string[]
  experiences: ResumeExperienceEntry[]
  education: ResumeEducationEntry[]
  projects: ResumeProjectEntry[]
  certifications: ResumeCertificationEntry[]
}

export interface QAReport {
  ats_keyword_coverage?: number | null
  matched_keywords: string[]
  missing_keywords: string[]
  word_count: number
  warnings: string[]
  errors: string[]
}

export interface ResumeVersion {
  id: string
  resume_id: string
  version_number: number
  status: ResumeVersionStatus
  structured_content: StructuredResumeContent
  qa_report: QAReport
  generated_at: string
}

export interface Resume {
  id: string
  job_id?: string | null
  label: string
  created_at: string
  latest_version?: ResumeVersion | null
}

export interface ResumeDetail extends Resume {
  versions: ResumeVersion[]
}

export interface CoverLetterVersion {
  id: string
  version_number: number
  status: ResumeVersionStatus
  body_text: string
  qa_report: QAReport
  generated_at: string
}

export type ApplicationStatus =
  | 'preparing'
  | 'ready_for_review'
  | 'approved'
  | 'staged'
  | 'submission_blocked'
  | 'submitted'
  | 'rejected'
  | 'interview'
  | 'offer'
  | 'withdrawn'
  | 'error'

export type OutcomeStatus = 'rejected' | 'interview' | 'offer' | 'withdrawn'

export interface GateResult {
  name: string
  passed: boolean
  message: string
  overridden: boolean
}

export interface GateReport {
  gates: GateResult[]
  passed: boolean
}

export interface ApplicationAnswer {
  id: string
  question: string
  answer?: string | null
  is_grounded: boolean
  flag_reason?: string | null
  reviewed: boolean
}

export interface ApplicationEvent {
  from_status?: string | null
  to_status: string
  actor: string
  note?: string | null
  created_at: string
}

export interface StagingNotes {
  fields_filled: string[]
  fields_needing_manual_input: string[]
  blocked_reason?: string | null
}

export interface Application {
  id: string
  job_id: string
  job_title: string
  company_name?: string | null
  status: ApplicationStatus
  gate_report: GateReport
  submitted_at?: string | null
  outcome_note?: string | null
  staging_notes: StagingNotes
  has_staged_screenshot: boolean
  created_at: string
}

export interface ApplicationDetail extends Application {
  resume_version?: ResumeVersion | null
  cover_letter_version?: CoverLetterVersion | null
  answers: ApplicationAnswer[]
  events: ApplicationEvent[]
}

export type RunType = 'discovery' | 'digest' | 'stale_check'
export type RunStatus = 'running' | 'completed' | 'failed'

export interface AutomationStep {
  step_name: string
  status: string
  detail: Record<string, unknown>
  error?: string | null
  created_at: string
}

export interface AutomationRun {
  id: string
  run_type: RunType
  status: RunStatus
  triggered_by: string
  started_at: string
  completed_at?: string | null
  summary: Record<string, number>
  error?: string | null
}

export interface AutomationRunDetail extends AutomationRun {
  steps: AutomationStep[]
}

export interface Notification {
  id: string
  type: string
  title: string
  body: string
  data: Record<string, unknown>
  read: boolean
  created_at: string
}

export interface DashboardSummary {
  jobs_discovered: number
  jobs_shortlisted: number
  applications_submitted: number
  interviews: number
  offers: number
  rejections: number
  rejection_rate: number
  response_rate: number
}

export interface DashboardPipeline {
  discovered: number
  shortlisted: number
  prepared: number
  applied: number
  interview: number
  offer: number
}

export interface DashboardOverview {
  summary: DashboardSummary
  pipeline: DashboardPipeline
}

export type ActivityType = 'audit' | 'application_event' | 'automation_run'
export type ActivityStatus = 'success' | 'error' | 'info'

export interface ActivityItem {
  type: ActivityType
  title: string
  detail?: string | null
  status: ActivityStatus
  created_at: string
}

export type AlertType = 'application_error' | 'resume_failed' | 'cover_letter_failed' | 'answer_flagged'

export interface AlertLink {
  kind: 'application' | 'resume' | 'cover_letter'
  id: string
}

export interface AlertItem {
  type: AlertType
  title: string
  detail: string
  link: AlertLink
  created_at: string
}
