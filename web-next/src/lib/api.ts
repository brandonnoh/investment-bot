import type {
  AnalysisHistory,
  IntelData,
  LogResponse,
  ProcessStatus,
} from '@/types/api'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8421'

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
