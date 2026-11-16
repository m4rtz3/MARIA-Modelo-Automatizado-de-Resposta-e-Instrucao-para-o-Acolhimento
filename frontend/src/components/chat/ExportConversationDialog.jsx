import { useEffect, useRef } from 'react'

export default function ExportConversationDialog({ onConfirmar, onCancelar }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return undefined

    dialog.showModal()
    return () => {
      if (dialog.open) dialog.close()
    }
  }, [])

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="export-conversation-title"
      aria-describedby="export-conversation-notice"
      onCancel={(event) => {
        event.preventDefault()
        onCancelar()
      }}
      className="m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-2xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-plum-950/50"
    >
      <div className="p-6">
        <h2
          id="export-conversation-title"
          className="font-display text-xl text-plum-900"
        >
          Baixar uma cópia desta conversa em texto?
        </h2>
        <p
          id="export-conversation-notice"
          className="mt-3 rounded-xl bg-paper px-4 py-3 text-sm leading-relaxed text-ink-muted"
        >
          O arquivo ficará salvo apenas no seu dispositivo. Ninguém mais terá
          acesso a ele — nem a equipe da MARIA, nem nenhum serviço externo. Se
          quiser mais privacidade, você pode apagar o arquivo depois de
          guardá-lo em um lugar seguro.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancelar}
            autoFocus
            className="min-h-10 rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink-muted transition-colors hover:bg-paper hover:text-ink"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirmar}
            className="min-h-10 rounded-lg bg-plum-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-plum-700"
          >
            Confirmar
          </button>
        </div>
      </div>
    </dialog>
  )
}
