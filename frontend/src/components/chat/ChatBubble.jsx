export default function ChatBubble({ role, content, estadoCarregamento }) {
  const daUsuaria = role === 'user'

  return (
    <div className={`flex ${daUsuaria ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed sm:max-w-[75%] ${
          daUsuaria
            ? 'bg-plum-800 text-plum-100 rounded-br-sm'
            : 'border border-line bg-surface text-ink rounded-bl-sm'
        }`}
      >
        {!daUsuaria && (
          <p className="mb-1 font-display text-xs font-medium tracking-wide text-plum-700">
            MARIA
          </p>
        )}
        {daUsuaria || content ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : estadoCarregamento ? (
          <div className="flex flex-wrap items-center gap-2 rounded-lg bg-paper px-3 py-2" role="status" aria-live="polite">
            <span className="text-sm italic text-ink-muted">
              {estadoCarregamento === 'longo'
                ? 'A resposta está demorando. A MARIA ainda está tentando responder; aguarde.'
                : 'MARIA está preparando uma resposta.'}
            </span>
            <span className="flex items-center gap-1" aria-hidden="true">
              <span className="loading-dot" />
              <span className="loading-dot" />
              <span className="loading-dot" />
            </span>
          </div>
        ) : null}
      </div>
    </div>
  )
}
