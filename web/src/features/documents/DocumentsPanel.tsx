import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, type ChangeEvent } from 'react'
import {
  listDocuments,
  uploadDocument,
  type DocumentItem,
  type DocumentStatus,
} from '../../api/client'

const documentsKey = ['documents'] as const

const statusLabels: Record<DocumentStatus, string> = {
  pending: 'Sırada',
  processing: 'İşleniyor',
  ready: 'Hazır',
  failed: 'Hata',
}

function isInProgress(document: DocumentItem) {
  return document.status === 'pending' || document.status === 'processing'
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentsPanel() {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const documents = useQuery({
    queryKey: documentsKey,
    queryFn: ({ signal }) => listDocuments(signal),
    refetchInterval: (query) => (query.state.data?.some(isInProgress) ? 2000 : false),
  })
  const upload = useMutation({
    mutationFn: uploadDocument,
    onSettled: () => queryClient.invalidateQueries({ queryKey: documentsKey }),
  })

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) {
      upload.mutate(file)
    }
    event.target.value = ''
  }

  return (
    <section className="card documents" aria-labelledby="documents-title">
      <div className="card-header">
        <h2 id="documents-title">Dokümanlar</h2>
        <button type="button" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? 'Yükleniyor…' : 'Doküman yükle'}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          hidden
          aria-label="Doküman dosyası"
          onChange={handleFileChange}
        />
      </div>
      {upload.isError && <p role="alert">{upload.error.message}</p>}
      {documents.isPending && <p className="muted">Yükleniyor…</p>}
      {documents.isError && <p role="alert">Doküman listesi alınamadı.</p>}
      {documents.data?.length === 0 && (
        <p className="muted">Henüz doküman yok. PDF, Word veya .txt yükleyerek başla.</p>
      )}
      <ul className="document-list">
        {documents.data?.map((document) => (
          <li key={document.id} className="document-row">
            <div>
              <strong>{document.fileName}</strong>
              <span className="muted">
                {formatSize(document.sizeBytes)}
                {document.pageCount ? ` · ${document.pageCount} sayfa` : ''}
              </span>
              {document.error && <span className="error-text">{document.error}</span>}
            </div>
            <span className={`badge badge-${document.status}`}>
              {statusLabels[document.status]}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
