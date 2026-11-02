import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { login } from '../../api/client'
import { currentUserKey } from './useCurrentUser'

export function LoginForm() {
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (user) => queryClient.setQueryData(currentUserKey, user),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <form className="card login-form" onSubmit={handleSubmit}>
      <h2>Giriş yap</h2>
      <label>
        E-posta
        <input
          type="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <label>
        Şifre
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </label>
      {mutation.isError && <p role="alert">{mutation.error.message}</p>}
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Giriş yapılıyor…' : 'Giriş yap'}
      </button>
    </form>
  )
}
