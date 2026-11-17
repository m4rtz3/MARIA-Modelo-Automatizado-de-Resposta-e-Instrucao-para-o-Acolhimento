const REGRAS = {
  panorama: {
    temas: {
      visaoGeral: {
        rotulo: 'visão geral dos indicadores',
        termos: [
          'panorama geral',
          'visao geral dos registros',
          'visao geral dos indicadores',
          'indicadores gerais',
          'analise geral dos dados',
          'explorar os dados',
          'tendencias gerais',
          'visao geral',
          'panorama dos dados',
        ],
      },
    },
  },
  vitima: {
    temas: {
      perfil: {
        rotulo: 'perfil das vítimas',
        termos: [
          'perfil da vitima',
          'perfil das vitimas',
          'caracteristicas da vitima',
          'caracteristicas das vitimas',
          'dados das vitimas',
        ],
      },
      demografia: {
        rotulo: 'indicadores demográficos e vulnerabilidade',
        termos: [
          'faixa etaria das vitimas',
          'faixa etaria da vitima',
          'faixa etaria',
          'idade das vitimas',
          'perfil demografico',
          'dados demograficos',
          'demografia das vitimas',
          'vulnerabilidade das vitimas',
          'vulnerabilidade',
          'raca e cor das vitimas',
          'escolaridade das vitimas',
          'condicao socioeconomica das vitimas',
        ],
      },
    },
  },
  agressor: {
    temas: {
      perfil: {
        rotulo: 'perfil dos agressores',
        termos: [
          'perfil do agressor',
          'perfil dos agressores',
          'caracteristicas do agressor',
          'caracteristicas dos agressores',
          'dados dos agressores',
        ],
      },
      relacao: {
        rotulo: 'relação entre vítima e agressor',
        termos: [
          'relacao entre vitima e agressor',
          'relacao vitima agressor',
          'vinculo entre vitima e agressor',
          'parentesco entre vitima e agressor',
        ],
      },
      comportamento: {
        rotulo: 'comportamento dos agressores',
        termos: [
          'perfil comportamental do agressor',
          'comportamento do agressor',
          'antecedentes do agressor',
        ],
      },
    },
  },
  agressao: {
    temas: {
      tipo: {
        rotulo: 'tipos e características das agressões',
        termos: [
          'tipos de violencia',
          'tipo de violencia',
          'natureza da agressao',
          'caracteristicas da agressao',
          'caracteristicas das agressoes',
        ],
      },
      recorrencia: {
        rotulo: 'frequência e recorrência',
        termos: [
          'frequencia das agressoes',
          'recorrencia da violencia',
          'violencia recorrente',
          'reincidencia das agressoes',
        ],
      },
      ocorrencia: {
        rotulo: 'local e circunstâncias das ocorrências',
        termos: [
          'local de ocorrencia',
          'local da agressao',
          'onde ocorreu a violencia',
          'circunstancias da ocorrencia',
        ],
      },
    },
  },
  menores: {
    temas: {
      violencia: {
        rotulo: 'violência contra crianças e adolescentes',
        termos: [
          'violencia contra criancas',
          'violencia contra adolescentes',
          'criancas e adolescentes',
          'criancas',
          'adolescentes',
          'menores de idade',
          'vitimas menores de idade',
          'perfil das vitimas menores',
          'violencia contra menores',
        ],
      },
    },
  },
  gestantes: {
    temas: {
      gestacao: {
        rotulo: 'violência durante a gestação',
        termos: [
          'violencia na gestacao',
          'violencia durante a gestacao',
          'violencia durante a gravidez',
          'vitimas gestantes',
          'gestante',
          'gestantes',
          'gravidez',
          'agressao contra gestante',
          'violencia contra gestantes',
        ],
      },
    },
  },
  qualidade: {
    temas: {
      consistencia: {
        rotulo: 'consistência dos registros',
        termos: [
          'qualidade dos dados',
          'inconsistencias nos registros',
          'subnotificacao',
          'registros incompletos',
          'dados faltantes',
          'campos nao preenchidos',
          'duplicidade de registros',
          'confiabilidade dos dados',
          'preenchimento dos registros',
        ],
      },
    },
  },
  'sinan-sim': {
    temas: {
      cruzamento: {
        rotulo: 'cruzamento e comparação entre SINAN e SIM',
        termos: [
          'sinan e sim',
          'sinan x sim',
          'cruzamento do sinan com o sim',
          'cruzamento das bases',
          'comparacao entre sinan e sim',
          'mortalidade e notificacoes',
          'diferencas entre as bases',
          'registros de obito e notificacoes',
        ],
      },
    },
  },
}

const LIMITE_CONVERSAS_PARA_RECENCIA = 0.15
const MIN_CONVERSAS_PARA_RECOMENDAR = 2
const MIN_MENSAGENS_PARA_RECOMENDAR = 3
const cacheRecomendacoes = new WeakMap()

