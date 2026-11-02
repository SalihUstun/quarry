import { useQuery } from '@tanstack/react-query'
import { fetchSystemStatus, type ServiceState } from '../../api/client'

const stateLabels: Record<ServiceState, string> = {
  ok: 'Çalışıyor',
  unavailable: 'Erişilemiyor',
}

function StatusRow({ name, state }: { name: string; state: ServiceState }) {
  return (
    <li className={`status-row status-${state}`}>
      <span>{name}</span>
      <strong>{stateLabels[state]}</strong>
    </li>
  )
}

export function StatusPanel() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['system-status'],
    queryFn: ({ signal }) => fetchSystemStatus(signal),
    refetchInterval: 10_000,
  })

  if (isPending) {
    return <p>Durum kontrol ediliyor…</p>
  }

  if (isError) {
    return <p role="alert">Gateway'e ulaşılamıyor.</p>
  }

  return (
    <ul className="status-list" aria-label="Servis durumu">
      <StatusRow name="Gateway" state={data.gateway} />
      <StatusRow name="AI servisi" state={data.ai} />
    </ul>
  )
}
