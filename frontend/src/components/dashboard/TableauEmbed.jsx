import { useEffect, useRef, useState } from 'react'

const TABLEAU_JS_URL = 'https://public.tableau.com/javascripts/api/tableau.embed.3.latest.min.js'

/**
 * Embed via Web Component oficial do Tableau (<tableau-viz>).
 * Funciona tanto com links do Tableau Public quanto do Tableau Server/Cloud
 * (troque TABLEAU_JS_URL pelo script do seu servidor, se não for Public —
 * normalmente algo como https://SEU-SERVIDOR/javascripts/api/tableau.embed.3.min.js).
 */
export default function TableauEmbed({ url }) {
  const containerRef = useRef(null)
  const [scriptCarregado, setScriptCarregado] = useState(
    typeof window !== 'undefined' && !!customElements.get('tableau-viz')
  )

  useEffect(() => {
    if (scriptCarregado) return
    const existente = document.querySelector(`script[src="${TABLEAU_JS_URL}"]`)
    if (existente) {
      existente.addEventListener('load', () => setScriptCarregado(true))
      return
    }
    const script = document.createElement('script')
    script.src = TABLEAU_JS_URL
    script.type = 'module'
    script.onload = () => setScriptCarregado(true)
    document.head.appendChild(script)
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
    containerRef.current.appendChild(viz)
  }, [scriptCarregado, url])

  if (!url) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-line bg-surface p-8 text-center">
        <p className="max-w-sm text-sm text-ink-muted">
          Nenhum link de dashboard configurado. Defina{' '}
          <code className="rounded bg-plum-100 px-1.5 py-0.5 text-plum-800">
            VITE_TABLEAU_URL
          </code>{' '}
          no .env do front-end com o link do dashboard publicado no Tableau
          Public ou Server.
        </p>
      </div>
    )
  }

  return <div ref={containerRef} className="h-full w-full" />
}
