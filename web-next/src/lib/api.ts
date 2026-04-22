import type {
  AnalysisHistory,
  IntelData,
  LogResponse,
  ProcessStatus,
} from '@/types/api'

// Flask가 정적 파일과 API 모두 서빙하므로 상대 경로 사용
// NEXT_PUBLIC_API_BASE는 개발 모드(dev server)에서 로컬 Flask 연결 시에만 사용
const BASE = typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE
  ? process.env.NEXT_PUBLIC_API_BASE
  : ''

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json() as Promise<T>
}

export async function fetchIntelData(): Promise<IntelData> {
  return apiFetch<IntelData>('/api/data')
}

export async function fetchProcessStatus(): Promise<ProcessStatus> {
  return apiFetch<ProcessStatus>('/api/status')
}

export async function fetchAnalysisHistory(): Promise<AnalysisHistory[]> {
  return apiFetch<AnalysisHistory[]>('/api/analysis-history')
}

export async function fetchLogs(
  name: string,
  lines = 50,
): Promise<LogResponse> {
  return apiFetch<LogResponse>(`/api/logs?name=${name}&lines=${lines}`)
}

export async function fetchOpportunities(strategy: string): Promise<{
  strategy: string
  meta: { name: string; description: string }
  opportunities: import('@/types/api').Opportunity[]
  total_count: number
}> {
  return apiFetch(`/api/opportunities?strategy=${strategy}`)
}
