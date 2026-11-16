import { Send } from 'lucide-react'
import { useState } from 'react'

export default function ChatInput({ onEnviar, desabilitado }) {
  const [texto, setTexto] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    const limpo = texto.trim()
    if (!limpo || desabilitado) return
    onEnviar(limpo)
    setTexto('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full items-end gap-2 border-t border-line bg-surface p-3">
      <textarea
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder="Escreva sua pergunta ou o que está acontecendo..."
        aria-label="Mensagem para a MARIA"
        disabled={desabilitado}
        className="max-h-32 min-w-0 flex-1 resize-none rounded-xl border border-line bg-paper px-4 py-3 text-[15px] text-ink placeholder:text-ink-muted focus:border-plum-500 disabled:opacity-60"
      />
      <button
        type="submit"
        disabled={desabilitado || !texto.trim()}
        aria-label="Enviar mensagem"
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-plum-800 text-plum-100 transition-colors hover:bg-plum-700 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Send size={18} aria-hidden="true" />
      </button>
    </form>
  )
}
