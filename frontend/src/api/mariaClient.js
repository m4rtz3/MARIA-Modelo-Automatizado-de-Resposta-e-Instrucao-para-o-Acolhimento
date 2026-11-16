const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function criarErroDaResposta(resp) {
  const body = await resp.json().catch(() => ({}))
  const detail = typeof body.detail === 'string'
    ? body.detail
    : body.detail?.message
  const erro = new Error(detail || `Erro ${resp.status} ao falar com a MARIA.`)
  erro.code = body.code || body.detail?.code
  erro.status = resp.status
  return erro
}

/**
 * Envia uma mensagem e recebe a resposta completa de uma vez.
 * historico: [{ role: 'user' | 'assistant', content: string }]
 */
export async function enviarMensagem({ mensagem, historico = [], topK = 3, temperatura = 0.6 }) {
  const resp = await fetch(`${API_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mensagem,
      historico,
      top_k: topK,
      temperatura,
    }),
  })
  if (!resp.ok) {
    throw await criarErroDaResposta(resp)
  }

  return resp.json() // { resposta, localizacao_detectada }
}

/**
 * Consome os eventos SSE emitidos enquanto o Gemini gera a resposta.
 * onChunk é chamado a cada pedaço de texto recebido.
 */
export async function enviarMensagemStream({ mensagem, historico = [], topK = 3, temperatura = 0.6 }, onChunk) {
  const resp = await fetch(`${API_URL}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mensagem,
      historico,
      top_k: topK,
      temperatura,
    }),
  })

  if (!resp.ok || !resp.body) {
    if (!resp.ok) throw await criarErroDaResposta(resp)
    const erro = new Error('O serviço não iniciou a resposta. Tente novamente.')
    erro.code = 'stream_unavailable'
    throw erro
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let acumulado = ''
  let buffer = ''

  function processarEvento(evento) {
    const dados = evento
      .split('\n')
      .filter((linha) => linha.startsWith('data:'))
      .map((linha) => linha.slice(5).trimStart())
      .join('\n')
    if (!dados) return

    const payload = JSON.parse(dados)
    if (payload.type === 'chunk') {
      acumulado += payload.content
      onChunk(acumulado)
    } else if (payload.type === 'error') {
      const erro = new Error(payload.detail || 'A resposta foi interrompida.')
      erro.code = payload.code
      throw erro
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const eventos = buffer.split('\n\n')
    buffer = eventos.pop() || ''
    eventos.forEach(processarEvento)
    if (done) break
  }
  if (buffer.trim()) processarEvento(buffer)

  return acumulado
}

export async function checarSaude() {
  const resp = await fetch(`${API_URL}/api/health`)
  if (!resp.ok) throw new Error('Backend indisponível.')
  return resp.json()
}

export async function validarSenhaConfiguracoes(senha) {
  const resp = await fetch(`${API_URL}/api/settings/unlock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ senha }),
  })
  if (!resp.ok) throw await criarErroDaResposta(resp)
  return resp.json()
}

export async function salvarConfiguracoes({ senha, googleApiKey }) {
  const resp = await fetch(`${API_URL}/api/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      senha,
      google_api_key: googleApiKey || null,
    }),
  })
  if (!resp.ok) throw await criarErroDaResposta(resp)
  return resp.json()
}
