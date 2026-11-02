import { StatusPanel } from './features/status/StatusPanel'

export function App() {
  return (
    <main className="app">
      <h1>Quarry</h1>
      <p className="subtitle">Türkçe dokümanlar için kaynak gösteren soru-cevap platformu</p>
      <StatusPanel />
    </main>
  )
}
