export interface SseMessage {
  event: string
  data: string
}

function parseBlock(block: string): SseMessage | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      data.push(line.slice(5).replace(/^ /, ''))
    }
  }
  return data.length > 0 ? { event, data: data.join('\n') } : null
}

export async function* readSse(stream: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) {
        break
      }
      buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const message = parseBlock(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (message) {
          yield message
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
    const trailing = parseBlock(buffer)
    if (trailing) {
      yield trailing
    }
  } finally {
    reader.releaseLock()
  }
}