function normalizar(texto) {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

function contemTermo(texto, termo) {
  return ` ${texto} `.includes(` ${termo} `)
}

function temasCorrespondentes(texto, regras) {
  const normalizado = normalizar(texto)
  return Object.entries(regras.temas)
    .filter(([, tema]) => tema.termos.some((termo) => contemTermo(normalizado, termo)))
    .map(([id]) => id)
}

function ehComplemento(texto) {
  const normalizado = normalizar(texto)
  const palavras = normalizado.split(' ').filter(Boolean)
  return palavras.length <= 8 || /^(e|tambem|nesse caso|e sobre|e quanto a)\b/.test(normalizado)
}

function listarConversasRecentes(conversas) {
  return (Array.isArray(conversas) ? conversas : [])
    .map((conversa, indiceOriginal) => ({
      conversa,
      indiceOriginal,
      atualizadoEm: Date.parse(conversa?.atualizadaEm || conversa?.criadaEm || ''),
    }))
    .sort((a, b) => {
      const aValido = Number.isFinite(a.atualizadoEm)
      const bValido = Number.isFinite(b.atualizadoEm)
      if (aValido && bValido && a.atualizadoEm !== b.atualizadoEm) {
        return b.atualizadoEm - a.atualizadoEm
      }
      if (aValido !== bValido) return aValido ? -1 : 1
      return a.indiceOriginal - b.indiceOriginal
    })
}

/**
 * Prioriza temas que aparecem em várias mensagens e conversas salvas.
 * A análise é local: o texto não é enviado à API nem ao Tableau.
 */
export function recomendarDashboards(conversas, dashboards) {
  if (Array.isArray(conversas) && cacheRecomendacoes.has(conversas)) {
    return cacheRecomendacoes.get(conversas)
  }

  const pontuacoes = new Map(
    dashboards.map((dashboard) => [
      dashboard.id,
      { score: 0, mensagens: 0, conversas: new Set(), temas: new Set() },
    ])
  )

  listarConversasRecentes(conversas).forEach(({ conversa }, indiceRecencia) => {
    if (!Array.isArray(conversa?.mensagens)) return

    const mensagensUsuario = conversa.mensagens
      .filter((mensagem) => mensagem?.role === 'user' && typeof mensagem.content === 'string')
      .map((mensagem) => mensagem.content.trim())
      .filter(Boolean)

    mensagensUsuario.forEach((conteudo, indiceMensagem) => {
      for (const [dashboardId, regras] of Object.entries(REGRAS)) {
        const pontuacao = pontuacoes.get(dashboardId)
        if (!pontuacao) continue

        let temas = temasCorrespondentes(conteudo, regras)
        if (!temas.length && ehComplemento(conteudo)) {
          const contexto = mensagensUsuario
            .slice(Math.max(0, indiceMensagem - 2), indiceMensagem)
            .join(' ')
          temas = temasCorrespondentes(contexto, regras)
        }
        if (!temas.length) continue

        pontuacao.mensagens += 1
        pontuacao.conversas.add(conversa.id || conversa.criadaEm || String(indiceRecencia))
        temas.forEach((tema) => pontuacao.temas.add(regras.temas[tema].rotulo))
        pontuacao.score += (
          1 + (temas.length - 1) * 0.25
        ) / (1 + indiceRecencia * LIMITE_CONVERSAS_PARA_RECENCIA)
      }
    })
  })

  const ranking = dashboards
    .map((dashboard) => {
      const pontuacao = pontuacoes.get(dashboard.id)
      return {
        ...dashboard,
        score: pontuacao.score,
        mensagensCorrespondentes: pontuacao.mensagens,
        conversasCorrespondentes: pontuacao.conversas.size,
        temasCorrespondentes: [...pontuacao.temas],
      }
    })
    .sort((a, b) => b.score - a.score)

  const confiaveis = ranking.filter((dashboard) => (
    dashboard.mensagensCorrespondentes >= MIN_MENSAGENS_PARA_RECOMENDAR &&
    dashboard.conversasCorrespondentes >= MIN_CONVERSAS_PARA_RECOMENDAR
  ))
  const recomendado = confiaveis[0]
    || ranking.find((dashboard) => dashboard.id === 'panorama')
    || ranking[0]

  const ordenados = [
    recomendado,
    ...ranking.filter((dashboard) => dashboard.id !== recomendado?.id),
  ].filter(Boolean)

  const resultado = {
    recomendadoId: recomendado?.id || null,
    personalizada: confiaveis.length > 0,
    dashboards: ordenados,
    temas: recomendado?.temasCorrespondentes || [],
  }
  if (Array.isArray(conversas)) cacheRecomendacoes.set(conversas, resultado)
  return resultado
}
