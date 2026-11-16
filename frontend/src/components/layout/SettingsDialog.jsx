import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import {
  salvarConfiguracoes,
  validarSenhaConfiguracoes,
} from '../../api/mariaClient'

export default function SettingsDialog({
  aberto,
  onFechar,
  temperatura,
  onSalvarTemperatura,
}) {
  const dialogRef = useRef(null)
  const [desbloqueado, setDesbloqueado] = useState(false)
  const [senha, setSenha] = useState('')
  const [chaveApi, setChaveApi] = useState('')
  const [temperaturaRascunho, setTemperaturaRascunho] = useState(temperatura)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (aberto && !dialog.open) dialog.showModal()
    if (!aberto && dialog.open) dialog.close()
  }, [aberto])

  useEffect(() => {
    if (aberto) {
      setTemperaturaRascunho(temperatura)
      setDesbloqueado(false)
      setSenha('')
      setChaveApi('')
      setErro('')
      setAviso('')
    }
  }, [aberto, temperatura])

  async function desbloquear(e) {
    e.preventDefault()
    setErro('')
    setSalvando(true)
    try {
      await validarSenhaConfiguracoes(senha)
      setSenha('')
      setDesbloqueado(true)
    } catch (e) {
      setErro(e.message)
    } finally {
      setSalvando(false)
    }
  }

  async function confirmarAlteracoes(e) {
    e.preventDefault()
    setErro('')
    setAviso('')
    setSalvando(true)
    try {
      await salvarConfiguracoes({
        senha,
        googleApiKey: chaveApi.trim() || null,
      })
      const temperaturaSalva = onSalvarTemperatura(
        Number(temperaturaRascunho)
      )
      setSenha('')
      setChaveApi('')
      setDesbloqueado(false)
      if (temperaturaSalva) {
        onFechar()
      } else {
        setAviso(
          'A chave foi salva no backend, mas não foi possível persistir a temperatura neste navegador.'
        )
      }
    } catch (e) {
      setErro(e.message)
    } finally {
      setSalvando(false)
    }
  }

  function fechar() {
    setSenha('')
    setChaveApi('')
    setDesbloqueado(false)
    onFechar()
  }

  return (
    <dialog
      ref={dialogRef}
      onClose={onFechar}
      aria-labelledby="settings-title"
      className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-2xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/40"
    >
      <div className="flex items-start justify-between border-b border-line px-5 py-4">
        <div>
          <h2 id="settings-title" className="font-display text-xl text-plum-900">
            Configurações
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Acesso protegido por senha
          </p>
        </div>
        <button
          type="button"
          onClick={fechar}
          aria-label="Fechar configurações"
          className="flex size-9 items-center justify-center rounded-lg text-ink-muted hover:bg-paper hover:text-plum-800"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {!desbloqueado ? (
        <form onSubmit={desbloquear} className="space-y-4 p-5">
          <label className="block text-sm font-medium" htmlFor="settings-unlock-password">
            Senha de configurações
          </label>
          <input
            id="settings-unlock-password"
            type="password"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
            className="w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm focus:border-plum-500"
          />
          {erro && <p role="alert" className="text-sm text-clay-700">{erro}</p>}
          {aviso && <p role="status" className="text-sm text-ink-muted">{aviso}</p>}
          <button
            type="submit"
            disabled={salvando}
            className="w-full rounded-lg bg-plum-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-plum-700 disabled:opacity-50"
          >
            {salvando ? 'Verificando...' : 'Desbloquear'}
          </button>
        </form>
      ) : (
        <form onSubmit={confirmarAlteracoes} className="space-y-5 p-5">
          <div>
            <label className="block text-sm font-medium" htmlFor="gemini-api-key">
              Chave da API Gemini
            </label>
            <input
              id="gemini-api-key"
              type="password"
              autoComplete="new-password"
              value={chaveApi}
              onChange={(e) => setChaveApi(e.target.value)}
              placeholder="Deixe em branco para manter a chave atual"
              className="mt-1.5 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm focus:border-plum-500"
            />
            <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">
              A chave será salva no `.env` do backend e aplicada imediatamente.
              Ela não fica armazenada neste navegador.
            </p>
          </div>

          <div>
            <div className="flex items-center justify-between gap-3">
              <label className="text-sm font-medium" htmlFor="chat-temperature">
                Temperatura da resposta
              </label>
              <output htmlFor="chat-temperature" className="text-sm font-semibold text-plum-800">
                {Number(temperaturaRascunho).toFixed(1)}
              </output>
            </div>
            <input
              id="chat-temperature"
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={temperaturaRascunho}
              onChange={(e) => setTemperaturaRascunho(e.target.value)}
              className="mt-3 w-full accent-plum-800"
            />
            <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">
              Valores menores deixam as respostas mais previsíveis; valores
              maiores permitem mais variação na forma de responder, mas podem
              torná-las menos consistentes. Isso não aumenta a precisão dos
              fatos. O padrão 0,6 busca equilibrar naturalidade e consistência.
              Esta preferência fica salva somente neste navegador.
            </p>
          </div>

          <label className="block text-sm font-medium" htmlFor="settings-confirm-password">
            Confirme a senha para salvar
            <input
              id="settings-confirm-password"
              type="password"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
              className="mt-1.5 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm focus:border-plum-500"
            />
          </label>

          {erro && <p role="alert" className="text-sm text-clay-700">{erro}</p>}
          {aviso && <p role="status" className="text-sm text-ink-muted">{aviso}</p>}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={fechar}
              disabled={salvando}
              className="rounded-lg border border-line px-4 py-2.5 text-sm text-ink-muted hover:bg-paper disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={salvando || !senha}
              className="rounded-lg bg-plum-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-plum-700 disabled:opacity-50"
            >
              {salvando ? 'Salvando...' : 'Confirmar alterações'}
            </button>
          </div>
        </form>
      )}
    </dialog>
  )
}
