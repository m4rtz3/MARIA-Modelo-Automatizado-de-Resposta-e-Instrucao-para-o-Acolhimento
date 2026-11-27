import assert from 'node:assert/strict'
import test from 'node:test'
import { DASHBOARDS } from './dashboards.js'
import { recomendarDashboards } from './dashboardRecommendations.js'

function conversa(id, mensagens, atualizadaEm) {
  return {
    id,
    atualizadaEm,
    mensagens: mensagens.map((content) => ({ role: 'user', content })),
  }
}

test('configura todos os dashboards com URLs de visualização incorporáveis', () => {
  for (const dashboard of DASHBOARDS) {
    const url = new URL(dashboard.url)

    assert.match(url.pathname, /^\/views\//)
    assert.equal(url.searchParams.get(':embed'), 'true')
  }
})

test('mantém Panorama quando o tema aparece em apenas uma conversa', () => {
  const resultado = recomendarDashboards([
    conversa('a', [
      'Quero entender o perfil das vítimas',
      'Quais características das vítimas aparecem nos dados?',
      'Como analisar a faixa etária das vítimas?',
    ], '2026-11-15T10:00:00Z'),
  ], DASHBOARDS)

  assert.equal(resultado.recomendadoId, 'panorama')
  assert.equal(resultado.personalizada, false)
})

test('recomenda um tema recorrente em conversas diferentes', () => {
  const resultado = recomendarDashboards([
    conversa('a', [
      'Quero entender o perfil das vítimas',
      'Como analisar a faixa etária das vítimas?',
    ], '2026-11-15T10:00:00Z'),
    conversa('b', [
      'Quais características das vítimas aparecem nos dados?',
    ], '2026-11-14T10:00:00Z'),
  ], DASHBOARDS)

  assert.equal(resultado.recomendadoId, 'vitima')
  assert.equal(resultado.personalizada, true)
  assert.ok(resultado.temas.includes('perfil das vítimas'))
})

test('não infere interesse de uma menção isolada nem de respostas da MARIA', () => {
  const resultado = recomendarDashboards([
    {
      id: 'a',
      atualizadaEm: '2026-11-15T10:00:00Z',
      mensagens: [
        { role: 'user', content: 'O que significa a palavra gestante?' },
        { role: 'assistant', content: 'O dashboard de gestantes traz indicadores.' },
      ],
    },
  ], DASHBOARDS)

  assert.equal(resultado.recomendadoId, 'panorama')
  assert.equal(resultado.personalizada, false)
})

test('reaproveita o cálculo para a mesma lista de conversas', () => {
  const conversas = [conversa('a', ['Panorama geral dos indicadores'], '2026-11-15T10:00:00Z')]
  const primeiro = recomendarDashboards(conversas, DASHBOARDS)
  const segundo = recomendarDashboards(conversas, DASHBOARDS)

  assert.equal(segundo, primeiro)
})
