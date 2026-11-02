import { useRef, useState, type FormEvent } from 'react'
import { askQuestion, type Source } from '../../api/client'

interface Exchange {
  id: number
  question: string
  answer: string
  sources: Source[]
  cited: number[]
  error: string | null
  streaming: boolean
}

function citedSources(exchange: Exchange) {
  return exchange.sources.filter((source) => exchange.cited.includes(source.number))
}

export function ChatPanel() {
  const [question, setQuestion] = useState('')
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const nextId = useRef(0)
  const isStreaming = exchanges.some((exchange) => exchange.streaming)

  function update(id: number, change: (exchange: Exchange) => Partial<Exchange>) {
    setExchanges((current) =>
      current.map((exchange) =>
        exchange.id === id ? { ...exchange, ...change(exchange) } : exchange,
      ),
    )
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isStreaming) {
      return
    }
    const id = nextId.current++
    setQuestion('')
    setExchanges((current) => [
      ...current,
      { id, question: trimmed, answer: '', sources: [], cited: [], error: null, streaming: true },
    ])

    try {
      for await (const answerEvent of askQuestion(trimmed)) {
        switch (answerEvent.type) {
          case 'sources':
            update(id, () => ({ sources: answerEvent.sources }))
            break
          case 'token':
            update(id, (exchange) => ({ answer: exchange.answer + answerEvent.text }))
            break
          case 'done':
            update(id, () => ({ cited: answerEvent.cited }))
            break
          case 'error':
            update(id, () => ({ error: answerEvent.message }))
            break
        }
      }
    } catch (error) {
      update(id, () => ({
        error: error instanceof Error ? error.message : 'Beklenmeyen bir hata oluştu.',
      }))
    } finally {
      update(id, () => ({ streaming: false }))
    }
  }

  return (
    <section className="card chat" aria-labelledby="chat-title">
      <h2 id="chat-title">Soru sor</h2>
      <div className="exchanges" aria-live="polite">
        {exchanges.length === 0 && (
          <p className="muted">Yüklediğin dokümanlar hakkında Türkçe soru sorabilirsin.</p>
        )}
        {exchanges.map((exchange) => (
          <article key={exchange.id} className="exchange">
            <p className="question">{exchange.question}</p>
            <p className="answer">
              {exchange.answer || (exchange.streaming && !exchange.error ? 'Düşünüyor…' : '')}
            </p>
            {exchange.error && <p role="alert">{exchange.error}</p>}
            {citedSources(exchange).length > 0 && (
              <ul className="sources" aria-label="Kaynaklar">
                {citedSources(exchange).map((source) => (
                  <li key={source.chunkId} className="source-card">
                    <span className="source-number">[{source.number}]</span>
                    <div>
                      <strong>
                        {source.fileName} · s. {source.pageNumber}
                      </strong>
                      <p className="muted">{source.snippet}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
      <form className="ask-form" onSubmit={handleSubmit}>
        <input
          aria-label="Soru"
          placeholder="Örn. Yıllık izin kaç gün?"
          value={question}
          maxLength={2000}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button type="submit" disabled={isStreaming || !question.trim()}>
          Sor
        </button>
      </form>
    </section>
  )
}
