import { useMemo, useState } from 'react'
import { ArrowLeft, BarChart3, Sparkles } from 'lucide-react'
import TableauEmbed from './TableauEmbed'
import { criarUrlDashboard } from './dashboardFilters'
import { DASHBOARDS } from './dashboards'
import { recomendarDashboards } from './dashboardRecommendations'

export default function DashboardView({ filtros, conversas }) {
  const recomendacao = useMemo(
    () => recomendarDashboards(conversas, DASHBOARDS),
    [conversas]
  )
  const [dashboardEscolhido, setDashboardEscolhido] = useState(null)
  const dashboardSelecionadoId = dashboardEscolhido || recomendacao.recomendadoId
  const dashboardSelecionado = recomendacao.dashboards.find(
    (dashboard) => dashboard.id === dashboardSelecionadoId
  )
  const urlDashboard = criarUrlDashboard(dashboardSelecionado?.url || '', filtros)

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto px-4 py-5">
      <div className="mx-auto w-full max-w-[1600px]">
        <div className="mb-4">
          <p className="font-display text-2xl text-plum-900">Dashboards</p>
          <p className="mt-1 text-sm text-ink-muted">
            Explore indicadores agregados das bases SINAN e SIM. Os painéis
            preservam os filtros e as interações nativas do Tableau.
          </p>
        </div>

        <section
          className="mb-4 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-plum-200 bg-plum-100 p-4 sm:p-5"
          aria-labelledby="recomendacao-titulo"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-plum-800">
              <Sparkles size={17} aria-hidden="true" />
              <h2 id="recomendacao-titulo" className="text-sm font-semibold">
                Seus dashboards em destaque
              </h2>
            </div>
            <p className="mt-1.5 text-sm text-ink-muted">
              {recomendacao.personalizada
                ? `Em conversas diferentes, apareceram temas recorrentes como ${recomendacao.temas.join(', ')}.`
                : 'Ainda não há conversas recorrentes suficientes para personalizar a recomendação. O Panorama está selecionado; todos os painéis continuam disponíveis.'}
            </p>
          </div>
          {dashboardEscolhido && (
            <button
              type="button"
              onClick={() => setDashboardEscolhido(null)}
              className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg border border-plum-300 bg-white px-3 text-sm font-medium text-plum-800 transition-colors hover:bg-plum-50"
            >
              <ArrowLeft size={16} aria-hidden="true" />
              Voltar às recomendações
            </button>
          )}
        </section>

        <nav className="mb-4" aria-label="Selecionar dashboard">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
            <BarChart3 size={17} aria-hidden="true" />
            Todos os dashboards
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {recomendacao.dashboards.map((dashboard) => {
              const selecionado = dashboard.id === dashboardSelecionadoId
              const recomendado = dashboard.id === recomendacao.recomendadoId
              return (
                <button
                  key={dashboard.id}
                  type="button"
                  onClick={() => setDashboardEscolhido(dashboard.id)}
                  aria-pressed={selecionado}
                  className={`min-h-16 rounded-xl border px-3 py-2.5 text-left transition-colors ${
                    selecionado
                      ? 'border-plum-500 bg-plum-100 ring-1 ring-plum-500'
                      : 'border-line bg-surface hover:border-plum-200 hover:bg-plum-100/50'
                  }`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-plum-900">
                      {dashboard.name}
                    </span>
                    {recomendado && recomendacao.personalizada && (
                      <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-plum-800">
                        Recomendado
                      </span>
                    )}
                  </span>
                  <span className="mt-1 block text-xs leading-relaxed text-ink-muted">
                    {dashboard.description}
                  </span>
                </button>
              )
            })}
          </div>
        </nav>

        <section aria-label={`Dashboard selecionado: ${dashboardSelecionado?.name || ''}`}>
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-display text-xl text-plum-900">
              {dashboardSelecionado?.name}
            </h2>
            {dashboardSelecionado?.id === recomendacao.recomendadoId &&
              recomendacao.personalizada && (
                <span className="text-xs text-ink-muted">
                  Recomendado com base nos temas das conversas
                </span>
              )}
          </div>
          <div className="h-[min(68vh,880px)] min-h-[420px] overflow-hidden rounded-2xl border border-line bg-surface sm:min-h-[520px]">
            <TableauEmbed key={dashboardSelecionadoId} url={urlDashboard} />
          </div>
        </section>
      </div>
    </div>
  )
}
