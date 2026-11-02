import { describe, expect, it } from 'vitest'
import { readSse, type SseMessage } from './sse'

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<SseMessage[]> {
  const messages: SseMessage[] = []
  for await (const message of readSse(stream)) {
    messages.push(message)
  }
  return messages
}

describe('readSse', () => {
  it('parses events split across arbitrary chunk boundaries', async () => {
    const messages = await collect(
      streamOf(['event: tok', 'en\ndata: {"text":"Mer', 'haba"}\n', '\nevent: done\ndata: {}\n\n']),
    )

    expect(messages).toEqual([
      { event: 'token', data: '{"text":"Merhaba"}' },
      { event: 'done', data: '{}' },
    ])
  })

  it('handles CRLF line endings and a trailing event without blank line', async () => {
    const messages = await collect(streamOf(['event: a\r\ndata: 1\r\n\r\nevent: b\r\ndata: 2']))

    expect(messages).toEqual([
      { event: 'a', data: '1' },
      { event: 'b', data: '2' },
    ])
  })

  it('handles a CRLF pair split across two chunks', async () => {
    const messages = await collect(streamOf(['data: 1\r', '\n\r\ndata: 2\r\n\r\n']))

    expect(messages).toEqual([
      { event: 'message', data: '1' },
      { event: 'message', data: '2' },
    ])
  })

  it('ignores comment-only blocks', async () => {
    const messages = await collect(streamOf([': keep-alive\n\ndata: x\n\n']))

    expect(messages).toEqual([{ event: 'message', data: 'x' }])
  })
})
