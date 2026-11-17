const tableauViewUrl = (view) => (
  `https://public.tableau.com/views/Geral_Maria_Individual_TESTE/${view}` +
  '?:showVizHome=no&:language=pt-BR&:display_count=n'
)

export const DASHBOARDS = [
  {
    id: 'panorama',
    name: 'Panorama',
    description: 'Visão geral dos registros e indicadores.',
    url: tableauViewUrl('1Panorama'),
  },
  {
    id: 'vitima',
    name: 'Perfil da vítima',
    description: 'Informações e características relacionadas às vítimas.',
    url: tableauViewUrl('2Vtima'),
  },
  {
    id: 'agressor',
    name: 'Perfil do agressor',
    description: 'Informações e características relacionadas aos agressores.',
    url: tableauViewUrl('3Agressor'),
  },
  {
    id: 'agressao',
    name: 'Características da agressão',
    description: 'Ocorrências, frequência e características das agressões.',
    url: tableauViewUrl('4Agresso'),
  },
  {
    id: 'menores',
    name: 'Menores',
    description: 'Indicadores e informações referentes a menores de idade.',
    url: tableauViewUrl('5Menores'),
  },
  {
    id: 'gestantes',
    name: 'Gestantes',
    description: 'Informações e indicadores referentes às vítimas gestantes.',
    url: tableauViewUrl('6Gestantes'),
  },
  {
    id: 'qualidade',
    name: 'Qualidade dos dados',
    description: 'Preenchimento, consistência e qualidade dos registros.',
    url: tableauViewUrl('7Qualidade'),
  },
  {
    id: 'sinan-sim',
    name: 'SINAN x SIM',
    description: 'Comparação e cruzamento de informações entre as bases.',
    url: tableauViewUrl('8SINANxSIM'),
  },
]
