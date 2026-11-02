import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LoginForm } from './LoginForm'
import { currentUserKey } from './useCurrentUser'

function renderForm(client: QueryClient) {
  return render(
    <QueryClientProvider client={client}>
      <LoginForm />
    </QueryClientProvider>,
  )
}

function submit(email: string, password: string) {
  fireEvent.change(screen.getByLabelText('E-posta'), { target: { value: email } })
  fireEvent.change(screen.getByLabelText('Şifre'), { target: { value: password } })
  fireEvent.click(screen.getByRole('button', { name: 'Giriş yap' }))
}

describe('LoginForm', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('stores the signed in user after a successful login', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(Response.json({ email: 'admin@quarry.local', tenantId: 't1' }))
    vi.stubGlobal('fetch', fetchMock)
    const client = new QueryClient()
    renderForm(client)

    submit('admin@quarry.local', 'gizli-sifre')

    await waitFor(() =>
      expect(client.getQueryData(currentUserKey)).toEqual({
        email: 'admin@quarry.local',
        tenantId: 't1',
      }),
    )
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/auth/login')
    expect(JSON.parse(init.body as string)).toEqual({
      email: 'admin@quarry.local',
      password: 'gizli-sifre',
    })
  })

  it('shows the server message when credentials are wrong', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(Response.json({ title: 'E-posta veya şifre hatalı.' }, { status: 401 })),
    )
    renderForm(new QueryClient())

    submit('admin@quarry.local', 'yanlis')

    expect(await screen.findByRole('alert')).toHaveTextContent('E-posta veya şifre hatalı.')
  })
})
