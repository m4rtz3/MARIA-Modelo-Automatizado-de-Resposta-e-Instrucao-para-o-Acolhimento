import { BarChart3, MessageCircle, Settings } from 'lucide-react'

const ABAS = [
  { id: 'chat', label: 'Conversar', icon: MessageCircle },
  { id: 'dashboard', label: 'Dashboards', icon: BarChart3 },
]

export default function Header({ abaAtiva, onMudarAba, onAbrirConfiguracoes }) {
  return (
    <header className="border-b border-line text-white" style={{ background: 'linear-gradient(90deg, #FCF7F2 0%, #FCF6F3 100%)' }}>
      <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 pb-0 pt-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <img
            src="/Logo_MARIA.png"
            alt="Logo da MARIA"
            className="h-20 w-auto object-contain"
          />
          <p className="mt-1.5 mb-2 text-sm" style={{ color: '#422548' }}>
            Apoio, informação e dados sobre violência doméstica
          </p>
        </div>

        <div className="flex items-center gap-2">
          <nav className="flex gap-1" aria-label="Navegação principal">
            {ABAS.map(({ id, label, icon: Icon }) => {
              const ativa = abaAtiva === id
              return (
                <button
                  key={id}
                  onClick={() => onMudarAba(id)}
                  aria-current={ativa ? 'page' : undefined}
                  className={`flex items-center gap-2 rounded-t-lg border border-b-0 px-4 py-2.5 text-sm font-medium transition-colors ${
                    ativa
                      ? 'border-line bg-paper text-plum-800'
                      : 'border-transparent hover:text-white'
                  }`}  style={{ color: '#422548' }}
                >
                  <Icon size={16} aria-hidden="true" />
                  {label}
                </button>
              )
            })}
          </nav>
          <button
            type="button"
            onClick={onAbrirConfiguracoes}
            aria-label="Abrir configurações"
            title="Configurações"
            className="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-white/10 hover:text-white" style={{ color: '#422548' }}
          >
            <Settings size={18} aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>
  )
}