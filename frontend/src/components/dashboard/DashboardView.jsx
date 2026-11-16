import TableauEmbed from './TableauEmbed'
import { criarUrlDashboard } from './dashboardFilters'

const TABLEAU_URL = import.meta.env.VITE_TABLEAU_URL || ''

export default function DashboardView({ filtros }) {
  const urlDashboard = criarUrlDashboard(TABLEAU_URL, filtros)

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col gap-4 px-4 py-6">
      <div>
        <p className="font-display text-xl text-plum-900">Dashboards</p>
        <p className="mt-1 text-sm text-ink-muted">
          Painel com os achados do pipeline MARIA — bases SINAN e SIM.
          Os números refletem o histórico agregado de notificações, não
          casos individuais identificáveis.
        </p>
      </div>

      <div className="min-h-[600px] flex-1 overflow-hidden rounded-2xl border border-line bg-surface">
        <TableauEmbed url={urlDashboard} />
      </div>
    </div>
  )
}
