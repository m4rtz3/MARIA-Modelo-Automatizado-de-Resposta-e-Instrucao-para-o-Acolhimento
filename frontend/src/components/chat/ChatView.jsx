import { useEffect, useRef, useState } from 'react'
import { enviarMensagemStream } from '../../api/mariaClient'
import ChatBubble from './ChatBubble'
import ChatInput from './ChatInput'

const SUGESTOES = [
  'Meu companheiro me humilha na frente dos outros. Isso é violência?',
  'Quero denunciar mas tenho medo. O que posso fazer?',
  'O que é a Lei Maria da Penha?',
  'Como consigo uma medida protetiva?',
  'Ele controla meu dinheiro e não me deixa sair sozinha.',
]

const AVISO_IDADE_STORAGE_KEY = 'aviso_idade_confirmado'

function deveExibirAvisoIdade() {
  try {
    return window.sessionStorage.getItem(AVISO_IDADE_STORAGE_KEY) !== 'true'
  } catch (erro) {
    console.warn('Não foi possível consultar o aviso de idade nesta sessão.', erro)
    return true
  }
}

function descreverErro(erro) {
  if (erro?.code === 'quota_exceeded') {
    return {
      titulo: 'Limite de uso temporariamente atingido',
      mensagem: erro.message,
    }
  }
  if (erro?.code === 'llm_timeout') {
    return { titulo: 'A resposta demorou demais', mensagem: erro.message }
  }
  if (erro?.code === 'llm_unavailable') {
    return { titulo: 'Serviço temporariamente indisponível', mensagem: erro.message }
  }
  if (erro?.code === 'llm_error' || erro?.code === 'chat_error') {
    return { titulo: 'Não foi possível responder', mensagem: erro.message }
  }
  if (erro?.code === 'stream_unavailable') {
    return { titulo: 'Não foi possível iniciar a resposta', mensagem: erro.message }
  }
  if (erro?.status === 422) {
    return {
      titulo: 'Não foi possível enviar a mensagem',
      mensagem: 'Confira o texto e tente enviar novamente.',
    }
  }
  if (erro instanceof TypeError) {
    return {
      titulo: 'Falha de conexão',
      mensagem: 'Não foi possível conectar ao serviço. Verifique sua conexão e tente novamente.',
    }
  }
  return {
    titulo: 'Algo deu errado',
    mensagem: erro?.message || 'Não foi possível falar com a MARIA agora. Tente novamente em instantes.',
  }
}

export default function ChatView({
  conversa,
  atualizarMensagens,
  carregando,
  definirCarregando,
  temperatura,
}) {
  const [erro, setErro] = useState(null)
  const [carregamentoLongo, setCarregamentoLongo] = useState(false)
  const [avisoIdadeVisivel, setAvisoIdadeVisivel] = useState(deveExibirAvisoIdade)
  const envioEmAndamentoRef = useRef(false)
  const fimDaListaRef = useRef(null)
  const mensagens = conversa?.mensagens ?? []

  useEffect(() => {
    fimDaListaRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensagens])

  useEffect(() => {
    if (!carregando) {
      setCarregamentoLongo(false)
      return undefined
    }

    const timeout = window.setTimeout(() => setCarregamentoLongo(true), 15000)
    return () => window.clearTimeout(timeout)
  }, [carregando])

  async function enviar(texto) {
    if (!conversa || envioEmAndamentoRef.current) return
    envioEmAndamentoRef.current = true
    const conversaId = conversa.id
    setErro(null)
    const historicoParaApi = mensagens.map(({ role, content }) => ({ role, content }))

    atualizarMensagens(conversaId, (atual) => [
      ...atual,
      { role: 'user', content: texto },
      { role: 'assistant', content: '' },
    ])
    definirCarregando(conversaId, true)

    try {
      await enviarMensagemStream(
        { mensagem: texto, historico: historicoParaApi, temperatura },
        (acumulado) => {
          atualizarMensagens(conversaId, (atual) => {
            const copia = [...atual]
            copia[copia.length - 1] = { role: 'assistant', content: acumulado }
            return copia
          })
        }
      )
    } catch (e) {
      setErro(descreverErro(e))
      atualizarMensagens(conversaId, (atual) => atual.slice(0, -1))
    } finally {
      envioEmAndamentoRef.current = false
      definirCarregando(conversaId, false)
    }
  }

  const semMensagens = mensagens.length === 0

  function dispensarAvisoIdade() {
    try {
      window.sessionStorage.setItem(AVISO_IDADE_STORAGE_KEY, 'true')
    } catch (erroStorage) {
      console.warn('Não foi possível salvar a confirmação do aviso de idade.', erroStorage)
    }
    setAvisoIdadeVisivel(false)
  }

  return (
    <div className="flex h-full flex-col">
      {avisoIdadeVisivel && (
        <div
          className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-plum-200 bg-plum-100 px-4 py-3 text-sm text-plum-900"
          role="region"
          aria-label="Aviso de idade"
        >
          <p>Este serviço é destinado a pessoas com 18 anos ou mais.</p>
          <button
            type="button"
            onClick={dispensarAvisoIdade}
            className="min-h-9 rounded-lg border border-plum-700 px-3 py-1 font-medium text-plum-800 transition-colors hover:bg-plum-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-plum-700"
          >
            Entendi
          </button>
        </div>
      )}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {semMensagens && (
            <div className="rounded-2xl border border-line bg-surface p-6">
              <p className="font-display text-xl text-plum-900">
                Oi, eu sou a MARIA.
              </p>
              <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">
                Estou aqui para tirar dúvidas sobre violência doméstica, explicar
                seus direitos e ajudar a entender como buscar apoio. Você pode
                começar por uma dessas perguntas, ou escrever com suas
                próprias palavras.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {SUGESTOES.map((sugestao) => (
                  <button
                    key={sugestao}
                    onClick={() => enviar(sugestao)}
                    className="rounded-full border border-plum-200 bg-plum-100 px-3.5 py-1.5 text-sm text-plum-800 transition-colors hover:bg-plum-200"
                  >
                    {sugestao}
                  </button>
                ))}
              </div>
            </div>
          )}

          {mensagens.map((msg, i) => (
            <ChatBubble
              key={i}
              role={msg.role}
              content={msg.content}
              estadoCarregamento={
                carregando && i === mensagens.length - 1 && msg.role === 'assistant' && !msg.content
                  ? carregamentoLongo ? 'longo' : 'carregando'
                  : null
              }
            />
          ))}

          {erro && (
            <div className="rounded-xl border border-clay-600/30 bg-clay-100 px-4 py-3 text-sm text-clay-700" role="alert" aria-live="assertive">
              <p className="font-semibold">{erro.titulo}</p>
              <p className="mt-1">{erro.mensagem}</p>
            </div>
          )}

          <div ref={fimDaListaRef} />
        </div>
      </div>

      <div className="mx-auto w-full max-w-3xl">
        <details className="px-4 py-1 text-xs text-ink-muted">
          <summary className="w-fit cursor-pointer select-none">
            Sobre sua privacidade
          </summary>
          <p className="pt-1 leading-relaxed">
            Suas mensagens e o histórico desta conversa são enviados ao Gemini
            para gerar respostas e ficam salvos neste navegador. O texto da
            conversa não é enviado ao dashboard; quando configurados, apenas
            filtros genéricos inferidos localmente podem ser enviados na URL do
            Tableau.
          </p>
        </details>
        <ChatInput onEnviar={enviar} desabilitado={carregando} />
      </div>
    </div>
  )
}
