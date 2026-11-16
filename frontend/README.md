# MARIA — Frontend (React + Tailwind v4)

Duas telas: **Conversar** (chat com a MARIA, via backend FastAPI) e **Dados
do projeto** (embed do dashboard Tableau).

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# edite .env.local: VITE_API_URL (backend) e VITE_TABLEAU_URL (link do dashboard)
npm run dev
```

Abre em http://localhost:5173 — o backend (veja `../backend/README.md`)
precisa estar rodando em paralelo, na porta que você configurou em
`VITE_API_URL`.

## Estrutura

```
src/
  api/mariaClient.js       # fetch pro backend (chat, chat/stream, stats)
  components/
    layout/                # Header (abas), EmergencyBar (190/180 fixo)
    chat/                  # ChatView, ChatBubble, ChatInput
    dashboard/              # DashboardView, TableauEmbed
  App.jsx                  # alterna entre as duas telas
  index.css                # tokens de design (Tailwind v4 @theme)
```

As conversas são salvas no `localStorage` deste navegador. As mensagens e o
histórico selecionado são enviados à API e ao Gemini para manter o contexto e
gerar respostas. O texto da conversa não é enviado ao dashboard; filtros
genéricos inferidos localmente só são enviados ao Tableau quando há um
mapeamento explícito configurado. Em dispositivos
compartilhados, exclua as conversas ao terminar; não há gravação de relatos
no backend para uso em dashboard de XAI.

O ícone de configurações abre um painel protegido por senha, configurada como
`MARIA_SETTINGS_PASSWORD` no `.env` do backend. A chave Gemini informada é
salva somente pelo backend; a temperatura fica salva neste navegador e é
enviada com cada mensagem. Em produção, use a interface somente com a API
publicada por HTTPS.

## Sobre o embed do Tableau

`TableauEmbed.jsx` usa o Web Component oficial (`<tableau-viz>`) carregado
via `tableau.embed.3.latest.min.js` do Tableau Public. Se o dashboard for
publicado no Tableau Server/Cloud da própria instituição em vez do Tableau
Público, troque a constante `TABLEAU_JS_URL` no mesmo arquivo pelo script
do seu servidor (formato `https://SEU-SERVIDOR/javascripts/api/tableau.embed.3.min.js`)
— o resto do componente funciona igual, só muda a origem do script.

`src/components/dashboard/dashboardFilters.js` extrai filtros genéricos
(`tema`, `perfil`, `regiao` e `periodo`) das 12 mensagens mais recentes da
pessoa usuária, sem usar respostas da MARIA. A extração local é uma heurística
por termos explícitos, não uma classificação clínica ou uma leitura do
contexto. Por padrão, `TABLEAU_FILTER_MAPPING` está vazio e nenhuma informação
é acrescentada à URL.

Quando os nomes dos campos do painel forem conhecidos, configure o mapeamento
com os nomes exatos dos filtros e os valores aceitos pelo Tableau:

```js
export const TABLEAU_FILTER_MAPPING = {
  tema: {
    field: 'Tipo de violência',
    values: { fisica: 'Física', psicologica: 'Psicológica' },
  },
}
```

O `DashboardView` transforma apenas chaves e valores mapeados em parâmetros
da URL do painel. O texto das mensagens nunca é incluído. Como os parâmetros
fazem parte da URL, use esse recurso apenas com filtros que possam ser
compartilhados com o Tableau e evite incluir dados pessoais ou identificáveis.

## Build de produção

```bash
npm run build
```

Gera `dist/` — sobe em qualquer host de site estático (Vercel, Netlify,
Cloudflare Pages). Lembre de configurar `VITE_API_URL` apontando pro
backend já implantado (não pro localhost).
