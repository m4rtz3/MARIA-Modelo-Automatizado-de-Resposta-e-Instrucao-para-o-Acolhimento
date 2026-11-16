const STORAGE_KEY = 'maria.conversations.v1'

function criarId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function criarConversa() {
  const agora = new Date()
  const data = new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(agora)

  return {
    id: criarId(),
    titulo: `Conversa ${data}`,
    criadaEm: agora.toISOString(),
    atualizadaEm: agora.toISOString(),
    mensagens: [],
  }
}

export function carregarConversas() {
  try {
    const salvo = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}')
    const conversas = Array.isArray(salvo.conversas)
      ? salvo.conversas.filter((conversa) => (
        conversa &&
        typeof conversa.id === 'string' &&
        typeof conversa.titulo === 'string' &&
        Array.isArray(conversa.mensagens)
      ))
      : []
    const ativaExiste = conversas.some((conversa) => conversa.id === salvo.conversaAtivaId)

    return {
      conversas,
      conversaAtivaId: ativaExiste ? salvo.conversaAtivaId : conversas[0]?.id ?? null,
    }
  } catch {
    return { conversas: [], conversaAtivaId: null }
  }
}

export function salvarConversas(estado) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(estado))
    return true
  } catch {
    return false
  }
}

export function exportarConversa(conversa) {
  if (!conversa) return

  const data = new Date(conversa.criadaEm).toLocaleString('pt-BR')
  const conteudo = [
    `MARIA — ${conversa.titulo}`,
    `Criada em: ${data}`,
    '',
    ...conversa.mensagens.flatMap(({ role, content }) => {
      if (!content?.trim()) return []
      const autor = role === 'user' ? 'Você' : 'MARIA'
      return [`${autor}:`, content, '']
    }),
  ].join('\n')
  const arquivo = new Blob([conteudo], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(arquivo)
  const link = document.createElement('a')
  const nomeSeguro = conversa.titulo.replace(/[^\p{L}\p{N}-]+/gu, '-').replace(/^-|-$/g, '')
  link.href = url
  link.download = `${nomeSeguro || 'conversa-maria'}.txt`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
