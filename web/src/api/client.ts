import { readSse } from './sse'

export type ServiceState = 'ok' | 'unavailable'

export interface SystemStatus {
  gateway: ServiceState
  ai: ServiceState
}

export interface User {
  email: string
  tenantId: string
}

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface DocumentItem {
  id: string
  fileName: string
  status: DocumentStatus
  error: string | null
  pageCount: number | null
  sizeBytes: number
  createdAt: string
}

export interface Source {
  number: number
  chunkId: string
  documentId: string
  fileName: string
  pageNumber: number
  snippet: string
}

export type AskEvent =
  | { type: 'sources'; sources: Source[] }
  | { type: 'token'; text: string }
  | { type: 'done'; cited: number[] }
  | { type: 'error'; message: string }

interface RawSource {
  number: number
  chunk_id: string
  document_id: string
  file_name: string
  page_number: number
  snippet: string
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  let message = `İstek başarısız oldu (${response.status}).`
  try {
    const body = (await response.json()) as { title?: string; detail?: string }
    message = body.title ?? body.detail ?? message
  } catch {
    return new ApiError(response.status, message)
  }
  return new ApiError(response.status, message)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', ...init })
  if (!response.ok) {
    throw await errorFrom(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

const jsonHeaders = { 'Content-Type': 'application/json' }

export function fetchSystemStatus(signal?: AbortSignal): Promise<SystemStatus> {
  return request<SystemStatus>('/api/status', { signal })
}

export async function fetchCurrentUser(signal?: AbortSignal): Promise<User | null> {
  try {
    return await request<User>('/api/auth/me', { signal })
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null
    }
    throw error
  }
}

export function login(email: string, password: string): Promise<User> {
  return request<User>('/api/auth/login', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ email, password }),
  })
}

export async function logout(): Promise<void> {
  await request<unknown>('/api/auth/logout', { method: 'POST' })
}

export function listDocuments(signal?: AbortSignal): Promise<DocumentItem[]> {
  return request<DocumentItem[]>('/api/documents', { signal })
}

export function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData()
  form.append('file', file)
  return request<DocumentItem>('/api/documents', { method: 'POST', body: form })
}

function toSource(raw: RawSource): Source {
  return {
    number: raw.number,
    chunkId: raw.chunk_id,
    documentId: raw.document_id,
    fileName: raw.file_name,
    pageNumber: raw.page_number,
    snippet: raw.snippet,
  }
}

function toAskEvent(event: string, data: string): AskEvent | null {
  const payload: unknown = JSON.parse(data)
  switch (event) {
    case 'sources':
      return { type: 'sources', sources: (payload as RawSource[]).map(toSource) }
    case 'token':
      return { type: 'token', text: (payload as { text: string }).text }
    case 'done':
      return { type: 'done', cited: (payload as { cited: number[] }).cited }
    case 'error':
      return { type: 'error', message: (payload as { message: string }).message }
    default:
      return null
  }
}

export async function* askQuestion(
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<AskEvent> {
  const response = await fetch('/api/ask', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { ...jsonHeaders, Accept: 'text/event-stream' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!response.ok || !response.body) {
    throw await errorFrom(response)
  }
  for await (const message of readSse(response.body)) {
    const event = toAskEvent(message.event, message.data)
    if (event) {
      yield event
    }
  }
}
