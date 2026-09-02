import { api } from './client'
import type {
  AlertItem,
  Application,
  ApplicationDetail,
  ActivityItem,
  AutomationRun,
  AutomationRunDetail,
  CandidateProfile,
  Certification,
  DashboardOverview,
  DiscoveryResult,
  Education,
  Experience,
  Job,
  JobDetail,
  JobSource,
  Notification,
  OutcomeStatus,
  Preferences,
  Project,
  ProfileExtraction,
  Provider,
  Resume,
  ResumeDetail,
  RunType,
  SavedStatus,
  Skill,
  User,
} from './types'

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export const authApi = {
  register: (email: string, password: string, name: string) =>
    api.post<TokenResponse>('/auth/register', { email, password, name }),
  login: (email: string, password: string) => api.post<TokenResponse>('/auth/login', { email, password }),
  me: () => api.get<User>('/auth/me'),
}

export const profileApi = {
  get: () => api.get<CandidateProfile>('/profile'),
  update: (payload: Partial<CandidateProfile>) => api.put<CandidateProfile>('/profile', payload),
  addExperience: (payload: Omit<Experience, 'id'>) => api.post<Experience>('/profile/experiences', payload),
  deleteExperience: (id: string) => api.delete(`/profile/experiences/${id}`),
  addEducation: (payload: Omit<Education, 'id'>) => api.post<Education>('/profile/education', payload),
  deleteEducation: (id: string) => api.delete(`/profile/education/${id}`),
  addSkill: (payload: Omit<Skill, 'id'>) => api.post<Skill>('/profile/skills', payload),
  deleteSkill: (id: string) => api.delete(`/profile/skills/${id}`),
  addCertification: (payload: Omit<Certification, 'id'>) =>
    api.post<Certification>('/profile/certifications', payload),
  deleteCertification: (id: string) => api.delete(`/profile/certifications/${id}`),
  addProject: (payload: Omit<Project, 'id'>) => api.post<Project>('/profile/projects', payload),
  deleteProject: (id: string) => api.delete(`/profile/projects/${id}`),
}

export const documentsApi = {
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<ProfileExtraction>('/profile/documents', formData)
  },
  getExtraction: (documentId: string) => api.get<ProfileExtraction>(`/profile/documents/${documentId}/extraction`),
  resolve: (documentId: string, resolutions: { change_id: string; action: 'accept' | 'reject' }[]) =>
    api.post<ProfileExtraction>(`/profile/documents/${documentId}/extraction/resolve`, { resolutions }),
}

export const jobSourcesApi = {
  list: () => api.get<JobSource[]>('/job-sources'),
  create: (provider: Provider, companySlug: string, displayName?: string) =>
    api.post<JobSource>('/job-sources', { provider, company_slug: companySlug, display_name: displayName }),
  remove: (id: string) => api.delete(`/job-sources/${id}`),
  discover: (id: string) => api.post<DiscoveryResult>(`/job-sources/${id}/discover`),
}

export interface JobListFilters {
  status?: string
  min_score?: number
  company?: string
  saved_status?: SavedStatus
  include_blacklisted?: boolean
}

export const jobsApi = {
  list: (filters: JobListFilters = {}) => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
    }
    const query = params.toString()
    return api.get<Job[]>(`/jobs${query ? `?${query}` : ''}`)
  },
  get: (id: string) => api.get<JobDetail>(`/jobs/${id}`),
  act: (id: string, action: 'shortlist' | 'save_for_later' | 'reject' | 'ignore', reason?: string) =>
    api.post(`/jobs/${id}/action`, { action, reason }),
}

export const preferencesApi = {
  get: () => api.get<Preferences>('/preferences'),
  update: (payload: Partial<Preferences>) => api.put<Preferences>('/preferences', payload),
}

export interface ResumeCreatePayload {
  job_id?: string
  label?: string
  include_projects?: boolean
  include_certifications?: boolean
}

export const resumesApi = {
  list: () => api.get<Resume[]>('/resumes'),
  get: (id: string) => api.get<ResumeDetail>(`/resumes/${id}`),
  create: (payload: ResumeCreatePayload) => api.post<ResumeDetail>('/resumes', payload),
  regenerate: (id: string) => api.post<ResumeDetail>(`/resumes/${id}/regenerate`),
  remove: (id: string) => api.delete(`/resumes/${id}`),
  downloadBlob: (resumeId: string, versionId: string) =>
    api.getBlob(`/resumes/${resumeId}/versions/${versionId}/download`),
}

export interface ApplicationCreatePayload {
  job_id: string
  resume_version_id: string
  generate_cover_letter: boolean
  custom_questions: string[]
  override_low_match?: boolean
}

export const applicationsApi = {
  list: () => api.get<Application[]>('/applications'),
  get: (id: string) => api.get<ApplicationDetail>(`/applications/${id}`),
  create: (payload: ApplicationCreatePayload) => api.post<ApplicationDetail>('/applications', payload),
  retryPreparation: (id: string) => api.post<ApplicationDetail>(`/applications/${id}/retry-preparation`),
  approve: (id: string) => api.post<ApplicationDetail>(`/applications/${id}/approve`),
  markSubmitted: (id: string, note?: string) =>
    api.post<ApplicationDetail>(`/applications/${id}/mark-submitted`, { note }),
  updateStatus: (id: string, status: OutcomeStatus, note?: string) =>
    api.post<ApplicationDetail>(`/applications/${id}/status`, { status, note }),
  reviewAnswer: (applicationId: string, answerId: string, answer: string) =>
    api.put(`/applications/${applicationId}/answers/${answerId}`, { answer }),
  remove: (id: string) => api.delete(`/applications/${id}`),
  downloadCoverLetterBlob: (id: string) => api.getBlob(`/applications/${id}/cover-letter/download`),
  stage: (id: string) => api.post<ApplicationDetail>(`/applications/${id}/stage`),
  stagingScreenshotBlob: (id: string) => api.getBlob(`/applications/${id}/staging-screenshot`),
}

export const automationApi = {
  listRuns: (runType?: RunType) => api.get<AutomationRun[]>(`/automation/runs${runType ? `?run_type=${runType}` : ''}`),
  getRun: (id: string) => api.get<AutomationRunDetail>(`/automation/runs/${id}`),
  runDiscovery: () => api.post<AutomationRun>('/automation/discovery/run'),
  runDigest: () => api.post<AutomationRun>('/automation/digest/run'),
}

export const notificationsApi = {
  list: (unreadOnly = false) => api.get<Notification[]>(`/notifications${unreadOnly ? '?unread=true' : ''}`),
  markRead: (id: string) => api.post<Notification>(`/notifications/${id}/read`),
  markAllRead: () => api.post<{ marked_read: number }>('/notifications/read-all'),
}

export const dashboardApi = {
  overview: () => api.get<DashboardOverview>('/dashboard/overview'),
  activity: (limit = 20) => api.get<ActivityItem[]>(`/dashboard/activity?limit=${limit}`),
  alerts: () => api.get<AlertItem[]>('/dashboard/alerts'),
}
