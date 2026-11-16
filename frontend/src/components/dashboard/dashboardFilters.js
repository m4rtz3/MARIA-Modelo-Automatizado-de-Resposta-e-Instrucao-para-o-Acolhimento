const LIMITE_MENSAGENS_RECENTES = 12

const CATEGORIAS = {
  tema: {
    fisica: ['violencia fisica', 'agressao fisica'],
    psicologica: ['violencia psicologica', 'violencia emocional'],
    sexual: ['violencia sexual', 'abuso sexual'],
    patrimonial: ['violencia patrimonial', 'controle financeiro'],
    moral: ['violencia moral', 'calunia', 'difamacao'],
  },
  perfil: {
    mulher: ['mulher', 'mulheres'],
    adolescente: ['adolescente', 'adolescentes'],
    idosa: ['idosa', 'idosas'],
    lgbtqia: ['lgbtqia', 'lgbt'],
  },
  regiao: {
    norte: ['norte'],
    nordeste: ['nordeste'],
    'centro-oeste': ['centro oeste'],
    sudeste: ['sudeste'],
    sul: ['sul'],
  },
  periodo: {
    recente: ['recentemente', 'nos ultimos dias', 'atualmente', 'este ano'],
    historico: ['no passado', 'anos atras', 'antigamente', 'historico'],
  },
}

/**
 * Configure cada chave com o nome exato do campo de filtro do Tableau.
 * Exemplo: { tema: { field: 'Tipo de violência', values: { fisica: 'Física' } } }
 * Um mapeamento vazio mantém a URL original, sem enviar filtros ao Tableau.
 */
export const TABLEAU_FILTER_MAPPING = {}

function normalizar(texto) {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

function corresponde(texto, termo) {
  const termoNormalizado = normalizar(termo)
  const textoComLimites = ` ${texto} `
  let inicio = textoComLimites.indexOf(` ${termoNormalizado} `)
  while (inicio !== -1) {
    const inicioTermo = inicio + 1
    const contextoAnterior = textoComLimites.slice(Math.max(0, inicioTermo - 40), inicioTermo)
    if (!/\b(?:nao|nunca|sem)(?:\s+\p{L}+){0,2}\s*$/u.test(contextoAnterior)) return true
    inicio = textoComLimites.indexOf(` ${termoNormalizado} `, inicio + 1)
  }
  return false
}

function extrairValor(texto, opcoes) {
  return Object.entries(opcoes)
    .filter(([, termos]) => termos.some((termo) => corresponde(texto, termo)))
    .map(([valor]) => valor)
}

/**
 * Infere filtros genéricos apenas de mensagens recentes da pessoa usuária.
 * Em caso de empate, prevalece o termo encontrado mais recentemente.
 */
export function extrairFiltrosConversa(mensagens) {
  const recentes = (Array.isArray(mensagens) ? mensagens : [])
    .filter((mensagem) => mensagem?.role === 'user' && typeof mensagem.content === 'string')
    .slice(-LIMITE_MENSAGENS_RECENTES)
    .map((mensagem) => normalizar(mensagem.content))

  const filtros = {}

  for (const [categoria, opcoes] of Object.entries(CATEGORIAS)) {
    const pontuacoes = new Map()
    recentes.forEach((texto, indice) => {
      for (const valor of extrairValor(texto, opcoes)) {
        const atual = pontuacoes.get(valor) || { frequencia: 0, recencia: -1 }
        pontuacoes.set(valor, {
          frequencia: atual.frequencia + 1,
          recencia: indice,
        })
      }
    })

    const valorMaisRelevante = [...pontuacoes.entries()]
      .sort(([, a], [, b]) => b.frequencia - a.frequencia || b.recencia - a.recencia)[0]?.[0]
    if (valorMaisRelevante) filtros[categoria] = valorMaisRelevante
  }

  return filtros
}

/**
 * Converte somente filtros explicitamente mapeados em parâmetros da URL.
 */
export function criarUrlDashboard(url, filtros, mapeamento = TABLEAU_FILTER_MAPPING) {
  const configurados = Object.entries(filtros || {}).filter(([chave, valor]) => (
    typeof mapeamento[chave]?.field === 'string' &&
    mapeamento[chave].field.length > 0 &&
    typeof mapeamento[chave].values?.[valor] === 'string'
  ))
  if (!configurados.length) return url

  const urlDashboard = new URL(url)
  for (const [chave, valor] of configurados) {
    const { field, values } = mapeamento[chave]
    urlDashboard.searchParams.set(field, values[valor])
  }
  return urlDashboard.toString()
}