import { Download, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import ChatView from './components/chat/ChatView'
import DashboardView from './components/dashboard/DashboardView'
import ExportConversationDialog from './components/chat/ExportConversationDialog'
import EmergencyBar from './components/layout/EmergencyBar'
import Header from './components/layout/Header'
import SettingsDialog from './components/layout/SettingsDialog'
import { extrairFiltrosConversa } from './components/dashboard/dashboardFilters'
import {
  carregarConversas,
  criarConversa,
  exportarConversa,
  salvarConversas,
} from './utils/conversationStorage'

const TEMPERATURA_STORAGE_KEY = 'maria.chat.temperature.v1'

function carregarTemperatura() {
  try {
    const valorSalvo = window.localStorage.getItem(TEMPERATURA_STORAGE_KEY)
    if (valorSalvo === null) return 0.6
    const salva = Number(valorSalvo)
    return Number.isFinite(salva) && salva >= 0 && salva <= 1 ? salva : 0.6
  } catch {
    return 0.6
  }
}

export default function App() {
  const [aba, setAba] = useState('chat')
  const [configuracoesAbertas, setConfiguracoesAbertas] = useState(false)
  const [dialogoExportacaoAberto, setDialogoExportacaoAberto] = useState(false)
  const [temperatura, setTemperatura] = useState(carregarTemperatura)
  const [estadoConversas, setEstadoConversas] = useState(() => {
    const salvo = carregarConversas()
    if (salvo.conversas.length) return salvo

    const conversa = criarConversa()
    return { conversas: [conversa], conversaAtivaId: conversa.id }
  })
  const [conversasCarregando, setConversasCarregando] = useState([])
  const [erroArmazenamento, setErroArmazenamento] = useState(false)

  useEffect(() => {
    setErroArmazenamento(!salvarConversas(estadoConversas))
  }, [estadoConversas])

  const conversaAtiva = estadoConversas.conversas.find(
    (conversa) => conversa.id === estadoConversas.conversaAtivaId
  )
  const filtrosDashboard = extrairFiltrosConversa(conversaAtiva?.mensagens)

  function atualizarMensagens(conversaId, atualizar) {
    setEstadoConversas((atual) => ({
      ...atual,
      conversas: atual.conversas.map((conversa) => (
        conversa.id === conversaId
          ? {
            ...conversa,
            mensagens: atualizar(conversa.mensagens),
            atualizadaEm: new Date().toISOString(),
          }
          : conversa
      )),
    }))
  }

  function criarNovaConversa() {
    const conversa = criarConversa()
    setEstadoConversas((atual) => ({
      conversas: [conversa, ...atual.conversas],
      conversaAtivaId: conversa.id,
    }))
    setAba('chat')
  }

  function excluirConversa(conversaId) {
    if (!window.confirm('Excluir esta conversa salva neste dispositivo?')) return

    setEstadoConversas((atual) => {
      const conversas = atual.conversas.filter((conversa) => conversa.id !== conversaId)
      if (!conversas.length) {
        const nova = criarConversa()
        return { conversas: [nova], conversaAtivaId: nova.id }
      }

      return {
        conversas,
        conversaAtivaId: atual.conversaAtivaId === conversaId
          ? conversas[0].id
          : atual.conversaAtivaId,
      }
    })
  }

  function confirmarExportacao() {
    if (!conversaAtiva?.mensagens.length) return
    setDialogoExportacaoAberto(true)
  }

  function exportarConversaAtiva() {
    if (conversaAtiva?.mensagens.length) exportarConversa(conversaAtiva)
    setDialogoExportacaoAberto(false)
  }

  function definirCarregando(conversaId, carregando) {
    setConversasCarregando((atuais) => {
      if (carregando) return atuais.includes(conversaId) ? atuais : [...atuais, conversaId]
      return atuais.filter((id) => id !== conversaId)
    })
  }

  function salvarTemperatura(novaTemperatura) {
    setTemperatura(novaTemperatura)
    try {
      window.localStorage.setItem(
        TEMPERATURA_STORAGE_KEY,
        String(novaTemperatura)
      )
      return true
    } catch {
      return false
    }
  }

  return (
    <div className="flex h-dvh flex-col">
      <EmergencyBar />
      <Header
        abaAtiva={aba}
        onMudarAba={setAba}
        onAbrirConfiguracoes={() => setConfiguracoesAbertas(true)}
      />
      <SettingsDialog
        aberto={configuracoesAbertas}
        onFechar={() => setConfiguracoesAbertas(false)}
        temperatura={temperatura}
        onSalvarTemperatura={salvarTemperatura}
      />
      {dialogoExportacaoAberto && (
        <ExportConversationDialog
          onConfirmar={exportarConversaAtiva}
          onCancelar={() => setDialogoExportacaoAberto(false)}
        />
      )}

      <main className="min-h-0 flex-1 bg-paper">
        {aba === 'chat' ? (
          <div className="flex h-full w-full flex-col md:flex-row">
            <aside className="flex max-h-44 shrink-0 flex-col border-b border-line bg-surface px-3 py-3 md:max-h-none md:w-64 md:border-b-0 md:border-r md:px-4 md:py-5">
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  onClick={criarNovaConversa}
                  className="flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg bg-plum-800 px-3 text-sm font-medium text-white transition-colors hover:bg-plum-700"
                >
                  <Plus size={17} aria-hidden="true" />
                  Nova conversa
                </button>
                <button
                  type="button"
                  onClick={confirmarExportacao}
                  disabled={!conversaAtiva?.mensagens.length}
                  aria-label="Exportar conversa ativa"
                  title="Exportar conversa ativa"
                  className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-line text-ink-muted transition-colors hover:bg-paper hover:text-plum-800 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Download size={17} aria-hidden="true" />
                </button>
              </div>

              <p className="mt-3 hidden text-xs text-ink-muted md:block">
                Salvas neste dispositivo
              </p>
              <nav aria-label="Conversas salvas" className="mt-2 flex min-h-0 gap-2 overflow-x-auto md:flex-1 md:flex-col md:overflow-x-hidden md:overflow-y-auto">
                {estadoConversas.conversas.map((conversa) => {
                  const ativa = conversa.id === estadoConversas.conversaAtivaId
                  return (
                    <div
                      key={conversa.id}
                      className={`flex min-w-48 shrink-0 items-center gap-1 rounded-lg border px-2 py-1.5 md:min-w-0 ${
                        ativa ? 'border-plum-200 bg-plum-100' : 'border-transparent hover:bg-paper'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setEstadoConversas((atual) => ({
                          ...atual,
                          conversaAtivaId: conversa.id,
                        }))}
                        aria-current={ativa ? 'page' : undefined}
                        className="min-w-0 flex-1 truncate py-1 text-left text-sm text-ink"
                      >
                        {conversa.titulo}
                        <span className="ml-2 text-xs text-ink-muted">
                          {conversa.mensagens.filter((mensagem) => mensagem.role === 'user').length || ''}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => excluirConversa(conversa.id)}
                        aria-label={`Excluir ${conversa.titulo}`}
                        title="Excluir conversa"
                        className="flex size-8 shrink-0 items-center justify-center rounded-md text-ink-muted transition-colors hover:bg-clay-100 hover:text-clay-700"
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  )
                })}
              </nav>
              {erroArmazenamento && (
                <p role="alert" className="mt-2 text-xs text-clay-700">
                  Não foi possível salvar neste navegador.
                </p>
              )}
            </aside>

            <section className="min-h-0 min-w-0 flex-1" aria-label="Conversa ativa">
              <ChatView
                key={conversaAtiva?.id}
                conversa={conversaAtiva}
                atualizarMensagens={atualizarMensagens}
                carregando={conversasCarregando.includes(conversaAtiva?.id)}
                definirCarregando={definirCarregando}
                temperatura={temperatura}
              />
            </section>
          </div>
        ) : <DashboardView filtros={filtrosDashboard} />}
      </main>
    </div>
  )
}
