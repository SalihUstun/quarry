export type ServiceState = 'ok' | 'unavailable'

export interface SystemStatus {
  gateway: ServiceState
  ai: ServiceState
}

export async function fetchSystemStatus(signal?: AbortSignal): Promise<SystemStatus> {
  const response = await fetch('/api/status', { signal })
  if (!response.ok) {
    throw new Error(`Status request failed with ${response.status}`)
  }
  return (await response.json()) as SystemStatus
}
