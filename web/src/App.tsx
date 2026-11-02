import { LoginForm } from './features/auth/LoginForm'
import { useCurrentUser, useLogout } from './features/auth/useCurrentUser'
import { ChatPanel } from './features/chat/ChatPanel'
import { DocumentsPanel } from './features/documents/DocumentsPanel'
import { StatusPanel } from './features/status/StatusPanel'

export function App() {
  const currentUser = useCurrentUser()
  const logout = useLogout()

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Quarry</h1>
          <p className="subtitle">Türkçe dokümanlar için kaynak gösteren soru-cevap platformu</p>
        </div>
        {currentUser.data && (
          <div className="user-menu">
            <span className="muted">{currentUser.data.email}</span>
            <button type="button" className="secondary" onClick={() => logout.mutate()}>
              Çıkış
            </button>
          </div>
        )}
      </header>
      <main>
        {currentUser.isPending && <p className="muted">Yükleniyor…</p>}
        {currentUser.isError && <p role="alert">Oturum bilgisi alınamadı.</p>}
        {currentUser.data === null && <LoginForm />}
        {currentUser.data && (
          <div className="workspace">
            <DocumentsPanel />
            <ChatPanel />
          </div>
        )}
      </main>
      <footer>
        <StatusPanel />
      </footer>
    </div>
  )
}
