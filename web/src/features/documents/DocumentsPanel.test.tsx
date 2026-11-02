import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DocumentsPanel } from './DocumentsPanel'

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <DocumentsPanel />
    </QueryClientProvider>,
  )
}

describe('DocumentsPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists documents with status, size, page count and errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        Response.json([
          {
            id: '1',
            fileName: 'el-kitabi.pdf',
            status: 'ready',
            error: null,
            pageCount: 3,
            sizeBytes: 37_273,
            createdAt: '2026-11-02T10:00:00Z',
          },
          {
            id: '2',
            fileName: 'bozuk.pdf',
            status: 'failed',
            error: 'PDF okunamadı',
            pageCount: null,
            sizeBytes: 512,
            createdAt: '2026-11-02T09:00:00Z',
          },
        ]),
      ),
    )

    renderPanel()

    expect(await screen.findByText('el-kitabi.pdf')).toBeInTheDocument()
    expect(screen.getByText('Hazır')).toBeInTheDocument()
    expect(screen.getByText('36 KB · 3 sayfa')).toBeInTheDocument()
    expect(screen.getByText('Hata')).toBeInTheDocument()
    expect(screen.getByText('PDF okunamadı')).toBeInTheDocument()
  })

  it('shows an empty state when there are no documents', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json([])))

    renderPanel()

    expect(await screen.findByText(/Henüz doküman yok/)).toBeInTheDocument()
  })
})
