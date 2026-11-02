import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StatusPanel } from './StatusPanel'

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <StatusPanel />
    </QueryClientProvider>,
  )
}

describe('StatusPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows each service state returned by the gateway', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ gateway: 'ok', ai: 'unavailable' })),
    )

    renderWithClient()

    expect(await screen.findByText('Gateway')).toBeInTheDocument()
    expect(screen.getByText('Çalışıyor')).toBeInTheDocument()
    expect(screen.getByText('Erişilemiyor')).toBeInTheDocument()
  })

  it('shows an alert when the gateway cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 502 })))

    renderWithClient()

    expect(await screen.findByRole('alert')).toHaveTextContent("Gateway'e ulaşılamıyor.")
  })
})
