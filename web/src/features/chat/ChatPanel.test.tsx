import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AskEvent } from '../../api/client'
import { ChatPanel } from './ChatPanel'

const askQuestion = vi.hoisted(() => vi.fn<(question: string) => AsyncGenerator<AskEvent>>())

vi.mock('../../api/client', () => ({ askQuestion }))

async function* events(...items: AskEvent[]): AsyncGenerator<AskEvent> {
  for (const item of items) {
    yield await Promise.resolve(item)
  }
}

function ask(question: string) {
  fireEvent.change(screen.getByLabelText('Soru'), { target: { value: question } })
  fireEvent.click(screen.getByRole('button', { name: 'Sor' }))
}

describe('ChatPanel', () => {
  afterEach(() => {
    askQuestion.mockReset()
  })

  it('streams the answer and shows only cited sources with file and page', async () => {
    askQuestion.mockReturnValue(
      events(
        {
          type: 'sources',
          sources: [
            {
              number: 1,
              chunkId: 'c1',
              documentId: 'd1',
              fileName: 'el-kitabi.pdf',
              pageNumber: 2,
              snippet: 'Yılda 14 iş günü izin verilir.',
            },
            {
              number: 2,
              chunkId: 'c2',
              documentId: 'd1',
              fileName: 'el-kitabi.pdf',
              pageNumber: 3,
              snippet: 'Masraflar 30 gün içinde girilir.',
            },
          ],
        },
        { type: 'token', text: 'Yıllık izin ' },
        { type: 'token', text: '14 iş günüdür [1].' },
        { type: 'done', cited: [1] },
      ),
    )
    render(<ChatPanel />)

    ask('  Yıllık izin kaç gün?  ')

    expect(await screen.findByText('Yıllık izin 14 iş günüdür [1].')).toBeInTheDocument()
    expect(askQuestion).toHaveBeenCalledWith('Yıllık izin kaç gün?')
    expect(screen.getByText('el-kitabi.pdf · s. 2')).toBeInTheDocument()
    expect(screen.queryByText('el-kitabi.pdf · s. 3')).not.toBeInTheDocument()
  })

  it('shows the error message when the stream reports an error', async () => {
    askQuestion.mockReturnValue(
      events({ type: 'sources', sources: [] }, { type: 'error', message: 'Sağlayıcı hatası.' }),
    )
    render(<ChatPanel />)

    ask('Soru?')

    expect(await screen.findByRole('alert')).toHaveTextContent('Sağlayıcı hatası.')
  })
})
