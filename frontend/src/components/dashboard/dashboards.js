const TABLEAU_PARAMS = '?:showVizHome=no&:language=pt-BR&:display_count=n&:embed=true'

const tableauViewUrl = (baseUrl) => {
  const separator = baseUrl.includes('?') ? '&' : '?'
  return `${baseUrl}${separator}${TABLEAU_PARAMS.slice(1)}`
}

export const DASHBOARDS = [
  {
    id: 'panorama',
    name: 'Panorama',
    description: 'Visão geral dos registros e indicadores.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Panorama_Violncia_Domstica/1Panorama'
    ),
  },
  {
    id: 'vitima',
    name: 'Perfil da vítima',
    description: 'Informações e características relacionadas às vítimas.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Quemavtima/2Vtima'
    ),
  },
  {
    id: 'agressor',
    name: 'Perfil do agressor',
    description: 'Informações e características relacionadas aos agressores.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Quemagride/3Agressor'
    ),
  },
  {
    id: 'agressao',
    name: 'Características da agressão',
    description: 'Ocorrências, frequência e características das agressões.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Comoeondeaconteceaagresso/4Agresso'
    ),
  },
  {
    id: 'menores',
    name: 'Menores',
    description: 'Indicadores e informações referentes a menores de idade.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Vtimasmenoresde18anos/5Menores'
    ),
  },
  {
    id: 'gestantes',
    name: 'Gestantes',
    description: 'Informações e indicadores referentes às vítimas gestantes.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Vtimasgestantes/6Gestantes'
    ),
  },
  {
    id: 'qualidade',
    name: 'Qualidade dos dados',
    description: 'Preenchimento, consistência e qualidade dos registros.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Qualidadedosdados_17956546591230/7Qualidade'
    ),
  },
  {
    id: 'sinan-sim',
    name: 'SINAN x SIM',
    description: 'Comparação e cruzamento de informações entre as bases.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Quemnotificadaequemmorre/8SINANxSIM'
    ),
  },
  {
    id: 'historico',
    name: 'Histórico',
    description: 'Repetição de notificações, escalada e relação com desfecho letal por chave.',
    url: tableauViewUrl(
      'https://public.tableau.com/views/Histricorepetiodenotificaesedesfecholetal/9Histrico'
    ),
  },
  {
    id: 'datasenado',
    name: 'Contexto DataSenado',
    description: 'Indicadores contextuais da Pesquisa Nacional de Violência contra a Mulher (2025).',
    url: tableauViewUrl(
      'https://public.tableau.com/views/DataSenado2025/10ContextoDataSenado'
    ),
  },
]