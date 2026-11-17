import { useEffect, useRef, useState } from 'react'

const TABLEAU_JS_URL = 'https://public.tableau.com/javascripts/api/tableau.embedding.3.latest.min.js'
let tableauScriptPromise

function carregarApiTableau() {
  if (customElements.get('tableau-viz')) return Promise.resolve()
  if (tableauScriptPromise) return tableauScriptPromise

  tableauScriptPromise = new Promise((resolve, reject) => {
    const existente = document.querySelector(`script[src="${TABLEAU_JS_URL}"]`)
    const script = existente || document.createElement('script')
    script.addEventListener('load', resolve, { once: true })
    script.addEventListener('error', () => {
      tableauScriptPromise = null
      script.remove()
      reject(new Error('Não foi possível carregar o componente do Tableau.'))
    }, { once: true })

    if (!existente) {
      script.src = TABLEAU_JS_URL
      script.type = 'module'
      document.head.appendChild(script)
    }
  })
  return tableauScriptPromise
}

/**
 * Embed via Web Component oficial do Tableau (<tableau-viz>).
 * Funciona tanto com links do Tableau Public quanto do Tableau Server/Cloud
 * (troque TABLEAU_JS_URL pelo script do seu servidor, se não for Public —
 * normalmente algo como https://SEU-SERVIDOR/javascripts/api/tableau.embed.3.min.js).
 */
export default function TableauEmbed({ url }) {
  const containerRef = useRef(null)
  const [scriptCarregado, setScriptCarregado] = useState(
    typeof window !== 'undefined' && !!window.customElements?.get('tableau-viz')
  )
  const [erro, setErro] = useState(false)

  useEffect(() => {
    if (scriptCarregado) return
    let ativo = true
    carregarApiTableau()
      .then(() => {
        if (ativo) setScriptCarregado(true)
      })
      .catch(() => {
        if (ativo) setErro(true)
      })
    return () => {
      ativo = false
    }
  }, [scriptCarregado])

  useEffect(() => {
    if (!scriptCarregado || !containerRef.current || !url) return

    containerRef.current.innerHTML = ''
    const viz = document.createElement('tableau-viz')
    viz.setAttribute('src', url)
    viz.setAttribute('toolbar', 'bottom')
    viz.setAttribute('hide-tabs', '')
    viz.style.width = '100%'
    viz.style.height = '100%'
    viz.style.display = 'block'
    containerRef.current.appendChild(viz)
  }, [scriptCarregado, url])

  if (!url) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-line bg-surface p-8 text-center">
        <p className="max-w-sm text-sm text-ink-muted">
          Nenhum link de dashboard configurado. Confira a URL desta visualização
          no catálogo de dashboards do projeto.
        </p>
      </div>
    )
  }

  if (erro) {
    return (
      <div role="alert" className="flex h-full min-h-80 items-center justify-center p-8 text-center">
        <p className="max-w-md text-sm text-ink-muted">
          Não foi possível carregar este painel do Tableau. Verifique a conexão
          e tente selecionar o dashboard novamente.
        </p>
      </div>
    )
  }

  return (
    <div className="relative h-full w-full">
      {!scriptCarregado && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-ink-muted" role="status">
          Carregando dashboard…
        </div>
      )}
      <div ref={containerRef} className="h-full w-full" />
    </div>
  )
}
